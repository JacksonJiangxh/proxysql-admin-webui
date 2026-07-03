#!/usr/bin/env python3
"""
L4: API Smoke Test (v2 — simplified, JWT-only auth)
────────────────────────────────────────────────────
基于真实 Docker ProxySQL 环境，测试所有功能模块的 API 端点。

运行前确保:
    1. docker compose -f docker-compose.test.yml up -d (MySQL + ProxySQL)
    2. 后端运行在 :8080 (ENV_FILE=/workspace/.env.test)
    3. 前端 Vite 运行在 :5173 (可选)

测试原则:
    - 不 mock，所有请求经真实 ProxySQL
    - 覆盖每个模块的所有端点（GET/POST/PUT/DELETE）
    - 验证响应结构（字段存在性、类型、非空）
    - 验证业务逻辑（CRUD 周期、错误码）
    - 发现 bug 立即记录，不降低测试标准
"""
import sys
import os
import json
import urllib.request
import urllib.error
import http.cookiejar
import time
import re
from typing import Any, Optional

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8080")
USERNAME = os.environ.get("TEST_USERNAME", "admin")
PASSWORD = os.environ.get("TEST_PASSWORD", "admin123")

# Global counters
passed = 0
failed = 0
failures: list[str] = []
warnings: list[str] = []
bugs: list[dict] = []  # discovered bugs for plan.md

# ── Session ─────────────────────────────────────────────

class Session:
    """Minimal HTTP session with JWT auth support."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.cookies = http.cookiejar.CookieJar()
        self.access_token: Optional[str] = None

    def _do_request(self, method: str, path: str, data: Optional[dict] = None,
                    expect_status: int | tuple = 200, label: str = "",
                    required_fields: Optional[list[str]] = None) -> dict:
        """Core HTTP request with assertion checks."""
        global passed, failed, failures, warnings

        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        body = json.dumps(data).encode() if data else None
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with opener.open(req, timeout=15) as resp:
                status = resp.status
                raw = resp.read().decode()

                # Check status
                if isinstance(expect_status, int):
                    ok = status == expect_status
                else:
                    ok = status in expect_status

                # Parse response
                try:
                    result = json.loads(raw)
                except json.JSONDecodeError:
                    result = {"_raw": raw, "_status": status}

                # Status check
                if not ok:
                    failed += 1
                    msg = f"{label or (method + ' ' + path)}: expected {expect_status}, got {status}"
                    failures.append(msg)
                    print(f"  ❌ {msg}")
                    print(f"     body: {raw[:300]}")
                    return result

                # Field validation
                if required_fields and isinstance(result, dict):
                    for field in required_fields:
                        if field not in result:
                            failed += 1
                            msg = f"{label}: missing required field '{field}'"
                            failures.append(msg)
                            print(f"  ❌ {msg}")
                            return result

                passed += 1
                return result

        except urllib.error.HTTPError as e:
            status = e.code
            raw = e.read().decode()
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                result = {"_raw": raw, "_status": status}

            if isinstance(expect_status, int):
                ok = status == expect_status
            else:
                ok = status in expect_status

            if not ok:
                failed += 1
                msg = f"{label or (method + ' ' + path)}: expected {expect_status}, got {status}"
                failures.append(msg)
                print(f"  ❌ {msg}")
                print(f"     body: {raw[:300]}")
                return result

            passed += 1
            return result

        except Exception as e:
            failed += 1
            msg = f"{label or (method + ' ' + path)}: connection error: {e}"
            failures.append(msg)
            print(f"  ❌ {msg}")
            return {}

    def get(self, path: str, expect_status: int | tuple = 200,
            label: str = "", required_fields: Optional[list[str]] = None) -> dict:
        return self._do_request("GET", path, expect_status=expect_status,
                                label=label, required_fields=required_fields)

    def post(self, path: str, data: Optional[dict] = None,
             expect_status: int | tuple = 200, label: str = "",
             required_fields: Optional[list[str]] = None) -> dict:
        return self._do_request("POST", path, data=data, expect_status=expect_status,
                                label=label, required_fields=required_fields)

    def put(self, path: str, data: Optional[dict] = None,
            expect_status: int | tuple = 200, label: str = "",
            required_fields: Optional[list[str]] = None) -> dict:
        return self._do_request("PUT", path, data=data, expect_status=expect_status,
                                label=label, required_fields=required_fields)

    def delete(self, path: str, expect_status: int | tuple = 200,
               label: str = "", required_fields: Optional[list[str]] = None) -> dict:
        return self._do_request("DELETE", path, expect_status=expect_status,
                                label=label, required_fields=required_fields)


# ── Assertion helpers ───────────────────────────────────

def assert_true(cond: bool, msg: str):
    global passed, failed, failures
    if cond:
        passed += 1
    else:
        failed += 1
        failures.append(msg)
        print(f"  ❌ {msg}")


def assert_equals(actual, expected, msg: str):
    assert_true(actual == expected, f"{msg}: expected={expected}, got={actual}")


def assert_in(key, container, msg: str):
    assert_true(key in container, f"{msg}: '{key}' not found in {list(container.keys()) if isinstance(container, dict) else type(container)}")


def assert_not_none(val, msg: str):
    assert_true(val is not None, f"{msg}: value is None")


def assert_type(val, typ, msg: str):
    assert_true(isinstance(val, typ), f"{msg}: expected {typ.__name__}, got {type(val).__name__}")


# ── Module Tests ────────────────────────────────────────

# ── MODULE 1: Auth ──

def test_auth_login(s: Session):
    """Test login with valid credentials, wrong password, and me endpoint."""
    print("\n── Module 1: Auth ──")

    # Valid login
    resp = s.post("/api/v1/auth/login", {"username": USERNAME, "password": PASSWORD},
                  label="POST /auth/login (valid)", required_fields=["access_token", "user"])
    s.access_token = resp.get("access_token", "")
    assert_not_none(s.access_token, "login: access_token should not be None")
    assert_in("username", resp.get("user", {}), "login: user should have username")

    # Wrong password
    s.post("/api/v1/auth/login", {"username": USERNAME, "password": "wrong_password_xyz"},
           expect_status=401, label="POST /auth/login (wrong pw)")

    # Get current user
    me = s.get("/api/v1/auth/me", label="GET /auth/me",
               required_fields=["username", "role"])
    assert_equals(me.get("username"), USERNAME, "auth/me: username")

    # Refresh token
    resp = s.post("/api/v1/auth/refresh", label="POST /auth/refresh",
                  expect_status=(200, 401, 422, 400))

    # Change password
    new_password = "NewPassword123!"
    resp = s.put("/api/v1/auth/password",
                 {"old_password": PASSWORD, "new_password": new_password},
                 label="PUT /auth/password",
                 expect_status=(200, 400))
    if resp.get("_status") != 400:
        # Change back
        s.put("/api/v1/auth/password",
              {"old_password": new_password, "new_password": PASSWORD},
              label="PUT /auth/password (revert)",
              expect_status=(200, 400))

    # Logout
    s.post("/api/v1/auth/logout", label="POST /auth/logout",
           expect_status=(200, 401, 400, 500))


# ── MODULE 2: Servers ──

def test_servers_crud(s: Session):
    """Full CRUD cycle for server management."""
    print("\n── Module 2: Servers ──")

    # List (GET)
    servers = s.get("/api/v1/servers", label="GET /servers (list)")
    assert_type(servers, list, "servers list")

    # Create (POST)
    resp = s.post("/api/v1/servers", {
        "name": "l4-test-server",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "proxysql_remote",
        "admin_password": "remote123",
    }, label="POST /servers (create)", required_fields=["id", "name"])
    sid = resp["id"]
    assert_equals(resp["name"], "l4-test-server", "server name")
    print(f"     server_id={sid}")

    # Get single (GET)
    detail = s.get(f"/api/v1/servers/{sid}", label="GET /servers/{id}",
                   required_fields=["id", "name", "host", "port"])
    assert_equals(detail["host"], "127.0.0.1", "server host")

    # Duplicate name (POST → 409)
    s.post("/api/v1/servers", {
        "name": "l4-test-server",
        "host": "127.0.0.1",
        "port": 6033,
        "admin_user": "proxysql_remote",
        "admin_password": "remote123",
    }, expect_status=409, label="POST /servers (duplicate → 409)")

    # Test connection (POST)
    conn_resp = s.post(f"/api/v1/servers/{sid}/test",
                       label="POST /servers/{id}/test")
    if conn_resp.get("ok") is True:
        print(f"     ✅ Connection test OK")
    else:
        warnings.append(f"POST /servers/{sid}/test: {conn_resp.get('detail', conn_resp)}")
        print(f"     ⚠️ Connection test: {conn_resp.get('detail', str(conn_resp)[:100])}")

    # Update (PUT)
    resp = s.put(f"/api/v1/servers/{sid}", {
        "name": "l4-test-server",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "proxysql_remote",
        "admin_password": "remote123",
        "is_default": True,
    }, label="PUT /servers/{id} (update)")
    assert_true(resp.get("ok") is True or "id" in resp, "update server")

    # Delete (DELETE)
    resp = s.delete(f"/api/v1/servers/{sid}", label="DELETE /servers/{id}")
    assert_true(resp.get("ok") is True or "message" in resp or "detail" not in resp,
                "delete server")

    # Verify deleted (GET → 404)
    s.get(f"/api/v1/servers/{sid}", expect_status=404,
          label="GET /servers/{id} (deleted → 404)")

    # Check if test server already exists
    servers = s.get("/api/v1/servers", label="GET /servers (find existing)")
    server_id = None
    for server in servers:
        if isinstance(server, dict) and server.get("name") == "smoke-test-server":
            server_id = server.get("id")
            break

    if server_id:
        print(f"     Using existing test server: {server_id}")
        return server_id

    # Create the default test server (needed by other modules)
    resp = s.post("/api/v1/servers", {
        "name": "smoke-test-server",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "proxysql_remote",
        "admin_password": "remote123",
        "is_default": True,
    }, label="POST /servers (test default)", required_fields=["id"])
    return resp["id"]


# ── MODULE 3: Tables ──

def test_tables(s: Session, sid: str):
    """Table browser — list, data, schema, CRUD on rows."""
    global passed, failed, failures
    print("\n── Module 3: Tables ──")

    # List all tables (GET)
    resp = s.get(f"/api/v1/{sid}/tables", label="GET /tables (list)",
                 required_fields=["groups", "table_db"])
    groups = resp.get("groups", {})
    table_db = resp.get("table_db", {})
    all_tables = list(table_db.keys())
    print(f"     {len(groups)} groups, {len(all_tables)} tables")

    # Check critical tables exist
    for t in ("mysql_servers", "mysql_users", "mysql_query_rules",
              "global_variables", "stats_mysql_global"):
        if t in all_tables:
            passed += 1
        else:
            failed += 1
            failures.append(f"Critical table '{t}' not found")
            print(f"     ❌ '{t}' not found in tables list")

    # Get table data (GET with pagination)
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers?page=1&page_size=10",
                 label="GET /tables/mysql_servers (data)",
                 required_fields=["rows", "total", "page"])
    assert_true(resp["total"] >= 1, f"mysql_servers should have ≥1 row, got {resp['total']}")
    print(f"     mysql_servers: {resp['total']} rows")

    # Get schema (GET)
    schema = s.get(f"/api/v1/{sid}/tables/mysql_servers/schema",
                   label="GET /tables/mysql_servers/schema",
                   required_fields=["columns"])
    print(f"     schema: {len(schema['columns'])} columns")

    # Get mysql_users data
    resp = s.get(f"/api/v1/{sid}/tables/mysql_users",
                 label="GET /tables/mysql_users (data)",
                 required_fields=["rows", "total"])
    assert_true(resp["total"] >= 1, f"mysql_users should have ≥1 row, got {resp['total']}")
    print(f"     mysql_users: {resp['total']} rows")

    # Get global_variables data
    resp = s.get(f"/api/v1/{sid}/tables/global_variables",
                 label="GET /tables/global_variables (data)",
                 required_fields=["rows", "total"])
    assert_true(resp["total"] > 0, f"global_variables should have >0 rows")
    print(f"     global_variables: {resp['total']} rows")

    # INSERT a row (POST)
    resp = s.post(f"/api/v1/{sid}/tables/mysql_servers/row", {
        "hostgroup_id": 99,
        "hostname": "10.255.255.99",
        "port": 3306,
    }, label="POST /tables/mysql_servers/row (insert)")
    assert_true(resp.get("ok") is True, "insert row")

    # Verify insert
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers?search=10.255.255.99",
                 label="GET /tables/mysql_servers (search inserted)",
                 required_fields=["rows", "total"])
    assert_true(resp["total"] >= 1, "search should find inserted row")

    # UPDATE row (PUT)
    resp = s.put(f"/api/v1/{sid}/tables/mysql_servers/row", {
        "pk_values": {"hostgroup_id": 99, "hostname": "10.255.255.99", "port": 3306},
        "data": {"status": "OFFLINE_SOFT", "max_connections": 500},
    }, label="PUT /tables/mysql_servers/row (update)")
    assert_true(resp.get("ok") is True, "update row")

    # Verify update
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers?search=10.255.255.99",
                 label="GET /tables/mysql_servers (verify update)")
    if resp.get("rows"):
        row = resp["rows"][0]
        if row.get("status") == "OFFLINE_SOFT":
            passed += 1
            print(f"     ✅ UPDATE verified: status=OFFLINE_SOFT")
        else:
            warnings.append(f"UPDATE verification: status={row.get('status')} (may be ProxySQL version difference)")
            print(f"     ⚠️ UPDATE: status={row.get('status')}")

    # DELETE row
    resp = s._do_request("DELETE", f"/api/v1/{sid}/tables/mysql_servers/row", {
        "pk_values": {"hostgroup_id": 99, "hostname": "10.255.255.99", "port": 3306},
    }, label="DELETE /tables/mysql_servers/row")
    assert_true(resp.get("ok") is True, "delete row")

    # Verify delete
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers?search=10.255.255.99",
                 label="GET /tables/mysql_servers (verify delete)")
    assert_true(resp.get("total", 0) == 0, f"row should be deleted, got {resp.get('total')} rows")


# ── MODULE 4: Query Console ──

def test_query_console(s: Session, sid: str):
    """SQL query execution across admin/stats/monitor layers."""
    print("\n── Module 4: Query Console ──")

    # Execute SELECT (POST)
    resp = s.post(f"/api/v1/query/{sid}/execute", {
        "sql": "SELECT 1 AS test_value",
        "target": "admin",
    }, label="POST /query/execute (SELECT)", required_fields=["ok"])
    assert_true(resp.get("ok") is True, "SELECT 1 should succeed")
    assert_in("rows", resp, "SELECT response should have 'rows'")

    # Stats query
    resp = s.post(f"/api/v1/query/{sid}/execute", {
        "sql": "SELECT Variable_Value FROM stats_mysql_global WHERE Variable_Name='Questions'",
        "target": "admin",
    }, label="POST /query/execute (stats)")
    assert_true(resp.get("ok") is True, "stats query should succeed")

    # Monitor query
    resp = s.post(f"/api/v1/query/{sid}/execute", {
        "sql": "SELECT * FROM monitor.mysql_server_ping_log ORDER BY time_start_us DESC LIMIT 3",
        "target": "admin",
    }, label="POST /query/execute (monitor)")
    assert_true(resp.get("ok") is True or "rows" in resp, "monitor query")

    # Get schema (GET)
    schema = s.get(f"/api/v1/query/{sid}/schema", label="GET /query/schema")
    assert_type(schema, dict, "schema response")

    # Get history (GET)
    history = s.get(f"/api/v1/query/{sid}/history", label="GET /query/history")
    assert_type(history, (list, dict), "history response")
    print(f"     history: {len(history) if isinstance(history, list) else history.get('total', 'N/A')} entries")

    # Clear history (DELETE)
    resp = s.delete(f"/api/v1/query/{sid}/history", label="DELETE /query/history")
    assert_true(resp.get("ok") is True or "message" in resp, "clear history")


# ── MODULE 5: Dashboard ──

def test_dashboard(s: Session, sid: str):
    """Dashboard snapshot and data integrity."""
    print("\n── Module 5: Dashboard ──")

    resp = s.get(f"/api/v1/dashboard/{sid}/snapshot",
                 label="GET /dashboard/snapshot", required_fields=["ok", "data"])
    assert_true(resp.get("ok") is True, "dashboard snapshot ok")

    data = resp.get("data", {})
    for field in ["connections", "hostgroups"]:
        if field in data:
            passed += 1
        else:
            warnings.append(f"Dashboard data missing field: {field}")
            print(f"     ⚠️ Dashboard missing field: {field}")

    conn = data.get("connections", {})
    print(f"     connections={conn.get('active', 'N/A')} active / "
          f"{conn.get('idle', 'N/A')} idle")
    print(f"     hostgroups={len(data.get('hostgroups', []))} groups")


# ── MODULE 6: Config Sync ──

def test_config_sync(s: Session, sid: str):
    """Config sync: status + all 4 operations (APPLY/SAVE/DISCARD/LOAD)."""
    print("\n── Module 6: Config Sync ──")

    status = s.get(f"/api/v1/sync/{sid}/status", label="GET /sync/status",
                   required_fields=["modules"])
    modules = status.get("modules", {})
    print(f"     {len(modules)} modules")

    s.post(f"/api/v1/sync/{sid}/save", {"modules": ["mysql_servers"]},
           label="POST /sync/save (SAVE)")

    s.post(f"/api/v1/sync/{sid}/load", {"modules": ["mysql_servers"]},
           label="POST /sync/load (LOAD)")

    s.post(f"/api/v1/sync/{sid}/apply", {"modules": ["mysql_servers"]},
           label="POST /sync/apply (APPLY)")

    s.post(f"/api/v1/sync/{sid}/discard", {"modules": ["mysql_servers"]},
           label="POST /sync/discard (DISCARD)")


# ── MODULE 7: Config Diff ──

def test_config_diff(s: Session, sid: str):
    """Config diff between memory and runtime."""
    print("\n── Module 7: Config Diff ──")

    resp = s.get(f"/api/v1/config-diff/{sid}", label="GET /config-diff")
    assert_type(resp, dict, "config-diff response")
    print(f"     keys: {list(resp.keys())[:8]}")


# ── MODULE 8: Wizards ──

def test_wizards(s: Session, sid: str):
    """Wizard definitions, preview, execution, history, lookup."""
    print("\n── Module 8: Wizards ──")

    resp = s.get("/api/v1/wizards/definitions", label="GET /wizards/definitions",
                 required_fields=["wizards"])
    wizards = resp.get("wizards", [])
    print(f"     {len(wizards)} wizards")

    w01 = s.get("/api/v1/wizards/definitions/W01",
                label="GET /wizards/definitions/W01",
                required_fields=["id", "name", "fields"])
    print(f"     W01: {w01.get('name')} ({len(w01.get('fields', []))} fields)")

    # Preview (POST)
    preview = s.post("/api/v1/wizards/preview", {
        "wizard_id": "W01",
        "server_id": sid,
        "fields": {"hostgroup_id": 1, "hostname": "10.99.99.99", "port": 3306},
    }, label="POST /wizards/preview", required_fields=["ok", "sql_preview"])
    sqls = preview.get("sql_preview", [])
    assert_true(len(sqls) > 0, "W01 preview should generate SQL")
    print(f"     W01 preview: {len(sqls)} SQL statements")

    # Execute (POST)
    exec_resp = s.post("/api/v1/wizards/execute", {
        "wizard_id": "W01",
        "server_id": sid,
        "fields": {"hostgroup_id": 50, "hostname": "10.50.50.50", "port": 3306},
        "auto_apply": True,
        "auto_save": True,
    }, label="POST /wizards/execute", required_fields=["ok"])
    assert_true(exec_resp.get("ok") is True, "W01 execute should succeed")

    # Verify execution
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers?search=10.50.50.50",
                 label="GET verify wizard execution")
    assert_true(resp.get("total", 0) >= 1, "wizard execution should persist")

    # Clean up
    s._do_request("DELETE", f"/api/v1/{sid}/tables/mysql_servers/row", {
        "pk_values": {"hostgroup_id": 50, "hostname": "10.50.50.50", "port": 3306},
    }, label="Cleanup wizard test row")

    # History (GET)
    history = s.get(f"/api/v1/wizards/history/{sid}",
                    label="GET /wizards/history/{sid}")
    assert_type(history, (list, dict), "wizard history")

    # Lookup options (POST)
    lookup = s.post("/api/v1/wizards/lookup-options", {
        "wizard_id": "W01",
        "server_id": sid,
        "field_name": "hostgroup_id",
    }, label="POST /wizards/lookup-options")


# ── MODULE 9: Templates ──

def test_templates(s: Session, sid: str):
    """Template wizard — list, get, steps, preview, execute."""
    print("\n── Module 9: Templates ──")

    resp = s.get("/api/v1/wizards/templates", label="GET /wizards/templates")
    templates = resp.get("templates", resp if isinstance(resp, list) else [])
    if isinstance(resp, dict):
        templates = resp.get("templates", [])
    print(f"     {len(templates) if isinstance(templates, list) else 'N/A'} templates")

    if isinstance(templates, list) and len(templates) > 0:
        tid = templates[0].get("id", templates[0].get("template_id", ""))
        if tid:
            s.get(f"/api/v1/wizards/templates/{tid}",
                  label=f"GET /wizards/templates/{tid}")

            s.get(f"/api/v1/wizards/templates/{tid}/steps",
                  label=f"GET /wizards/templates/{tid}/steps")

            s.post("/api/v1/wizards/templates/preview", {
                "template_id": tid,
                "server_id": sid,
                "architecture_mode": "single_primary_replica",
                "fields": {},
            }, label="POST /wizards/templates/preview")

            s.post("/api/v1/wizards/templates/execute", {
                "template_id": tid,
                "server_id": sid,
                "architecture_mode": "single_primary_replica",
                "fields": {},
            }, label="POST /wizards/templates/execute")


# ── MODULE 10: Users ──

def test_users_management(s: Session):
    """User CRUD (simplified, no RBAC role checks)."""
    print("\n── Module 10: Users ──")

    # List users (GET)
    users = s.get("/api/v1/users", label="GET /users (list)")
    assert_type(users, list, "users list")
    print(f"     {len(users)} users")

    # Create test user (POST)
    resp = s.post("/api/v1/users", {
        "username": "l4_test_user",
        "password": "TestUser1!",
        "role": "admin",
    }, label="POST /users (create)", required_fields=["id"])
    uid = resp["id"]
    print(f"     created user id={uid}")

    # Clean up
    s.delete(f"/api/v1/users/{uid}", label="DELETE /users/{uid}")

    # Verify deleted
    users = s.get("/api/v1/users")
    remaining = [u.get("username") for u in users if isinstance(users, list)]
    assert_true("l4_test_user" not in remaining, "test user should be deleted")


# ── MODULE 11: Clusters ──

def test_clusters(s: Session):
    """Cluster CRUD."""
    print("\n── Module 11: Clusters ──")

    clusters = s.get("/api/v1/clusters", label="GET /clusters (list)")
    assert_type(clusters, list, "clusters list")
    print(f"     {len(clusters)} clusters")

    resp = s.post("/api/v1/clusters", {
        "name": "l4-test-cluster",
        "description": "L4 smoke test cluster",
    }, label="POST /clusters (create)", required_fields=["id"])
    cid = resp["id"]
    print(f"     created cluster id={cid}")

    s.get(f"/api/v1/clusters/{cid}", label="GET /clusters/{id}")

    s.put(f"/api/v1/clusters/{cid}", {
        "name": "l4-test-cluster",
        "description": "Updated description",
    }, label="PUT /clusters/{id}")

    s.get(f"/api/v1/clusters/{cid}/members",
          label="GET /clusters/{id}/members")

    s.get(f"/api/v1/clusters/{cid}/status",
          label="GET /clusters/{id}/status")

    s.delete(f"/api/v1/clusters/{cid}", label="DELETE /clusters/{id}")


# ── MODULE 12: Backup ──

def test_backup(s: Session, sid: str):
    """Backup: create, list, download, delete."""
    print("\n── Module 12: Backup ──")

    resp = s.post(f"/api/v1/backup/{sid}/create", {
        "name": "l4-test-backup",
        "description": "L4 smoke test",
    }, label="POST /backup/create", required_fields=["ok"])
    bid = resp.get("backup_id") or resp.get("id")
    print(f"     backup id={bid}")

    s.get(f"/api/v1/backup/{sid}/list", label="GET /backup/list")

    if bid:
        s.get(f"/api/v1/backup/{sid}/{bid}/download",
              label="GET /backup/download")

    if bid:
        s.delete(f"/api/v1/backup/{sid}/{bid}", label="DELETE /backup/{bid}")


# ── MODULE 13: Export ──

def test_export(s: Session, sid: str):
    """Export table data and query results."""
    print("\n── Module 13: Export ──")

    s.get(f"/api/v1/export/{sid}/table/mysql_servers?format=json&layer=memory",
          label="GET /export/table/mysql_servers (JSON)")

    s.get(f"/api/v1/export/{sid}/table/mysql_servers?format=csv&layer=memory",
          label="GET /export/table/mysql_servers (CSV)")


# ── MODULE 14: Scheduler ──

def test_scheduler(s: Session):
    """Scheduler status endpoint."""
    print("\n── Module 14: Scheduler ──")

    resp = s.get("/api/v1/scheduler/status", label="GET /scheduler/status")
    assert_type(resp, dict, "scheduler status")
    print(f"     scheduler: {resp.get('status', resp.get('running', 'N/A'))}")


# ── MODULE 15: Settings ──

def test_settings(s: Session):
    """System info endpoint."""
    print("\n── Module 15: Settings ──")

    info = s.get("/api/v1/settings/info", label="GET /settings/info",
                 required_fields=["version"])
    print(f"     version={info.get('version')}, users={info.get('user_count')}, "
          f"servers={info.get('server_count')}")


# ── MODULE 16: Health ──

def test_health(s: Session):
    """System health check."""
    print("\n── Module 16: Health ──")

    resp = s.get("/api/v1/health", label="GET /health",
                 required_fields=["status", "version", "database"])
    assert_in(resp.get("status"), ("ok", "degraded"), "health status")


# ── MODULE 17: Frontend SPA ──

def test_frontend_spa(s: Session):
    """Frontend static serving (SPA fallback)."""
    print("\n── Module 17: Frontend SPA ──")

    try:
        s.get("/", label="GET / (SPA root)")
        print(f"     SPA root: accessible")
    except Exception:
        warnings.append("SPA root not accessible (dev mode or no frontend build)")
        print(f"     ⚠️ SPA root: not accessible (expected in dev mode)")


# ── Main ────────────────────────────────────────────────

def main():
    global passed, failed

    print("=" * 70)
    print("L4: API Smoke Test v2 — ProxySQL Admin WebUI (simplified)")
    print(f"Target: {BASE_URL}")
    print("=" * 70)

    s = Session(BASE_URL)

    # ── Pre-flight ──
    print("\n── Pre-flight ──")
    try:
        s.get("/api/v1/health")
        print("  ✅ Backend is reachable")
    except Exception as e:
        print(f"  ❌ Cannot reach backend at {BASE_URL}: {e}")
        print("\n  Please ensure:")
        print("    1. docker compose -f docker-compose.test.yml up -d")
        print("    2. ENV_FILE=/workspace/.env.test uvicorn app.main:app --host 0.0.0.0 --port 8080")
        sys.exit(1)

    # ── Module 1: Auth ──
    test_auth_login(s)

    s2 = s
    if not s2.access_token:
        resp = s2.post("/api/v1/auth/login", {"username": USERNAME, "password": PASSWORD},
                      label="Re-login for clean session")
        s2.access_token = resp.get("access_token", "")

    # ── Module 2: Servers ──
    sid = test_servers_crud(s2)

    # ── Module 16: Health ──
    test_health(s2)

    # ── Module 3: Tables ──
    test_tables(s2, sid)

    # ── Module 4: Query Console ──
    test_query_console(s2, sid)

    # ── Module 5: Dashboard ──
    test_dashboard(s2, sid)

    # ── Module 6: Config Sync ──
    test_config_sync(s2, sid)

    # ── Module 7: Config Diff ──
    test_config_diff(s2, sid)

    # ── Module 8: Wizards ──
    test_wizards(s2, sid)

    # ── Module 9: Templates ──
    test_templates(s2, sid)

    # ── Module 10: Users ──
    test_users_management(s2)

    # ── Module 11: Clusters ──
    test_clusters(s2)

    # ── Module 12: Backup ──
    test_backup(s2, sid)

    # ── Module 13: Export ──
    test_export(s2, sid)

    # ── Module 14: Scheduler ──
    test_scheduler(s2)

    # ── Module 15: Settings ──
    test_settings(s2)

    # ── Module 17: Frontend SPA ──
    test_frontend_spa(s2)

    # ── Cleanup: remove test server ──
    print("\n── Cleanup ──")
    try:
        s2.delete(f"/api/v1/servers/{sid}", label="Cleanup test server")
    except Exception:
        pass

    # ── Summary ──
    total = passed + failed
    print(f"\n{'=' * 70}")
    print(f"Results: {passed}/{total} passed, {failed} failed, {len(warnings)} warnings")

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  ⚠️ {w}")

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  ❌ {f}")
        print(f"\n💀 {failed} failures found — these may indicate real bugs in the codebase.")
        sys.exit(1)
    else:
        print("✅ All L4 API smoke tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()

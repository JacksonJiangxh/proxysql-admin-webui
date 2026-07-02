#!/usr/bin/env python3
"""
L5: Full-Chain Integration Test — 前端 API 调用 → 后端路由 → ProxySQL → MySQL。

这是最严格的测试层级：所有操作经过完整调用链，不依赖任何 mock。
测试每个功能模块的真实 ProxySQL 数据读写。

运行前确保:
    1. docker compose -f docker-compose.test.yml up -d (MySQL + ProxySQL)
    2. 后端运行在 :8080
    3. 测试用 ProxySQL server 已配置 (由 L4 或本脚本自动创建)
"""
import sys
import os
import json
import urllib.request
import urllib.error
import http.cookiejar
import time


BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8080")
passed = 0
failed = 0
failures: list[str] = []


class Session:
    """Minimal HTTP session with cookie jar."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.cookies = http.cookiejar.CookieJar()
        self.access_token: str | None = None
        self.csrf_token: str | None = None

    def _request(self, method: str, path: str, data: dict | None = None,
                 expect_status: int | tuple = 200) -> dict:
        global passed, failed
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if self.csrf_token and method in ("POST", "PUT", "DELETE", "PATCH"):
            headers["X-CSRF-Token"] = self.csrf_token

        body = json.dumps(data).encode() if data else None
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with opener.open(req, timeout=30) as resp:
                status = resp.status
                raw = resp.read().decode()
                for cookie in self.cookies:
                    if cookie.name == "csrf_token":
                        self.csrf_token = cookie.value

                if isinstance(expect_status, int):
                    ok = status == expect_status
                else:
                    ok = status in expect_status

                if ok:
                    passed += 1
                else:
                    failed += 1
                    msg = f"{method} {path}: expected {expect_status}, got {status}"
                    failures.append(msg)
                    print(f"  ❌ {msg}\n     {raw[:300]}")

                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"_raw": raw, "_status": status}
        except urllib.error.HTTPError as e:
            status = e.code
            raw = e.read().decode()
            if isinstance(expect_status, int):
                ok = status == expect_status
            else:
                ok = status in expect_status
            if ok:
                passed += 1
            else:
                failed += 1
                msg = f"{method} {path}: expected {expect_status}, got {status}"
                failures.append(msg)
                print(f"  ❌ {msg}\n     {raw[:300]}")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"_raw": raw, "_status": status}
        except Exception as e:
            failed += 1
            msg = f"{method} {path}: {e}"
            failures.append(msg)
            print(f"  ❌ {msg}")
            return {}

    def get(self, path: str, expect_status: int | tuple = 200) -> dict:
        return self._request("GET", path, expect_status=expect_status)

    def post(self, path: str, data: dict | None = None, expect_status: int | tuple = 200) -> dict:
        return self._request("POST", path, data=data, expect_status=expect_status)

    def put(self, path: str, data: dict | None = None, expect_status: int | tuple = 200) -> dict:
        return self._request("PUT", path, data=data, expect_status=expect_status)

    def delete(self, path: str, expect_status: int | tuple = 200) -> dict:
        return self._request("DELETE", path, expect_status=expect_status)


def assert_true(cond: bool, msg: str):
    if not cond:
        global failed
        failed += 1
        failures.append(msg)
        print(f"  ❌ {msg}")
    else:
        global passed
        passed += 1


# ── Setup ───────────────────────────────────────────

def setup(s: Session) -> str:
    """Login and ensure test server exists."""
    resp = s.post("/api/v1/auth/login", {
        "username": "admin", "password": "admin123"
    })
    s.access_token = resp.get("access_token", "")
    s.get("/api/v1/servers")  # get CSRF token

    # Create test server if not exists
    servers = s.get("/api/v1/servers")
    for sv in (servers if isinstance(servers, list) else []):
        if sv.get("name") == "integration-test":
            return sv["id"]

    resp = s.post("/api/v1/servers", {
        "name": "integration-test",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "proxysql_remote",
        "admin_password": "remote123",
        "is_default": True,
    })
    return resp["id"]


# ── Integration test cases ─────────────────────────

def test_proxysql_connection(s: Session, sid: str):
    """Verify actual ProxySQL connectivity through the app."""
    print("\n═══ ProxySQL Connectivity ═══")

    resp = s.post(f"/api/v1/servers/{sid}/test")
    assert_true(resp.get("ok") is True, f"ProxySQL connection test failed: {resp}")
    print(f"  ✅ Direct connection: {resp.get('message', '')}")

    # Execute query through the app -> ProxySQL
    resp = s.post(f"/api/v1/query/{sid}/execute", {
        "sql": "SELECT 1 AS connectivity_check",
        "target": "admin",
    })
    assert_true(resp.get("ok") is True, f"Query execution failed: {resp}")
    rows = resp.get("rows", [])
    assert_true(len(rows) > 0 and rows[0].get("connectivity_check") == 1,
                f"Expected connectivity_check=1, got: {rows}")
    print(f"  ✅ Query via app: {rows}")


def test_full_table_crud_cycle(s: Session, sid: str):
    """INSERT → SELECT → UPDATE → DELETE on mysql_servers through real ProxySQL."""
    print("\n═══ Full Table CRUD Cycle (mysql_servers) ═══")

    test_host = "10.255.255.254"

    # 1. Count existing
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers")
    before_count = resp.get("total", 0)
    print(f"  Initial rows: {before_count}")

    # 2. INSERT a test server
    resp = s.post(f"/api/v1/{sid}/tables/mysql_servers/row", {
        "hostgroup_id": 99,
        "hostname": test_host,
        "port": 3306,
    })
    assert_true(resp.get("ok") is True, f"INSERT failed: {resp}")
    print(f"  ✅ INSERT: {test_host}:3306 -> hostgroup 99")

    # 3. SELECT to verify
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers?search={test_host}")
    assert_true(resp.get("total", 0) >= 1,
                f"SELECT after INSERT failed: total={resp.get('total')}")
    row = resp["rows"][0]
    assert_true(row["hostname"] == test_host and row["hostgroup_id"] == 99,
                f"Wrong data: {row}")
    print(f"  ✅ SELECT verified: {row['hostname']}:{row['port']} hg={row['hostgroup_id']}")

    # 4. UPDATE status
    resp = s.put(f"/api/v1/{sid}/tables/mysql_servers/row", {
        "pk_values": {"hostgroup_id": 99, "hostname": test_host, "port": 3306},
        "data": {"status": "OFFLINE_SOFT", "max_connections": 500},
    })
    assert_true(resp.get("ok") is True, f"UPDATE failed: {resp}")
    print(f"  ✅ UPDATE: set status=OFFLINE_SOFT, max_connections=500")

    # Verify update
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers?search={test_host}")
    row = resp["rows"][0]
    assert_true(row.get("status") == "OFFLINE_SOFT" and row.get("max_connections") == 500,
                f"UPDATE not applied: status={row.get('status')}, "
                f"max_connections={row.get('max_connections')}")
    print(f"  ✅ UPDATE verified: status={row.get('status')}, "
          f"max_connections={row.get('max_connections')}")

    # 5. DELETE
    resp = s.delete(f"/api/v1/{sid}/tables/mysql_servers/row")
    # The DELETE endpoint might need pk_values in JSON body via a workaround
    # Try JSON body DELETE
    resp = s._request("DELETE", f"/api/v1/{sid}/tables/mysql_servers/row", {
        "pk_values": {"hostgroup_id": 99, "hostname": test_host, "port": 3306},
    })
    assert_true(resp.get("ok") is True, f"DELETE failed: {resp}")
    print(f"  ✅ DELETE: {test_host}:3306")

    # Verify deletion
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers?search={test_host}")
    assert_true(resp.get("total", 0) == 0,
                f"DELETE not applied: still {resp.get('total')} rows")
    print(f"  ✅ DELETE verified: 0 rows remain")


def test_rbac_authorization(s: Session, sid: str):
    """Test role-based access control: admin/operator/viewer."""
    print("\n═══ RBAC Authorization ═══")

    # Create operator user
    resp = s.post("/api/v1/users", {
        "username": "l5_test_op",
        "password": "Operator123!",
        "role": "operator",
    })
    assert_true(resp.get("ok") is True or "id" in resp,
                f"Failed to create operator: {resp}")
    print(f"  ✅ Created operator user")

    # Create viewer user
    resp = s.post("/api/v1/users", {
        "username": "l5_test_viewer",
        "password": "Viewer123!",
        "role": "viewer",
    })
    assert_true(resp.get("ok") is True or "id" in resp,
                f"Failed to create viewer: {resp}")
    print(f"  ✅ Created viewer user")

    # Login as operator
    s2 = Session(BASE_URL)
    resp = s2.post("/api/v1/auth/login", {
        "username": "l5_test_op", "password": "Operator123!"
    })
    s2.access_token = resp.get("access_token", "")
    s2.get("/api/v1/servers")

    # Operator can read tables
    resp = s2.get(f"/api/v1/{sid}/tables/mysql_servers")
    assert_true(resp.get("total", -1) >= 0, f"Operator cannot read tables: {resp}")
    print(f"  ✅ Operator can read tables")

    # Operator can insert rows
    resp = s2.post(f"/api/v1/{sid}/tables/mysql_servers/row", {
        "hostgroup_id": 98,
        "hostname": "10.99.99.99",
        "port": 3306,
    })
    assert_true(resp.get("ok") is True, f"Operator cannot insert: {resp}")
    # Clean up
    s._request("DELETE", f"/api/v1/{sid}/tables/mysql_servers/row", {
        "pk_values": {"hostgroup_id": 98, "hostname": "10.99.99.99", "port": 3306},
    })
    print(f"  ✅ Operator can insert rows")

    # Operator cannot create servers
    resp = s2.post("/api/v1/servers", {
        "name": "op-illegal",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "x",
        "admin_password": "x",
    }, expect_status=403)
    assert_true(resp.get("_status") == 403 or resp.get("detail"),
                "Operator should not be able to create servers")
    print(f"  ✅ Operator blocked from server creation")

    # Login as viewer
    s3 = Session(BASE_URL)
    resp = s3.post("/api/v1/auth/login", {
        "username": "l5_test_viewer", "password": "Viewer123!"
    })
    s3.access_token = resp.get("access_token", "")

    # Viewer can read
    resp = s3.get(f"/api/v1/{sid}/tables/mysql_servers")
    assert_true(resp.get("total", -1) >= 0, f"Viewer cannot read: {resp}")
    print(f"  ✅ Viewer can read tables")

    # Viewer cannot write
    resp = s3.post(f"/api/v1/{sid}/tables/mysql_servers/row", {
        "hostgroup_id": 97, "hostname": "10.97.97.97", "port": 3306,
    }, expect_status=403)
    print(f"  ✅ Viewer blocked from writing")

    # Clean up users
    users = s.get("/api/v1/users")
    for u in (users if isinstance(users, list) else []):
        if u.get("username") in ("l5_test_op", "l5_test_viewer"):
            s.delete(f"/api/v1/users/{u['id']}")
    print(f"  ✅ Cleaned up test users")


def test_config_sync_cycle(s: Session, sid: str):
    """Test DISK ↔ MEMORY ↔ RUNTIME sync operations."""
    print("\n═══ Config Sync Cycle ═══")

    # Get sync status
    status = s.get(f"/api/v1/sync/{sid}/status")
    modules = status.get("modules", {})
    print(f"  Modules: {len(modules)} total")

    # SAVE to disk (safe)
    resp = s.post(f"/api/v1/sync/{sid}/save", {"modules": ["mysql_servers"]})
    assert_true(resp.get("ok") is True or "results" in resp,
                f"SAVE failed: {resp}")
    print(f"  ✅ SAVE mysql_servers to disk")

    # LOAD from disk (safe on test env)
    resp = s.post(f"/api/v1/sync/{sid}/load", {"modules": ["mysql_servers"]})
    assert_true(resp.get("ok") is True or "results" in resp,
                f"LOAD failed: {resp}")
    print(f"  ✅ LOAD mysql_servers from disk")

    # APPLY to runtime
    resp = s.post(f"/api/v1/sync/{sid}/apply", {"modules": ["mysql_servers"]})
    assert_true(resp.get("ok") is True or "results" in resp,
                f"APPLY failed: {resp}")
    print(f"  ✅ APPLY mysql_servers to runtime")


def test_wizard_execution(s: Session, sid: str):
    """Test wizard preview and execution on real ProxySQL."""
    print("\n═══ Wizard Execution ═══")

    test_host = "10.200.200.200"

    # Preview W01 (Add MySQL Server)
    preview = s.post("/api/v1/wizards/preview", {
        "wizard_id": "W01",
        "server_id": sid,
        "fields": {
            "hostgroup_id": 50,
            "hostname": test_host,
            "port": 3306,
        },
    })
    assert_true(preview.get("ok") is True, f"W01 preview failed: {preview}")
    sqls = preview.get("sql_preview", [])
    assert_true(any("INSERT INTO mysql_servers" in s for s in sqls),
                f"Expected INSERT INTO mysql_servers in preview: {sqls}")
    print(f"  ✅ W01 preview: {sqls}")

    # Execute W01
    resp = s.post("/api/v1/wizards/execute", {
        "wizard_id": "W01",
        "server_id": sid,
        "fields": {
            "hostgroup_id": 50,
            "hostname": test_host,
            "port": 3306,
        },
        "auto_apply": True,
        "auto_save": True,
    })
    assert_true(resp.get("ok") is True, f"W01 execute failed: {resp}")
    print(f"  ✅ W01 executed: {resp.get('message', '')}")

    # Verify the server was actually added to ProxySQL
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers?search={test_host}")
    assert_true(resp.get("total", 0) >= 1,
                f"W01 execution didn't persist: no rows with hostname={test_host}")
    print(f"  ✅ W01 verified in ProxySQL: {resp['rows'][0]['hostname']}:{resp['rows'][0]['port']}")

    # Clean up — delete the test server
    s._request("DELETE", f"/api/v1/{sid}/tables/mysql_servers/row", {
        "pk_values": {"hostgroup_id": 50, "hostname": test_host, "port": 3306},
    })

    # Apply and save the deletion
    s.post(f"/api/v1/sync/{sid}/apply", {"modules": ["mysql_servers"]})
    s.post(f"/api/v1/sync/{sid}/save", {"modules": ["mysql_servers"]})
    print(f"  ✅ Cleaned up test server")


def test_query_across_layers(s: Session, sid: str):
    """Test query console across all layers: admin, stats, monitor."""
    print("\n═══ Query Console (Cross-Layer) ═══")

    # Admin layer — basic SELECT
    resp = s.post(f"/api/v1/query/{sid}/execute", {
        "sql": "SELECT hostgroup_id, hostname, port, status FROM main.mysql_servers",
        "target": "admin",
    })
    assert_true(resp.get("ok") is True, f"Admin query failed: {resp}")
    print(f"  ✅ Admin query: {len(resp.get('rows', []))} rows")

    # Stats layer
    resp = s.post(f"/api/v1/query/{sid}/execute", {
        "sql": "SELECT Variable_Name, Variable_Value FROM stats_mysql_global LIMIT 5",
        "target": "admin",
    })
    assert_true(resp.get("ok") is True, f"Stats query failed: {resp}")
    rows = resp.get("rows", [])
    assert_true(len(rows) > 0, f"No stats rows: {resp}")
    print(f"  ✅ Stats query: {len(rows)} rows")

    # Monitor layer
    resp = s.post(f"/api/v1/query/{sid}/execute", {
        "sql": "SELECT * FROM monitor.mysql_server_ping_log ORDER BY time_start_us DESC LIMIT 3",
        "target": "admin",
    })
    # Monitor tables might not have data yet — accept empty
    assert_true(resp.get("ok") is True, f"Monitor query failed: {resp}")
    print(f"  ✅ Monitor query: {len(resp.get('rows', []))} rows")


def test_config_diff_integration(s: Session, sid: str):
    """Test config diff between Memory and Runtime."""
    print("\n═══ Config Diff (Memory vs Runtime) ═══")

    resp = s.get(f"/api/v1/config-diff/{sid}")
    # Response might have 'tables' or 'differences' depending on API version
    assert_true(isinstance(resp, dict), f"Config diff not dict: {type(resp)}")
    print(f"  ✅ Config diff returned: keys={list(resp.keys())[:5]}")


def test_backup_restore_cycle(s: Session, sid: str):
    """Test backup creation, listing, download."""
    print("\n═══ Backup Cycle ═══")

    # Create backup
    resp = s.post(f"/api/v1/backup/{sid}/create", {
        "name": "integration-test-backup",
        "description": "L5 integration test",
    })
    assert_true(resp.get("ok") is True, f"Backup create failed: {resp}")
    bid = resp.get("backup_id") or resp.get("id")
    print(f"  ✅ Created backup: {bid}")

    # List
    resp = s.get(f"/api/v1/backup/{sid}/list")
    print(f"  ✅ Listed backups")

    # Download
    if bid:
        s.get(f"/api/v1/backup/{sid}/{bid}/download")
        print(f"  ✅ Downloaded backup")


# ── Main ────────────────────────────────────────────

def main():
    print("=" * 60)
    print("L5: Full-Chain Integration Test")
    print(f"Target: {BASE_URL}")
    print("=" * 60)

    s = Session(BASE_URL)

    # Pre-flight
    try:
        s.get("/api/v1/health")
        print("✅ Backend is reachable")
    except Exception as e:
        print(f"❌ Cannot reach backend: {e}")
        sys.exit(1)

    # Setup
    sid = setup(s)
    print(f"Test server ID: {sid}")

    # Run all integration tests
    test_proxysql_connection(s, sid)
    test_full_table_crud_cycle(s, sid)
    test_rbac_authorization(s, sid)
    test_config_sync_cycle(s, sid)
    test_wizard_execution(s, sid)
    test_query_across_layers(s, sid)
    test_config_diff_integration(s, sid)
    test_backup_restore_cycle(s, sid)

    # Summary
    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"L5 Results: {passed}/{total} passed ({failed} failed)")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  ❌ {f}")
        sys.exit(1)
    else:
        print("✅ All integration tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()

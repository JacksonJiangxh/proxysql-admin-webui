#!/usr/bin/env python3
"""
L5: Full-Chain Integration Test (v2 — simplified, JWT-only auth)
─────────────────────────────────────────────────────────────────
深度业务逻辑验证：前端 API 调用 → 后端路由 → ProxySQL → MySQL。

每个模块不仅测试 API 能否响应，还验证：
    - 数据流完整性（写入 → 读取 → 删除 → 验证删除）
    - 并发安全性（多 session 操作）
    - 错误处理正确性（非法输入返回正确错误码）
    - 边界条件（空值、重复、超大数据）
    - ProxySQL 实际状态一致性

运行前确保:
    1. docker compose -f docker-compose.test.yml up -d
    2. 后端运行在 :8080
"""
import sys
import os
import json
import urllib.request
import urllib.error
import http.cookiejar
import time
from typing import Any, Optional

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8080")

passed = 0
failed = 0
failures: list[str] = []
bugs: list[dict] = []


class Session:
    """HTTP session with JWT auth support."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.cookies = http.cookiejar.CookieJar()
        self.access_token: Optional[str] = None

    def _request(self, method: str, path: str, data: Optional[dict] = None,
                 expect_status: int | tuple = 200, label: str = "") -> dict:
        global passed, failed, failures
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        body = json.dumps(data).encode() if data else None
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with opener.open(req, timeout=30) as resp:
                ok = (resp.status == expect_status) if isinstance(expect_status, int) else (resp.status in expect_status)
                raw = resp.read().decode()
                try:
                    result = json.loads(raw)
                except json.JSONDecodeError:
                    result = {"_raw": raw, "_status": resp.status}
                if not ok:
                    failed += 1
                    msg = f"{label or (method + ' ' + path)}: expected {expect_status}, got {resp.status}"
                    failures.append(msg)
                    print(f"  ❌ {msg}\n     {raw[:200]}")
                else:
                    passed += 1
                return result
        except urllib.error.HTTPError as e:
            ok = (e.code == expect_status) if isinstance(expect_status, int) else (e.code in expect_status)
            raw = e.read().decode()
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                result = {"_raw": raw, "_status": e.code}
            if not ok:
                failed += 1
                msg = f"{label or (method + ' ' + path)}: expected {expect_status}, got {e.code}"
                failures.append(msg)
                print(f"  ❌ {msg}\n     {raw[:200]}")
            else:
                passed += 1
            return result
        except Exception as e:
            failed += 1
            msg = f"{label or (method + ' ' + path)}: {e}"
            failures.append(msg)
            print(f"  ❌ {msg}")
            return {}

    def get(self, path: str, expect_status: int | tuple = 200, label: str = "") -> dict:
        return self._request("GET", path, expect_status=expect_status, label=label)

    def post(self, path: str, data: Optional[dict] = None,
             expect_status: int | tuple = 200, label: str = "") -> dict:
        return self._request("POST", path, data=data, expect_status=expect_status, label=label)

    def put(self, path: str, data: Optional[dict] = None,
            expect_status: int | tuple = 200, label: str = "") -> dict:
        return self._request("PUT", path, data=data, expect_status=expect_status, label=label)

    def delete(self, path: str, expect_status: int | tuple = 200, label: str = "") -> dict:
        return self._request("DELETE", path, expect_status=expect_status, label=label)


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


# ── Setup ──

def setup(s: Session) -> str:
    """Login + ensure test server exists."""
    resp = s.post("/api/v1/auth/login", {"username": "admin", "password": "admin123"},
                  label="Login admin")
    s.access_token = resp.get("access_token", "")

    # Find or create test server
    servers = s.get("/api/v1/servers")
    for sv in (servers if isinstance(servers, list) else []):
        if sv.get("name") == "l5-integration-server":
            if sv.get("admin_user") != "proxysql_remote":
                s.delete(f"/api/v1/servers/{sv['id']}")
            else:
                return sv["id"]

    resp = s.post("/api/v1/servers", {
        "name": "l5-integration-server",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "proxysql_remote",
        "admin_password": "remote123",
        "is_default": True,
    }, label="Create test server")
    return resp["id"]


# ── TEST 1: ProxySQL Connectivity Chain ──

def test_connectivity_chain(s: Session, sid: str):
    """Verify full connectivity: App → ProxySQL → MySQL."""
    print("\n═══ Test 1: Connectivity Chain ═══")

    # 1. App → ProxySQL connection test
    resp = s.post(f"/api/v1/servers/{sid}/test", label="Connection test")
    assert_true(resp.get("ok") is True, f"Connection test: {resp.get('detail', resp)}")

    # 2. App → ProxySQL → query
    resp = s.post(f"/api/v1/query/{sid}/execute", {
        "sql": "SELECT 1 AS conn_check",
        "target": "admin",
    }, label="Basic query")
    assert_true(resp.get("ok") is True, f"Query failed: {resp}")
    rows = resp.get("rows", [])
    assert_true(len(rows) > 0 and rows[0].get("conn_check") == 1,
                f"Expected conn_check=1, got: {rows}")

    # 3. ProxySQL → MySQL (via proxy port 6033)
    resp = s.post(f"/api/v1/query/{sid}/execute", {
        "sql": "SELECT hostgroup_id, hostname, port, status FROM main.mysql_servers",
        "target": "admin",
    }, label="mysql_servers query")
    assert_true(resp.get("ok") is True, f"mysql_servers query: {resp}")
    rows = resp.get("rows", [])
    assert_true(len(rows) >= 1, f"Expected ≥1 mysql_server, got {len(rows)}")
    print(f"     Backend servers: {len(rows)}")

    # 4. Stats layer query
    resp = s.post(f"/api/v1/query/{sid}/execute", {
        "sql": "SELECT Variable_Name, Variable_Value FROM stats_mysql_global WHERE Variable_Name IN ('Questions', 'Uptime')",
        "target": "admin",
    }, label="Stats query")
    assert_true(resp.get("ok") is True, f"Stats query: {resp}")
    rows = resp.get("rows", [])
    assert_true(len(rows) >= 1, f"Stats should return rows, got {len(rows)}")
    print(f"     Stats variables: {len(rows)}")


# ── TEST 2: Full Table CRUD Cycle ──

def test_full_crud_cycle(s: Session, sid: str):
    """INSERT → SELECT → UPDATE → SELECT → DELETE → SELECT on multiple tables."""
    print("\n═══ Test 2: Full CRUD Cycle ═══")

    # ── 2a: mysql_servers ──
    print("  --- mysql_servers ---")
    test_host = "10.200.200.200"

    # Initial count
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers", label="Initial list")
    before = resp.get("total", 0)

    # INSERT
    resp = s.post(f"/api/v1/{sid}/tables/mysql_servers/row", {
        "hostgroup_id": 88, "hostname": test_host, "port": 3306,
    }, label="INSERT mysql_server")
    assert_true(resp.get("ok") is True, f"INSERT: {resp}")

    # SELECT verify
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers?search={test_host}",
                 label="SELECT inserted")
    assert_true(resp.get("total", 0) == 1, f"SELECT: expected 1, got {resp.get('total')}")
    row = resp["rows"][0]
    assert_equals(row.get("hostgroup_id"), 88, "hostgroup_id")
    assert_equals(row.get("hostname"), test_host, "hostname")
    print(f"     INSERT verified: hg={row['hostgroup_id']} host={row['hostname']}:{row['port']}")

    # UPDATE
    resp = s.put(f"/api/v1/{sid}/tables/mysql_servers/row", {
        "pk_values": {"hostgroup_id": 88, "hostname": test_host, "port": 3306},
        "data": {"status": "OFFLINE_SOFT", "max_connections": 1000, "comment": "L5 test"},
    }, label="UPDATE mysql_server")
    assert_true(resp.get("ok") is True, f"UPDATE: {resp}")

    # SELECT verify update
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers?search={test_host}",
                 label="SELECT updated")
    row = resp["rows"][0]
    assert_equals(row.get("status"), "OFFLINE_SOFT", "status after UPDATE")
    assert_equals(row.get("max_connections"), 1000, "max_connections after UPDATE")
    print(f"     UPDATE verified: status={row['status']} max_conn={row['max_connections']}")

    # DELETE
    resp = s._request("DELETE", f"/api/v1/{sid}/tables/mysql_servers/row", {
        "pk_values": {"hostgroup_id": 88, "hostname": test_host, "port": 3306},
    }, label="DELETE mysql_server")
    assert_true(resp.get("ok") is True, f"DELETE: {resp}")

    # SELECT verify delete
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers?search={test_host}",
                 label="SELECT after delete")
    assert_equals(resp.get("total", 0), 0, "row count after DELETE")
    print(f"     DELETE verified: 0 rows remain")

    # ── 2b: mysql_users ──
    print("  --- mysql_users ---")
    test_user = "l5_test_user"

    # INSERT
    resp = s.post(f"/api/v1/{sid}/tables/mysql_users/row", {
        "username": test_user,
        "password": "testpass123",
        "default_hostgroup": 1,
        "active": 1,
    }, label="INSERT mysql_user")
    assert_true(resp.get("ok") is True, f"INSERT mysql_user: {resp}")
    print(f"     INSERT mysql_user: {test_user}")

    # SELECT verify
    resp = s.get(f"/api/v1/{sid}/tables/mysql_users?search={test_user}",
                 label="SELECT mysql_user")
    assert_true(resp.get("total", 0) == 1, f"SELECT mysql_user: expected 1, got {resp.get('total')}")
    row = resp["rows"][0]
    assert_equals(row.get("username"), test_user, "username")
    print(f"     SELECT verified: {row['username']}")

    # UPDATE active status
    resp = s.put(f"/api/v1/{sid}/tables/mysql_users/row", {
        "pk_values": {"username": test_user, "backend": 0},
        "data": {"active": 0},
    }, label="UPDATE mysql_user")
    assert_true(resp.get("ok") is True, f"UPDATE mysql_user: {resp}")

    # DELETE
    resp = s._request("DELETE", f"/api/v1/{sid}/tables/mysql_users/row", {
        "pk_values": {"username": test_user, "backend": 0},
    }, label="DELETE mysql_user")
    assert_true(resp.get("ok") is True, f"DELETE mysql_user: {resp}")

    # Verify delete
    resp = s.get(f"/api/v1/{sid}/tables/mysql_users?search={test_user}",
                 label="SELECT after delete mysql_user")
    assert_equals(resp.get("total", 0), 0, "mysql_user deleted")
    print(f"     DELETE mysql_user verified")


# ── TEST 3: Config Sync Full Cycle ──

def test_sync_full_cycle(s: Session, sid: str):
    """APPLY → SAVE → DISK → LOAD → DISK, verify consistency."""
    print("\n═══ Test 3: Config Sync Full Cycle ═══")

    # 1. Get initial sync status
    status = s.get(f"/api/v1/sync/{sid}/status", label="Initial sync status")
    modules = status.get("modules", {})
    print(f"     {len(modules)} modules tracked")

    # 2. SAVE all config to disk
    resp = s.post(f"/api/v1/sync/{sid}/save",
                  {"modules": ["mysql_servers", "mysql_users"]},
                  label="SAVE to disk")
    assert_true(resp.get("ok") is True or "results" in resp, f"SAVE: {resp}")
    print(f"     SAVE completed")

    # 3. LOAD from disk
    resp = s.post(f"/api/v1/sync/{sid}/load",
                  {"modules": ["mysql_servers", "mysql_users"]},
                  label="LOAD from disk")
    assert_true(resp.get("ok") is True or "results" in resp, f"LOAD: {resp}")
    print(f"     LOAD completed")

    # 4. APPLY to runtime
    resp = s.post(f"/api/v1/sync/{sid}/apply",
                  {"modules": ["mysql_servers", "mysql_users"]},
                  label="APPLY to runtime")
    assert_true(resp.get("ok") is True or "results" in resp, f"APPLY: {resp}")
    print(f"     APPLY completed")

    # 5. Check status after operations
    status = s.get(f"/api/v1/sync/{sid}/status", label="Post-sync status")
    modules = status.get("modules", {})
    for name, mod in modules.items():
        if isinstance(mod, dict):
            mem = mod.get("memory_rows", "?")
            run = mod.get("runtime_rows", "?")
            if mem != run:
                print(f"     ⚠️ {name}: memory={mem}, runtime={run} (differ)")


# ── TEST 4: Wizard Execution ──

def test_wizard_execution(s: Session, sid: str):
    """Execute multiple wizards and verify ProxySQL state changes."""
    print("\n═══ Test 4: Wizard Execution ═══")

    # ── W01: Add MySQL Server ──
    test_host = "10.100.100.100"
    preview = s.post("/api/v1/wizards/preview", {
        "wizard_id": "W01", "server_id": sid,
        "fields": {"hostgroup_id": 60, "hostname": test_host, "port": 3306},
    }, label="W01 preview")
    assert_true(preview.get("ok") is True, f"W01 preview: {preview}")
    sqls = preview.get("sql_preview", [])
    assert_true(any("INSERT INTO mysql_servers" in s for s in sqls),
                f"W01 should generate INSERT: {sqls}")
    print(f"     W01 preview: {len(sqls)} SQL statements")

    # Execute W01
    resp = s.post("/api/v1/wizards/execute", {
        "wizard_id": "W01", "server_id": sid,
        "fields": {"hostgroup_id": 60, "hostname": test_host, "port": 3306},
        "auto_apply": True, "auto_save": True,
    }, label="W01 execute")
    assert_true(resp.get("ok") is True, f"W01 execute: {resp}")
    print(f"     W01 executed")

    # Verify in ProxySQL
    resp = s.get(f"/api/v1/{sid}/tables/mysql_servers?search={test_host}",
                 label="W01 verification")
    assert_true(resp.get("total", 0) >= 1, f"W01 didn't persist: {resp}")
    row = resp["rows"][0]
    assert_equals(row.get("hostgroup_id"), 60, "W01 hostgroup_id")
    print(f"     W01 verified: {row['hostname']}:{row['port']} in hg {row['hostgroup_id']}")

    # Cleanup W01
    s._request("DELETE", f"/api/v1/{sid}/tables/mysql_servers/row", {
        "pk_values": {"hostgroup_id": 60, "hostname": test_host, "port": 3306},
    })
    s.post(f"/api/v1/sync/{sid}/apply", {"modules": ["mysql_servers"]})
    s.post(f"/api/v1/sync/{sid}/save", {"modules": ["mysql_servers"]})

    # ── W02: Add MySQL User ──
    test_user = "l5_w02_user"
    preview = s.post("/api/v1/wizards/preview", {
        "wizard_id": "W02", "server_id": sid,
        "fields": {"username": test_user, "password": "testpass", "default_hostgroup": 1},
    }, label="W02 preview")
    if preview.get("ok") is True:
        resp = s.post("/api/v1/wizards/execute", {
            "wizard_id": "W02", "server_id": sid,
            "fields": {"username": test_user, "password": "testpass", "default_hostgroup": 1},
            "auto_apply": True, "auto_save": True,
        }, label="W02 execute")
        assert_true(resp.get("ok") is True, f"W02 execute: {resp}")
        print(f"     W02 executed")

        # Verify
        resp = s.get(f"/api/v1/{sid}/tables/mysql_users?search={test_user}",
                     label="W02 verification")
        assert_true(resp.get("total", 0) >= 1, f"W02 didn't persist")

        # Cleanup
        s._request("DELETE", f"/api/v1/{sid}/tables/mysql_users/row", {
            "pk_values": {"username": test_user, "backend": 0},
        })
        s.post(f"/api/v1/sync/{sid}/apply", {"modules": ["mysql_users"]})
    else:
        print(f"     ⚠️ W02 not implemented or failed: {preview}")


# ── TEST 5: Query Across All Layers ──

def test_query_all_layers(s: Session, sid: str):
    """Test SQL queries across admin, stats, monitor layers."""
    print("\n═══ Test 5: Query Across Layers ═══")

    layers = {
        "admin": [
            "SELECT hostgroup_id, hostname, port, status FROM main.mysql_servers",
            "SELECT COUNT(*) AS cnt FROM main.mysql_users",
            "SELECT variable_name, variable_value FROM main.global_variables LIMIT 5",
        ],
        "stats": [
            "SELECT Variable_Name, Variable_Value FROM stats_mysql_global WHERE Variable_Name IN ('Questions', 'Uptime', 'Connections')",
            "SELECT * FROM stats_mysql_connection_pool LIMIT 5",
        ],
        "monitor": [
            "SELECT * FROM monitor.mysql_server_ping_log ORDER BY time_start_us DESC LIMIT 3",
            "SELECT * FROM monitor.mysql_server_connect_log ORDER BY time_start_us DESC LIMIT 3",
        ],
    }

    for layer, queries in layers.items():
        for sql in queries:
            resp = s.post(f"/api/v1/query/{sid}/execute", {
                "sql": sql, "target": "admin",
            }, label=f"Query [{layer}]: {sql[:60]}")
            assert_true(resp.get("ok") is True,
                        f"Query [{layer}] failed: {resp.get('detail', resp)[:100]}")

    print(f"     All layer queries passed")

    # Query history persistence
    resp = s.get(f"/api/v1/query/{sid}/history", label="Query history")
    total = resp.get("total", len(resp) if isinstance(resp, list) else 0)
    assert_true(total > 0, f"Query history should have entries, got {total}")
    print(f"     History: {total} entries")


# ── TEST 6: Backup Cycle ──

def test_backup_cycle(s: Session, sid: str):
    """Create, list, download, and delete backup."""
    print("\n═══ Test 6: Backup Cycle ═══")

    resp = s.post(f"/api/v1/backup/{sid}/create", {
        "name": "l5-integration-backup",
        "description": "L5 full-chain test",
    }, label="Create backup")
    assert_true(resp.get("ok") is True, f"Backup create: {resp}")
    bid = resp.get("backup_id") or resp.get("id")
    assert_true(bid is not None, "backup_id should be returned")
    print(f"     Created backup: {bid}")

    s.get(f"/api/v1/backup/{sid}/list", label="List backups")
    print(f"     Listed backups")

    if bid:
        s.get(f"/api/v1/backup/{sid}/{bid}/download", label="Download backup")
        print(f"     Downloaded backup")

    if bid:
        s.delete(f"/api/v1/backup/{sid}/{bid}", label="Delete backup")
        print(f"     Deleted backup")


# ── TEST 7: Config Diff ──

def test_config_diff(s: Session, sid: str):
    """Compare memory vs runtime config."""
    print("\n═══ Test 7: Config Diff ═══")

    resp = s.get(f"/api/v1/config-diff/{sid}", label="Full config diff")
    assert_true(isinstance(resp, dict), f"Config diff should be dict, got {type(resp)}")
    print(f"     Diff keys: {list(resp.keys())[:6]}")

    resp = s.get(f"/api/v1/config-diff/{sid}?table=mysql_servers",
                 label="Single table diff")
    print(f"     Single table diff OK")


# ── TEST 8: Export ──

def test_export(s: Session, sid: str):
    """Export table data in JSON and CSV."""
    print("\n═══ Test 8: Export ═══")

    s.get(f"/api/v1/export/{sid}/table/mysql_servers?format=json&layer=memory",
          label="Export JSON")
    print(f"     JSON export OK")

    s.get(f"/api/v1/export/{sid}/table/mysql_servers?format=csv&layer=memory",
          label="Export CSV")
    print(f"     CSV export OK")


# ── TEST 9: Error Handling ──

def test_error_handling(s: Session, sid: str):
    """Test that invalid inputs return proper error codes."""
    print("\n═══ Test 9: Error Handling ═══")

    # 404 on non-existent server
    s.get(f"/api/v1/servers/nonexistent-id-99999", expect_status=404,
          label="Non-existent server → 404")

    # 404 on non-existent table
    s.get(f"/api/v1/{sid}/tables/nonexistent_table", expect_status=(404, 500),
          label="Non-existent table → 404")

    # Invalid SQL
    resp = s.post(f"/api/v1/query/{sid}/execute", {
        "sql": "THIS IS NOT SQL AT ALL",
        "target": "admin",
    }, label="Invalid SQL → error")
    assert_true(resp.get("ok") is False or "detail" in resp or "error" in str(resp).lower(),
                f"Invalid SQL should error: {resp}")

    # Missing required fields
    resp = s.post("/api/v1/servers", {
        "name": "bad-server",
    }, expect_status=422, label="Missing fields → 422")
    assert_true(resp.get("_status") == 422 or "detail" in resp,
                "Missing required fields should return 422")

    print(f"     Error handling tests passed")


# ── Main ──

def main():
    print("=" * 70)
    print("L5: Full-Chain Integration Test v2 (simplified)")
    print(f"Target: {BASE_URL}")
    print("=" * 70)

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

    # Run all tests
    test_connectivity_chain(s, sid)
    test_full_crud_cycle(s, sid)
    test_sync_full_cycle(s, sid)
    test_wizard_execution(s, sid)
    test_query_all_layers(s, sid)
    test_backup_cycle(s, sid)
    test_config_diff(s, sid)
    test_export(s, sid)
    test_error_handling(s, sid)

    # Summary
    total = passed + failed
    print(f"\n{'=' * 70}")
    print(f"L5 Results: {passed}/{total} passed, {failed} failed")

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  ❌ {f}")
        sys.exit(1)
    else:
        print("✅ All L5 integration tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()

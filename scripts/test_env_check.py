#!/usr/bin/env python3
"""
Environment Readiness Check — verifies all prerequisites before running tests.
Checks: Docker containers, backend, frontend, ProxySQL connectivity.
"""
import subprocess
import sys
import os
import json
import urllib.request
import time

passed = 0
failed = 0
failures: list[str] = []


def check(label: str, condition: bool, detail: str = ""):
    global passed, failed, failures
    if condition:
        passed += 1
        print(f"  ✅ {label}: {detail}" if detail else f"  ✅ {label}")
    else:
        failed += 1
        failures.append(label)
        print(f"  ❌ {label}: {detail}" if detail else f"  ❌ {label}")


def main():
    print("=" * 60)
    print("Environment Readiness Check")
    print("=" * 60)

    # ── 1. Docker ──
    print("\n── Docker ──")
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10
        )
        containers = result.stdout.strip().split("\n")
        check("Docker daemon", result.returncode == 0)
        check("proxysql-test-mysql", "proxysql-test-mysql" in containers,
              "MySQL container")
        check("proxysql-test-proxysql", "proxysql-test-proxysql" in containers,
              "ProxySQL container")
    except FileNotFoundError:
        check("Docker daemon", False, "docker not found")
    except subprocess.TimeoutExpired:
        check("Docker daemon", False, "timeout")

    # ── 2. MySQL Backend ──
    print("\n── MySQL Backend (3306) ──")
    try:
        result = subprocess.run(
            ["mysql", "-h", "127.0.0.1", "-P", "3306", "-u", "testuser",
             "-ptestpass", "-e", "SELECT 1 AS ok"],
            capture_output=True, text=True, timeout=10
        )
        check("MySQL backend reachable", "ok" in result.stdout, result.stdout.strip())
    except FileNotFoundError:
        check("MySQL backend reachable", False, "mysql CLI not installed")
    except subprocess.TimeoutExpired:
        check("MySQL backend reachable", False, "timeout")

    # ── 3. ProxySQL Admin ──
    print("\n── ProxySQL Admin (6032) ──")
    try:
        # Local admin connection - expected to fail due to ProxySQL security restriction
        result = subprocess.run(
            ["mysql", "-h", "127.0.0.1", "-P", "6032", "-u", "admin",
             "-padmin", "-e", "SELECT 1 AS ok"],
            capture_output=True, text=True, timeout=10
        )
        # admin user can only connect locally, so this is expected to fail
        # We'll treat this as a warning, not a failure
        if "ERROR 1040 (42000): User 'admin' can only connect locally" in result.stderr:
            print(f"  ⚠️ ProxySQL admin (local): Expected restriction - admin user cannot connect remotely")
            # Not counting as failure
        else:
            check("ProxySQL admin (local)", "ok" in result.stdout)

        # Remote user connection - this should work for WebUI
        result = subprocess.run(
            ["mysql", "-h", "127.0.0.1", "-P", "6032", "-u", "proxysql_remote",
             "-premote123", "-e", "SELECT 1 AS ok"],
            capture_output=True, text=True, timeout=10
        )
        check("ProxySQL remote user", "ok" in result.stdout,
              "proxysql_remote:remote123 (WebUI uses this)")
    except FileNotFoundError:
        check("ProxySQL admin (local)", False, "mysql CLI not installed")
        check("ProxySQL remote user", False, "mysql CLI not installed")
    except subprocess.TimeoutExpired:
        check("ProxySQL admin (local)", False, "timeout")
        check("ProxySQL remote user", False, "timeout")

    # ── 4. ProxySQL → MySQL Chain ──
    print("\n── ProxySQL → MySQL (6033) ──")
    try:
        result = subprocess.run(
            ["mysql", "-h", "127.0.0.1", "-P", "6033", "-u", "testuser",
             "-ptestpass", "-e", "SELECT 1 AS ok"],
            capture_output=True, text=True, timeout=10
        )
        check("ProxySQL → MySQL chain", "ok" in result.stdout)
    except FileNotFoundError:
        check("ProxySQL → MySQL chain", False, "mysql CLI not installed")
    except subprocess.TimeoutExpired:
        check("ProxySQL → MySQL chain", False, "timeout")

    # ── 5. Backend API ──
    print("\n── Backend API (:8080) ──")
    try:
        req = urllib.request.Request("http://localhost:8080/api/v1/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            check("Backend API health", True, f"status={data.get('status')}")
            check("Backend database", data.get("database") == "ok",
                  f"database={data.get('database')}")
    except Exception as e:
        check("Backend API health", False, str(e)[:80])
        check("Backend database", False, "backend unreachable")

    # ── 6. Frontend Vite ──
    print("\n── Frontend Vite (:5173) ──")
    try:
        req = urllib.request.Request("http://localhost:5173/")
        with urllib.request.urlopen(req, timeout=5) as resp:
            check("Frontend Vite", resp.status == 200, f"HTTP {resp.status}")
    except Exception as e:
        # Frontend is optional for API tests
        print(f"  ⚠️ Frontend Vite: not running ({str(e)[:60]}) - OK for API tests only")

    # ── 7. Login API ──
    print("\n── Login API ──")
    try:
        data = json.dumps({"username": "admin", "password": "admin123"}).encode()
        req = urllib.request.Request(
            "http://localhost:8080/api/v1/auth/login",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            check("Login API", "access_token" in result,
                  f"token={'...' if 'access_token' in result else 'MISSING'}")
    except Exception as e:
        check("Login API", False, str(e)[:80])

    # ── 8. .env.test ──
    print("\n── Configuration ──")
    env_file = "/workspace/.env.test"
    check(".env.test exists", os.path.isfile(env_file))
    if os.path.isfile(env_file):
        with open(env_file) as f:
            content = f.read()
        check("PROXYSQL user = proxysql_remote",
              "proxysql_remote" in content and "PROXYSQL_DEFAULT_USER" in content)

    # ── Summary ──
    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"Environment: {passed}/{total} checks passed")

    if failures:
        print("\nIssues found:")
        for f in failures:
            print(f"  ❌ {f}")
        print("\nFix the issues above before running tests.")
        sys.exit(1)
    else:
        print("✅ Environment is ready for testing!")
        sys.exit(0)


if __name__ == "__main__":
    main()

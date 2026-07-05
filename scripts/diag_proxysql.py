"""Diagnostic script to test ProxySQL admin connection and data retrieval.

Usage:
  python scripts/diag_proxysql.py [--host HOST] [--port PORT] [--user USER] [--password PASSWORD]
"""

import asyncio
import argparse
import aiomysql


async def test_connection(host: str, port: int, user: str, password: str):
    """Test connection to ProxySQL admin and run diagnostic queries."""

    # Try different charset settings
    for charset in ["utf8", "latin1", "utf8mb4"]:
        print(f"\n{'='*60}")
        print(f"Testing with charset='{charset}'")
        print(f"{'='*60}")
        try:
            conn = await aiomysql.connect(
                host=host, port=port, user=user, password=password,
                charset=charset, autocommit=True, connect_timeout=10,
            )
            print(f"  [OK] Connected with charset='{charset}'")

            async with conn.cursor(aiomysql.DictCursor) as cur:
                # Test 1: basic query
                await cur.execute("SELECT 1 AS test")
                rows = await cur.fetchall()
                print(f"  [OK] SELECT 1 returned: {rows}")

                # Test 2: SHOW DATABASES
                await cur.execute("SHOW DATABASES")
                dbs = await cur.fetchall()
                print(f"  [OK] SHOW DATABASES: {[list(r.values())[0] for r in dbs]}")

                # Test 3: Count runtime_mysql_servers
                try:
                    await cur.execute("SELECT COUNT(*) AS cnt FROM main.runtime_mysql_servers")
                    row = await cur.fetchone()
                    print(f"  [OK] runtime_mysql_servers count: {row['cnt'] if row else 0}")
                except Exception as e:
                    print(f"  [ERR] runtime_mysql_servers: {e}")

                # Test 4: Count runtime_mysql_users
                try:
                    await cur.execute("SELECT COUNT(*) AS cnt FROM main.runtime_mysql_users")
                    row = await cur.fetchone()
                    print(f"  [OK] runtime_mysql_users count: {row['cnt'] if row else 0}")
                except Exception as e:
                    print(f"  [ERR] runtime_mysql_users: {e}")

                # Test 5: stats_mysql_connection_pool
                try:
                    await cur.execute("SELECT COUNT(*) AS cnt FROM stats_mysql_connection_pool")
                    row = await cur.fetchone()
                    print(f"  [OK] stats_mysql_connection_pool count: {row['cnt'] if row else 0}")
                except Exception as e:
                    print(f"  [ERR] stats_mysql_connection_pool: {e}")

                # Test 6: Check CONFIG MODULES for sync
                try:
                    await cur.execute("SELECT variable_name, variable_value FROM main.runtime_global_variables WHERE variable_name LIKE 'mysql-monitor_%'")
                    vars_rows = await cur.fetchall()
                    for v in vars_rows:
                        print(f"  [INFO] {v['variable_name']} = {v['variable_value']}")
                except Exception as e:
                    print(f"  [ERR] monitor variables: {e}")

                # Test 7: Check if mysql_servers (memory) exists and is populated
                try:
                    await cur.execute("SELECT COUNT(*) AS cnt FROM main.mysql_servers")
                    row = await cur.fetchone()
                    print(f"  [OK] mysql_servers (memory) count: {row['cnt'] if row else 0}")
                except Exception as e:
                    print(f"  [ERR] mysql_servers (memory): {e}")

                # Test 8: PRAGMA table_info for runtime table
                try:
                    await cur.execute("PRAGMA table_info(runtime_mysql_servers)")
                    cols = await cur.fetchall()
                    print(f"  [OK] PRAGMA runtime_mysql_servers columns: {[c['name'] for c in cols]}")
                except Exception as e:
                    print(f"  [ERR] PRAGMA: {e}")

                # Test 9: Sample data from runtime_mysql_servers
                try:
                    await cur.execute("SELECT * FROM main.runtime_mysql_servers LIMIT 5")
                    sample = await cur.fetchall()
                    if sample:
                        print(f"  [OK] runtime_mysql_servers sample ({len(sample)} rows):")
                        for s in sample:
                            print(f"       {s}")
                    else:
                        print(f"  [WARN] runtime_mysql_servers is empty")
                except Exception as e:
                    print(f"  [ERR] sample data: {e}")

            conn.close()
            print(f"\n  charset='{charset}' tests passed. Using this charset.")
            return charset

        except Exception as e:
            print(f"  [FAIL] charset='{charset}': {type(e).__name__}: {e}")
            continue

    print("\n[FAIL] All charset attempts failed.")
    return None


def main():
    parser = argparse.ArgumentParser(description="ProxySQL connection diagnostic")
    parser.add_argument("--host", default="168.107.52.206")
    parser.add_argument("--port", type=int, default=46032)
    parser.add_argument("--user", default="jiangxh")
    parser.add_argument("--password", default="jiang2124")
    args = parser.parse_args()

    print(f"Target: {args.user}@{args.host}:{args.port}")
    result = asyncio.run(test_connection(args.host, args.port, args.user, args.password))

    if result:
        print(f"\n✓ Connection successful with charset='{result}'")
    else:
        print("\n✗ All connection attempts failed")


if __name__ == "__main__":
    main()

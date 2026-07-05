"""
诊断脚本：排查配置同步"始终未应用"和 runtime 重复用户问题。

用法:
    cd /workspace
    python scripts/diag_sync.py
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.database import get_db
from app.utils.security import decrypt_credential
from app.services.proxysql import ProxySQLService
from app.utils.helpers import row_hash


async def get_credentials():
    """从数据库获取 ProxySQL 连接信息。"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM server_configs")
        rows = await cursor.fetchall()
        if not rows:
            print("❌ 没有找到任何 server_configs")
            return None
        for row in rows:
            config = dict(row)
            password = decrypt_credential(config["admin_password_encrypted"])
            print(f"📡 找到服务器: id={config['id']}, host={config['host']}:{config['port']}, user={config['admin_user']}")
            return config["host"], config["port"], config["admin_user"], password
    finally:
        await db.close()


async def main():
    creds = await get_credentials()
    if not creds:
        return
    host, port, user, password = creds
    svc = ProxySQLService()

    # ─── 1. 测试 mysql_users 三层 ──────────────────────────────
    print("\n" + "=" * 70)
    print("🔍 测试1: mysql_users 三层数据对比")
    print("=" * 70)

    for layer_name, sql in [
        ("MEMORY (main.mysql_users)", "SELECT * FROM main.mysql_users"),
        ("RUNTIME (main.runtime_mysql_users)", "SELECT * FROM main.runtime_mysql_users"),
        ("DISK (disk.mysql_users)", "SELECT * FROM disk.mysql_users"),
    ]:
        try:
            rows = await svc.execute_query(host, port, user, password, sql)
        except Exception as e:
            print(f"  ❌ {layer_name}: {e}")
            continue

        print(f"\n  📊 {layer_name}: {len(rows)} 行")
        if rows:
            print(f"     列: {list(rows[0].keys())}")
        for i, row in enumerate(rows):
            username = row.get('username', row.get('__username', 'N/A'))
            h = row_hash(row)
            print(f"     #{i}: username={username}, active={row.get('active')}, "
                  f"default_hostgroup={row.get('default_hostgroup')}, "
                  f"hash={h[:20]}...")
            if i < 5:
                # Print full row for first few entries
                print(f"       完整行: {json.dumps(row, default=str, indent=14, ensure_ascii=False)}")

    # ─── 2. 检查是否有重复用户 ──────────────────────────────
    print("\n\n" + "=" * 70)
    print("🔍 测试2: 检查各层的重复 username")
    print("=" * 70)

    for layer_name, sql in [
        ("MEMORY", "SELECT username, COUNT(*) as cnt FROM main.mysql_users GROUP BY username HAVING cnt > 1"),
        ("RUNTIME", "SELECT username, COUNT(*) as cnt FROM main.runtime_mysql_users GROUP BY username HAVING cnt > 1"),
        ("DISK", "SELECT username, COUNT(*) as cnt FROM disk.mysql_users GROUP BY username HAVING cnt > 1"),
    ]:
        try:
            rows = await svc.execute_query(host, port, user, password, sql)
        except Exception as e:
            print(f"  ❌ {layer_name}: {e}")
            continue
        if rows:
            print(f"  ⚠️  {layer_name}: 发现 {len(rows)} 个重复用户:")
            for r in rows:
                print(f"      username={r['username']}, count={r['cnt']}")
        else:
            print(f"  ✅ {layer_name}: 无重复")

    # ─── 3. 对比 MEMORY vs RUNTIME 的详细差异 ──────────────
    print("\n\n" + "=" * 70)
    print("🔍 测试3: MEMORY vs RUNTIME mysql_users 逐行差异")
    print("=" * 70)

    mem = await svc.execute_query(host, port, user, password, "SELECT * FROM main.mysql_users")
    run = await svc.execute_query(host, port, user, password, "SELECT * FROM main.runtime_mysql_users")
    disk = await svc.execute_query(host, port, user, password, "SELECT * FROM disk.mysql_users")

    mem_hashes = {row_hash(r): r for r in mem}
    run_hashes = {row_hash(r): r for r in run}
    disk_hashes = {row_hash(r): r for r in disk}

    only_mem = set(mem_hashes.keys()) - set(run_hashes.keys())
    only_run = set(run_hashes.keys()) - set(mem_hashes.keys())
    common = set(mem_hashes.keys()) & set(run_hashes.keys())

    print(f"  MEMORY: {len(mem)} 行 (unique hashes: {len(mem_hashes)})")
    print(f"  RUNTIME: {len(run)} 行 (unique hashes: {len(run_hashes)})")
    print(f"  DISK: {len(disk)} 行 (unique hashes: {len(disk_hashes)})")
    print(f"  通用 (hash相同): {len(common)}")
    print(f"  仅 MEMORY: {len(only_mem)}")
    print(f"  仅 RUNTIME: {len(only_run)}")

    if only_mem:
        print("\n  📝 仅在 MEMORY 中的行:")
        for h in only_mem:
            r = mem_hashes[h]
            print(f"      username={r.get('username')}, active={r.get('active')}, "
                  f"default_hostgroup={r.get('default_hostgroup')}")
            # Check type info
            for k, v in r.items():
                print(f"        {k}: {v!r} (type={type(v).__name__})")

    if only_run:
        print("\n  📝 仅在 RUNTIME 中的行:")
        for h in only_run:
            r = run_hashes[h]
            print(f"      username={r.get('username')}, active={r.get('active')}, "
                  f"default_hostgroup={r.get('default_hostgroup')}")
            for k, v in r.items():
                print(f"        {k}: {v!r} (type={type(v).__name__})")

    # ─── 4. 模拟 row_hash 的类型敏感性测试 ──────────────────
    print("\n\n" + "=" * 70)
    print("🔍 测试4: row_hash 类型敏感性")
    print("=" * 70)

    test_pairs = [
        ({"a": 1}, {"a": "1"}, "int vs str"),
        ({"a": 0}, {"a": "0"}, "int 0 vs str '0'"),
        ({"a": True}, {"a": 1}, "bool True vs int 1"),
        ({"a": True}, {"a": "1"}, "bool True vs str '1'"),
    ]

    for d1, d2, desc in test_pairs:
        h1 = row_hash(d1)
        h2 = row_hash(d2)
        status = "❌ DIFFERENT" if h1 != h2 else "✅ SAME"
        print(f"  {desc}: {status}")
        print(f"      hash1={h1}\n      hash2={h2}")

    # ─── 5. 检查 LOAD TO RUNTIME 是否真的生效 ────────────────
    print("\n\n" + "=" * 70)
    print("🔍 测试5: 执行 LOAD MYSQL USERS TO RUNTIME 并验证")
    print("=" * 70)

    # 先记录当前状态
    before_mem = await svc.execute_query(host, port, user, password, "SELECT username FROM main.mysql_users ORDER BY username")
    before_run = await svc.execute_query(host, port, user, password, "SELECT username FROM main.runtime_mysql_users ORDER BY username")
    print(f"  执行前: MEMORY {len(before_mem)} 行, RUNTIME {len(before_run)} 行")

    # 执行 APPLY
    try:
        result = await svc.execute_admin_command(host, port, user, password, "LOAD MYSQL USERS TO RUNTIME")
        print(f"  命令输出: {result}")
    except Exception as e:
        print(f"  ❌ 命令失败: {e}")

    # 检查后
    import asyncio as _asyncio
    await _asyncio.sleep(1)  # 给 ProxySQL 一点时间
    after_mem = await svc.execute_query(host, port, user, password, "SELECT username FROM main.mysql_users ORDER BY username")
    after_run = await svc.execute_query(host, port, user, password, "SELECT username FROM main.runtime_mysql_users ORDER BY username")
    print(f"  执行后: MEMORY {len(after_mem)} 行, RUNTIME {len(after_run)} 行")

    # 再次对比哈希
    after_mem_full = await svc.execute_query(host, port, user, password, "SELECT * FROM main.mysql_users")
    after_run_full = await svc.execute_query(host, port, user, password, "SELECT * FROM main.runtime_mysql_users")
    
    after_mem_h = {row_hash(r) for r in after_mem_full}
    after_run_h = {row_hash(r) for r in after_run_full}

    only_mem2 = after_mem_h - after_run_h
    only_run2 = after_run_h - after_mem_h
    
    if only_mem2 or only_run2:
        print(f"\n  ⚠️  执行 LOAD TO RUNTIME 后仍有差异!")
        print(f"    仅 MEMORY: {len(only_mem2)}, 仅 RUNTIME: {len(only_run2)}")
        print(f"    这说明 row_hash 存在类型敏感性问题，而非真正的配置差异。")
        
        if only_mem2:
            print("    MEMORY 中有但 RUNTIME 没有的列差异:")
            for h in list(only_mem2)[:3]:
                row = next((r for r in after_mem_full if row_hash(r) == h), None)
                if row:
                    for k, v in sorted(row.items()):
                        print(f"      {k}: {v!r} ({type(v).__name__})")
    else:
        print("  ✅ LOAD TO RUNTIME 后 MEMORY 和 RUNTIME 完全一致!")

    await svc.close_all_pools()


if __name__ == "__main__":
    asyncio.run(main())

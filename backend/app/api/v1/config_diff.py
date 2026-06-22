"""Configuration diff API endpoints.

Compares Disk / Memory / Runtime layers of ProxySQL configuration tables
and returns row-level differences (Git-style +/~/- indicators).
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from app.database import get_db
from app.middleware import get_current_user
from app.services.proxysql import proxysql_service
from app.utils.db_helpers import get_proxysql_credentials
from app.utils.helpers import row_hash

router = APIRouter()


# Table prefixes that participate in config sync
_SYNC_TABLE_PREFIXES = [
    "mysql_", "pgsql_", "admin_", "proxysql_",
    "mysql_galera_", "mysql_group_replication_",
    "mysql_replication_", "scheduler", "restapi",
]


@router.get("/{server_id}")
async def get_config_diff(
    server_id: str,
    table: Optional[str] = Query(None, description="Specific table to diff (default: all)"),
    user=Depends(get_current_user),
):
    """Get configuration differences across Disk / Memory / Runtime layers.

    For each config table, returns:
    - Memory rows count
    - Runtime rows count
    - Rows only in Memory (not yet applied)
    - Rows only in Runtime (removed from Memory but still running)
    - Rows that differ (modified)
    """
    host, port, admin_user, password = await get_proxysql_credentials(server_id)

    # Determine which tables to diff
    if table:
        tables_to_diff = [table]
    else:
        rows = await proxysql_service.execute_query(
            host, port, admin_user, password, "SHOW TABLES FROM main"
        )
        # ProxySQL returns column "tables" (SELECT name AS tables FROM sqlite_master).
        all_names = [r.get("tables") or r.get("name") or list(r.values())[0] for r in rows]
        tables_to_diff = [
            n for n in all_names
            if any(n.startswith(p) for p in _SYNC_TABLE_PREFIXES)
            and not n.startswith("runtime_")
            and not n.startswith("disk.")
        ]

    results = []
    for tbl in tables_to_diff:
        try:
            memory_rows = await proxysql_service.execute_query(
                host, port, admin_user, password, f"SELECT * FROM main.{tbl}"
            )
        except Exception:
            memory_rows = []

        try:
            runtime_rows = await proxysql_service.execute_query(
                host, port, admin_user, password, f"SELECT * FROM main.runtime_{tbl}"
            )
        except Exception:
            runtime_rows = []

        # Build hash sets for comparison
        mem_hashes = {row_hash(r): r for r in memory_rows}
        run_hashes = {row_hash(r): r for r in runtime_rows}

        only_memory_keys = set(mem_hashes.keys()) - set(run_hashes.keys())
        only_runtime_keys = set(run_hashes.keys()) - set(mem_hashes.keys())
        common_keys = set(mem_hashes.keys()) & set(run_hashes.keys())

        has_diff = bool(only_memory_keys or only_runtime_keys)

        results.append({
            "table": tbl,
            "in_sync": not has_diff,
            "memory_rows": len(memory_rows),
            "runtime_rows": len(runtime_rows),
            "only_in_memory": len(only_memory_keys),
            "only_in_runtime": len(only_runtime_keys),
            "diff": {
                "added": [mem_hashes[k] for k in only_memory_keys] if has_diff else [],
                "removed": [run_hashes[k] for k in only_runtime_keys] if has_diff else [],
                "unchanged": len(common_keys),
            } if has_diff else None,
        })

    return {
        "server_id": server_id,
        "tables": results,
        "total_tables": len(results),
        "total_out_of_sync": sum(1 for r in results if not r["in_sync"]),
    }

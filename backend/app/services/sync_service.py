"""ProxySQL three-layer configuration sync service.

DISK <-- SAVE -- MEMORY -- APPLY --> RUNTIME
       -- LOAD -->        <-- DISCARD --
"""
from enum import Enum
from typing import Optional

from app.services.proxysql import proxysql_service
from app.utils.helpers import row_hash


class SyncAction(str, Enum):
    APPLY = "apply"       # MEMORY -> RUNTIME
    SAVE = "save"         # MEMORY -> DISK
    DISCARD = "discard"   # RUNTIME -> MEMORY
    LOAD = "load"         # DISK -> MEMORY


class SyncService:
    """Manages ProxySQL three-layer configuration synchronization."""

    # Table prefixes that participate in sync
    SYNC_TABLE_PREFIXES = [
        "mysql_", "pgsql_", "admin_", "proxysql_",
        "mysql_galera_", "mysql_group_replication_",
        "mysql_replication_", "scheduler", "restapi",
    ]

    # Module to LOAD/SAVE command mapping
    CONFIG_MODULES = {
        "mysql_servers": "MYSQL SERVERS",
        "mysql_users": "MYSQL USERS",
        "mysql_query_rules": "MYSQL QUERY RULES",
        "mysql_variables": "MYSQL VARIABLES",
        "admin_variables": "ADMIN VARIABLES",
        "pgsql_servers": "PGSQL SERVERS",
        "pgsql_users": "PGSQL USERS",
        "pgsql_query_rules": "PGSQL QUERY RULES",
        "pgsql_variables": "PGSQL VARIABLES",
        "proxysql_servers": "PROXYSQL SERVERS",
        "scheduler": "SCHEDULER",
    }

    async def get_sync_status(
        self,
        host: str, port: int, user: str, password: str,
    ) -> dict:
        """Get sync status for all config tables.

        Compares three layers:
        - MEMORY (main): Working configuration in memory
        - RUNTIME (runtime_*): Currently active configuration
        - DISK (disk.*): Persisted configuration on disk

        Status indicators:
        - has_unapplied: MEMORY differs from RUNTIME (needs LOAD to apply)
        - has_unsaved: MEMORY differs from DISK (needs SAVE to persist)
        """
        rows = await proxysql_service.execute_query(
            host, port, user, password, "SHOW TABLES FROM main"
        )
        # ProxySQL returns column "tables" (SELECT name AS tables FROM sqlite_master).
        all_names = [r.get("tables") or r.get("name") or list(r.values())[0] for r in rows]
        table_names = [
            n for n in all_names
            if any(n.startswith(p) for p in self.SYNC_TABLE_PREFIXES)
            and not n.startswith("runtime_")
        ]

        results = []
        for table in table_names:
            memory_rows = await proxysql_service.execute_query(
                host, port, user, password, f"SELECT * FROM main.{table}"
            )
            try:
                runtime_rows = await proxysql_service.execute_query(
                    host, port, user, password, f"SELECT * FROM main.runtime_{table}"
                )
            except Exception:
                runtime_rows = []

            # Check DISK layer for unsaved changes
            disk_rows = []
            try:
                disk_rows = await proxysql_service.execute_query(
                    host, port, user, password, f"SELECT * FROM disk.{table}"
                )
            except Exception:
                # disk table might not exist or be accessible
                disk_rows = []

            # Compute hashes for comparison
            mem_hashes = {row_hash(r) for r in memory_rows}
            run_hashes = {row_hash(r) for r in runtime_rows}
            disk_hashes = {row_hash(r) for r in disk_rows}

            # has_unapplied: MEMORY != RUNTIME
            has_unapplied = mem_hashes != run_hashes
            # has_unsaved: MEMORY != DISK
            has_unsaved = mem_hashes != disk_hashes if disk_rows else False

            only_memory = len(mem_hashes - run_hashes)
            only_runtime = len(run_hashes - mem_hashes)

            results.append({
                "table": table,
                "has_unapplied": has_unapplied,
                "has_unsaved": has_unsaved,
                "memory_rows": len(memory_rows),
                "runtime_rows": len(runtime_rows),
                "disk_rows": len(disk_rows),
                "diff": {
                    "only_memory": only_memory,
                    "only_runtime": only_runtime,
                } if has_unapplied else None,
                "unsaved_diff": {
                    "disk_differs": has_unsaved,
                    "disk_rows": len(disk_rows),
                } if has_unsaved else None,
            })

        return {
            "tables": results,
            "total_unapplied": sum(1 for r in results if r["has_unapplied"]),
            "total_unsaved": sum(1 for r in results if r["has_unsaved"]),
        }

    async def sync_action(
        self,
        host: str, port: int, user: str, password: str,
        action: SyncAction,
        tables: Optional[list[str]] = None,
    ) -> dict:
        """Execute a sync action on specified tables."""
        sql_templates = {
            SyncAction.APPLY: "LOAD {module} TO RUNTIME",
            SyncAction.SAVE: "SAVE {module} TO DISK",
            SyncAction.DISCARD: "LOAD {module} FROM RUNTIME",
            SyncAction.LOAD: "LOAD {module} FROM DISK",
        }

        if tables is None:
            rows = await proxysql_service.execute_query(
                host, port, user, password, "SHOW TABLES FROM main"
            )
            # ProxySQL returns column "tables" (SELECT name AS tables FROM sqlite_master).
            all_names = [r.get("tables") or r.get("name") or list(r.values())[0] for r in rows]
            tables = [
                n for n in all_names
                if any(n.startswith(p) for p in self.SYNC_TABLE_PREFIXES)
                and not n.startswith("runtime_")
            ]

        results = []
        for table in tables:
            # Map table name to module name for LOAD/SAVE commands
            module = self.CONFIG_MODULES.get(table)
            if module is None:
                # Try without _ prefix variants
                for prefix in ["mysql_", "pgsql_", "admin_"]:
                    if table.startswith(prefix):
                        base = table[len(prefix):]
                        if base in self.CONFIG_MODULES:
                            module = self.CONFIG_MODULES[base]
                            break

            if module is None:
                results.append({"table": table, "success": False, "error": f"Unknown module for table: {table}"})
                continue

            sql = sql_templates[action].format(module=module)
            try:
                output = await proxysql_service.execute_admin_command(
                    host, port, user, password, sql
                )
                results.append({"table": table, "success": True, "output": output})
            except Exception as e:
                results.append({"table": table, "success": False, "error": str(e)})

        return {
            "action": action.value,
            "results": results,
            "total": len(results),
            "succeeded": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
        }


sync_service = SyncService()

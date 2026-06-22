"""SQL query engine with multi-target support."""
import re
import time
from typing import Optional

from app.services.proxysql import proxysql_service


class QueryTarget:
    ADMIN = "admin"
    MYSQL_PROXY = "mysql"
    PGSQL_PROXY = "pgsql"


class QueryEngine:
    """Multi-target SQL query engine."""

    ALLOWED_ADMIN_COMMANDS = re.compile(
        r'^\s*(LOAD|SAVE|SELECT\s+CONFIG)\b', re.IGNORECASE
    )

    async def execute(
        self,
        host: str, port: int, user: str, password: str,
        sql: str,
        target: str = QueryTarget.ADMIN,
        database: Optional[str] = None,
    ) -> dict:
        """Execute SQL query against the specified target."""
        if target == QueryTarget.ADMIN:
            return await self._execute_admin(host, port, user, password, sql)
        else:
            raise ValueError(f"Unsupported query target: {target}")

    async def _execute_admin(
        self, host: str, port: int, user: str, password: str, sql: str
    ) -> dict:
        """Execute SQL on the admin interface."""
        start = time.time()
        is_select = bool(re.search(r'^\s*SELECT\b', sql, re.IGNORECASE))

        if is_select:
            rows = await proxysql_service.execute_query(host, port, user, password, sql)
            elapsed = time.time() - start
            return {
                "type": "select",
                "rows": rows,
                "row_count": len(rows),
                "elapsed_ms": round(elapsed * 1000, 2),
            }
        else:
            # Check if it's a LOAD/SAVE command
            if self.ALLOWED_ADMIN_COMMANDS.match(sql):
                output = await proxysql_service.execute_admin_command(
                    host, port, user, password, sql
                )
                elapsed = time.time() - start
                return {
                    "type": "admin_command",
                    "output": output,
                    "elapsed_ms": round(elapsed * 1000, 2),
                }

            affected = await proxysql_service.execute_modify(host, port, user, password, sql)
            elapsed = time.time() - start
            return {
                "type": "modify",
                "affected_rows": affected,
                "elapsed_ms": round(elapsed * 1000, 2),
            }

    async def get_schema(
        self, host: str, port: int, user: str, password: str, database: str = "main"
    ) -> dict:
        """Get database schema information."""
        from app.utils.helpers import quote_ident
        try:
            safe_db = quote_ident(database)
        except ValueError as e:
            raise ValueError(f"Invalid database name: {e}")

        rows = await proxysql_service.execute_query(
            host, port, user, password, f"SHOW TABLES FROM {safe_db}"
        )

        schema = {"database": database, "tables": []}
        for table_info in rows:
            # ProxySQL returns column "tables" (SELECT name AS tables FROM sqlite_master).
            table_name = table_info.get("tables") or table_info.get("name") or list(table_info.values())[0]
            try:
                safe_table = quote_ident(table_name)
                columns = await proxysql_service.execute_query(
                    host, port, user, password,
                    f"PRAGMA table_info({safe_table})"
                )
                schema["tables"].append({
                    "name": table_name,
                    "columns": [dict(c) for c in columns],
                })
            except Exception:
                schema["tables"].append({
                    "name": table_name,
                    "columns": [],
                })

        return schema


query_engine = QueryEngine()

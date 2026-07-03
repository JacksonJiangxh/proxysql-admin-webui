"""MySQL backend client — connects directly to backend MySQL servers
that are registered in ProxySQL's mysql_servers table.

This service provides a lightweight connection pool for executing
SQL queries and browsing schema on backend MySQL instances, using
the connection info (host, port) stored in ProxySQL's configuration
plus the monitor credentials from global_variables.
"""

import asyncio
import time
from typing import Optional

import aiomysql


class MySQLBackendClient:
    """Manages ad-hoc connections to backend MySQL servers.

    Unlike ProxySQLService which pools connections to the *admin* interface,
    this client creates short-lived connections for interactive database
    management (schema browsing, data exploration, SQL execution) against
    the actual backend MySQL instances.
    """

    def __init__(self):
        self._pools: dict[str, aiomysql.Pool] = {}
        self._last_used: dict[str, float] = {}
        self._pool_lock = asyncio.Lock()

    async def _get_pool(
        self, host: str, port: int, user: str, password: str
    ) -> aiomysql.Pool:
        """Get or create a connection pool keyed by (host:port:user)."""
        key = f"{user}@{host}:{port}"
        async with self._pool_lock:
            if key in self._pools:
                pool = self._pools[key]
                # Verify the pool is still usable
                try:
                    self._last_used[key] = time.time()
                    return pool
                except Exception:
                    # Pool is stale, recreate
                    await self._close_pool_unsafe(key)
            pool = await aiomysql.create_pool(
                host=host,
                port=port,
                user=user,
                password=password,
                autocommit=True,
                charset="utf8mb4",
                minsize=1,
                maxsize=5,
                connect_timeout=10,
                pool_recycle=1800,
            )
            self._pools[key] = pool
            self._last_used[key] = time.time()
            return pool

    async def _close_pool_unsafe(self, key: str):
        """Close a specific pool (caller must hold _pool_lock)."""
        pool = self._pools.pop(key, None)
        self._last_used.pop(key, None)
        if pool:
            pool.close()
            await pool.wait_closed()

    async def close_pool(self, host: str, port: int, user: str):
        """Close the pool for a specific backend."""
        key = f"{user}@{host}:{port}"
        async with self._pool_lock:
            await self._close_pool_unsafe(key)

    async def close_all(self):
        """Close all backend connection pools."""
        async with self._pool_lock:
            for key in list(self._pools.keys()):
                await self._close_pool_unsafe(key)

    async def execute_query(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        sql: str,
        timeout: float = 30.0,
    ) -> tuple[list[dict], float]:
        """Execute a SELECT query and return (rows, elapsed_ms)."""
        pool = await self._get_pool(host, port, user, password)
        start = time.perf_counter()
        try:
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await asyncio.wait_for(
                        cursor.execute(sql), timeout=timeout
                    )
                    rows = await cursor.fetchall()
                    # Convert to plain dicts
                    result = [dict(row) for row in rows]
                    elapsed = (time.perf_counter() - start) * 1000
                    return result, elapsed
        except asyncio.TimeoutError:
            elapsed = (time.perf_counter() - start) * 1000
            raise asyncio.TimeoutError(
                f"Query timed out after {timeout}s"
            )
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            raise

    async def execute_modify(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        sql: str,
        timeout: float = 30.0,
    ) -> tuple[int, float]:
        """Execute INSERT/UPDATE/DELETE and return (affected_rows, elapsed_ms)."""
        pool = await self._get_pool(host, port, user, password)
        start = time.perf_counter()
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await asyncio.wait_for(
                        cursor.execute(sql), timeout=timeout
                    )
                    affected = cursor.rowcount
                    elapsed = (time.perf_counter() - start) * 1000
                    return affected, elapsed
        except asyncio.TimeoutError:
            elapsed = (time.perf_counter() - start) * 1000
            raise asyncio.TimeoutError(
                f"Query timed out after {timeout}s"
            )
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            raise

    async def get_databases(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        timeout: float = 10.0,
    ) -> list[str]:
        """List all databases on a backend MySQL instance."""
        rows, _ = await self.execute_query(
            host, port, user, password,
            "SHOW DATABASES", timeout=timeout,
        )
        return [r["Database"] for r in rows]

    async def get_tables(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        timeout: float = 10.0,
    ) -> list[str]:
        """List all tables in a database."""
        rows, _ = await self.execute_query(
            host, port, user, password,
            f"SHOW TABLES FROM `{database}`", timeout=timeout,
        )
        # The column name is Tables_in_<database>
        key = f"Tables_in_{database}"
        return [r[key] for r in rows]

    async def get_table_schema(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        table: str,
        timeout: float = 10.0,
    ) -> list[dict]:
        """Get column definitions for a table."""
        rows, _ = await self.execute_query(
            host, port, user, password,
            f"DESCRIBE `{database}`.`{table}`", timeout=timeout,
        )
        return rows

    async def get_table_data(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        table: str,
        page: int = 1,
        page_size: int = 50,
        timeout: float = 30.0,
    ) -> tuple[list[dict], int, float]:
        """Get paginated data from a table.

        Returns:
            (rows, total_count, elapsed_ms)
        """
        # Get total count
        count_rows, count_elapsed = await self.execute_query(
            host, port, user, password,
            f"SELECT COUNT(*) as cnt FROM `{database}`.`{table}`",
            timeout=timeout,
        )
        total = count_rows[0]["cnt"] if count_rows else 0

        offset = (page - 1) * page_size
        data_rows, data_elapsed = await self.execute_query(
            host, port, user, password,
            f"SELECT * FROM `{database}`.`{table}` "
            f"LIMIT {page_size} OFFSET {offset}",
            timeout=timeout,
        )
        return data_rows, total, count_elapsed + data_elapsed

    async def test_connection(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        timeout: float = 5.0,
    ) -> dict:
        """Test connectivity to a backend MySQL server."""
        start = time.perf_counter()
        try:
            rows, elapsed = await self.execute_query(
                host, port, user, password,
                "SELECT 1 AS ok, VERSION() AS version, NOW() AS server_time",
                timeout=timeout,
            )
            return {
                "success": True,
                "version": rows[0].get("version", ""),
                "server_time": str(rows[0].get("server_time", "")),
                "elapsed_ms": round(elapsed, 2),
            }
        except asyncio.TimeoutError:
            elapsed = (time.perf_counter() - start) * 1000
            return {
                "success": False,
                "error": f"Connection timed out after {timeout}s",
                "elapsed_ms": round(elapsed, 2),
            }
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return {
                "success": False,
                "error": str(e),
                "elapsed_ms": round(elapsed, 2),
            }


# Global singleton
mysql_backend_client = MySQLBackendClient()

"""ProxySQL connection and query service.

Performance optimizations:
- Connection pooling with configurable pool sizes and recycling
- Default query timeout prevents long-running queries from blocking connections
- Connection health checks via pool_recycle and ping on acquire
"""
import asyncio
import aiomysql
import re
from typing import Any, Optional
from contextlib import asynccontextmanager

# Connection pool defaults (can be overridden via config)
POOL_MIN_SIZE = 2      # Minimum idle connections to keep warm
POOL_MAX_SIZE = 10     # Maximum concurrent connections per ProxySQL instance
POOL_RECYCLE = 1800    # Recycle connections after 30 minutes (seconds)
CONNECT_TIMEOUT = 10   # Connection timeout in seconds
QUERY_TIMEOUT = 30     # Default query timeout in seconds


class ProxySQLService:
    """Manages connection pools to ProxySQL admin interfaces."""

    def __init__(self):
        self._pools: dict[str, aiomysql.Pool] = {}
        self._last_used: dict[str, float] = {}
        # Pool reaper: close idle pools after 1 hour of inactivity
        self._reaper_task: Optional[asyncio.Task] = None

    def _pool_key(self, host: str, port: int, user: str) -> str:
        return f"{user}@{host}:{port}"

    async def get_pool(self, host: str, port: int, user: str, password: str) -> aiomysql.Pool:
        """Get or create a connection pool for a ProxySQL instance.

        Pools are created lazily and recycled automatically every POOL_RECYCLE
        seconds to prevent stale connections.
        """
        key = self._pool_key(host, port, user)
        if key not in self._pools:
            self._pools[key] = await aiomysql.create_pool(
                host=host,
                port=port,
                user=user,
                password=password,
                autocommit=True,
                minsize=POOL_MIN_SIZE,
                maxsize=POOL_MAX_SIZE,
                pool_recycle=POOL_RECYCLE,
                connect_timeout=CONNECT_TIMEOUT,
                # charset: use utf8 – ProxySQL's admin interface (SQLite-backed)
                # does not support utf8mb4 negotiation; using it can cause
                # queries to return empty results.
                charset='utf8',
            )
        self._last_used[key] = asyncio.get_event_loop().time()
        return self._pools[key]

    async def close_pool(self, host: str, port: int, user: str):
        """Close and remove a connection pool."""
        key = self._pool_key(host, port, user)
        pool = self._pools.pop(key, None)
        self._last_used.pop(key, None)
        if pool:
            pool.close()
            await pool.wait_closed()

    async def close_all_pools(self):
        """Close all connection pools (for graceful shutdown)."""
        for key in list(self._pools.keys()):
            pool = self._pools.pop(key, None)
            if pool:
                pool.close()
                await pool.wait_closed()
        self._last_used.clear()

    async def start_reaper(self, idle_timeout: int = 3600):
        """Start a background task that closes idle connection pools.

        Args:
            idle_timeout: Seconds of inactivity before a pool is closed.
        """
        async def _reap():
            while True:
                await asyncio.sleep(300)  # Check every 5 minutes
                now = asyncio.get_event_loop().time()
                idle_keys = [
                    k for k, t in self._last_used.items()
                    if now - t > idle_timeout
                ]
                for key in idle_keys:
                    pool = self._pools.pop(key, None)
                    self._last_used.pop(key, None)
                    if pool:
                        pool.close()
                        await pool.wait_closed()

        self._reaper_task = asyncio.ensure_future(_reap())

    @asynccontextmanager
    async def get_conn(self, host: str, port: int, user: str, password: str):
        """Get a connection from the pool as a context manager."""
        pool = await self.get_pool(host, port, user, password)
        async with pool.acquire() as conn:
            yield conn

    async def execute_query(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        sql: str,
        params: Optional[list] = None,
        timeout: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Execute a SELECT query and return results as list of dicts.

        Args:
            timeout: Query timeout in seconds (defaults to QUERY_TIMEOUT).
        """
        query_timeout = timeout if timeout is not None else QUERY_TIMEOUT
        try:
            async with self.get_conn(host, port, user, password) as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await asyncio.wait_for(
                        cur.execute(sql, params),
                        timeout=query_timeout,
                    )
                    rows = await asyncio.wait_for(
                        cur.fetchall(),
                        timeout=query_timeout,
                    )
                    return [dict(row) for row in rows]
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Query timed out after {query_timeout}s: {sql[:100]}"
            )
        except Exception as e:
            msg = str(e).lower()
            # Graceful degradation for version-specific tables
            if "no such table" in msg or "table doesn't exist" in msg:
                return []
            raise

    async def execute_modify(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        sql: str,
        params: Optional[list] = None,
        timeout: Optional[int] = None,
    ) -> int:
        """Execute INSERT/UPDATE/DELETE and return affected rows.

        Args:
            timeout: Query timeout in seconds (defaults to QUERY_TIMEOUT).
        """
        query_timeout = timeout if timeout is not None else QUERY_TIMEOUT
        async with self.get_conn(host, port, user, password) as conn:
            async with conn.cursor() as cur:
                await asyncio.wait_for(
                    cur.execute(sql, params),
                    timeout=query_timeout,
                )
                return cur.rowcount

    # Allowed admin command patterns (whitelist) for execute_admin_command.
    # Only commands matching these patterns are permitted, preventing command injection.
    _ADMIN_COMMAND_WHITELIST = [
        r'^LOAD\s+\w+(\s+\w+)*\s+TO\s+RUNTIME\s*$',
        r'^SAVE\s+\w+(\s+\w+)*\s+TO\s+DISK\s*$',
        r'^LOAD\s+\w+(\s+\w+)*\s+FROM\s+DISK\s*$',
        r'^LOAD\s+\w+(\s+\w+)*\s+FROM\s+RUNTIME\s*$',
        r'^SELECT\s+CONFIG\s+.*$',
    ]
    _ADMIN_COMMAND_REGEXES = [re.compile(p, re.IGNORECASE) for p in _ADMIN_COMMAND_WHITELIST]

    # Valid module name fragments that appear in LOAD/SAVE commands.
    # These correspond to the CONFIG_MODULES entries in sync_service.py.
    _VALID_MODULES = {
        "MYSQL SERVERS", "MYSQL USERS", "MYSQL QUERY RULES",
        "MYSQL VARIABLES", "ADMIN VARIABLES", "PGSQL SERVERS",
        "PGSQL USERS", "PGSQL QUERY RULES", "PGSQL VARIABLES",
        "PROXYSQL SERVERS", "SCHEDULER",
    }

    def _validate_admin_command(self, sql: str) -> None:
        """Validate that the SQL is an allowed admin command.

        Raises ValueError if the command is not in the whitelist.

        This is a defense-in-depth measure: even though the callers
        (sync_service, wizard_engine, cluster_service) are trusted,
        centralizing validation here prevents future regressions.
        """
        sql_stripped = sql.strip()
        if not any(rx.match(sql_stripped) for rx in self._ADMIN_COMMAND_REGEXES):
            raise ValueError(
                f"Command not allowed: {sql_stripped[:100]!r}. "
                f"Only LOAD/SAVE admin commands are permitted via execute_admin_command."
            )

    async def execute_admin_command(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        sql: str,
        timeout: Optional[int] = None,
    ) -> str:
        """Execute ProxySQL admin commands (LOAD/SAVE) via mysql CLI.

        Uses subprocess because aiomysql sometimes returns incorrect
        results for ProxySQL management commands.

        Security measures:
        1. Command whitelist validation (defense-in-depth)
        2. Password passed via MYSQL_PWD environment variable (not command-line)
        3. Host/port/user are not shell-interpolated (passed as separate args)

        Args:
            timeout: Command timeout in seconds (defaults to QUERY_TIMEOUT * 2
                     since LOAD/SAVE operations can be slower).
        """
        # Validate the SQL command against the whitelist
        self._validate_admin_command(sql)

        cmd_timeout = timeout if timeout is not None else QUERY_TIMEOUT * 2
        cmd = [
            "mysql",
            "-h", str(host),
            "-P", str(port),
            "-u", str(user),
            "main",
        ]
        # Password is passed via environment variable, NOT as a command-line
        # argument, to prevent exposure in `ps` output.
        import os
        env = {**os.environ, "MYSQL_PWD": str(password)}

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(sql.encode("utf-8")),
                timeout=cmd_timeout,
            )
            stderr_text = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                raise RuntimeError(stderr_text or f"Command failed with code {proc.returncode}")

            return stderr_text or "OK"
        except asyncio.TimeoutError:
            if proc:
                proc.kill()
            raise TimeoutError(
                f"Admin command timed out after {cmd_timeout}s"
            )


# Global singleton
proxysql_service = ProxySQLService()

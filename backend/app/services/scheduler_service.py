"""Application-level task scheduler using APScheduler.

Provides:
- Periodic auto-backup for configured ProxySQL servers
- CRON-based schedule management
- Persistent schedule storage in SQLite
"""

from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import get_db


class SchedulerService:
    """Manages scheduled tasks (auto-backup, health checks, etc.)."""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._job_prefix = "proxysql_"
        self._started = False

    async def start(self) -> None:
        """Load saved schedules from DB and start the scheduler."""
        if self._started:
            return

        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, server_id, cron_expression FROM backup_schedules WHERE enabled = 1"
            )
            rows = await cursor.fetchall()
        finally:
            await db.close()

        for row in rows:
            self._add_job(row["id"], row["server_id"], row["cron_expression"])

        self._scheduler.start()
        self._started = True

    async def shutdown(self) -> None:
        """Gracefully shut down the scheduler."""
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False

    async def add_backup_schedule(
        self, server_id: str, cron_expression: str
    ) -> dict:
        """Create a new auto-backup schedule.

        Args:
            server_id: The ProxySQL server UUID.
            cron_expression: CRON string, e.g. "0 3 * * *" (daily at 3am).

        Returns:
            dict with schedule metadata (id, server_id, cron_expression).
        """
        db = await get_db()
        try:
            cursor = await db.execute(
                """INSERT INTO backup_schedules (server_id, cron_expression)
                   VALUES (?, ?)""",
                (server_id, cron_expression),
            )
            await db.commit()
            schedule_id = cursor.lastrowid
            self._add_job(schedule_id, server_id, cron_expression)
        finally:
            await db.close()

        return {
            "id": schedule_id,
            "server_id": server_id,
            "cron_expression": cron_expression,
        }

    async def list_schedules(self) -> list[dict]:
        """List all backup schedules."""
        db = await get_db()
        try:
            cursor = await db.execute(
                """SELECT id, server_id, cron_expression, enabled, created_at
                   FROM backup_schedules ORDER BY created_at DESC"""
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()

    async def remove_schedule(self, schedule_id: int) -> bool:
        """Remove a backup schedule by ID."""
        db = await get_db()
        try:
            cursor = await db.execute(
                "DELETE FROM backup_schedules WHERE id = ?", (schedule_id,)
            )
            await db.commit()
            deleted = cursor.rowcount > 0
        finally:
            await db.close()

        if deleted:
            job_id = f"{self._job_prefix}backup_{schedule_id}"
            if self._scheduler.get_job(job_id):
                self._scheduler.remove_job(job_id)

        return deleted

    def _add_job(self, schedule_id: int, server_id: str, cron_expression: str) -> None:
        """Add a job to the APScheduler instance."""
        job_id = f"{self._job_prefix}backup_{schedule_id}"
        self._scheduler.add_job(
            self._run_backup,
            CronTrigger.from_crontab(cron_expression),
            id=job_id,
            args=[server_id],
            replace_existing=True,
        )

    async def _run_backup(self, server_id: str) -> None:
        """Execute an auto-backup for the given server."""
        import logging
        logger = logging.getLogger(__name__)
        try:
            from app.services.backup_service import backup_service
            from app.utils.db_helpers import get_proxysql_credentials
            host, port, admin_user, password = await get_proxysql_credentials(server_id)
            result = await backup_service.create_backup(
                server_id=server_id,
                user_id=0,  # system
                host=host,
                port=port,
                user=admin_user,
                password=password,
                name=f"Auto-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            )
            logger.info("auto-backup created", extra={"server_id": server_id, "backup_id": result["id"]})
        except Exception as e:
            logger.error("auto-backup failed", extra={"server_id": server_id, "error": str(e)})


scheduler_service = SchedulerService()

"""System settings & audit log API endpoints.

Provides:
- Audit log listing/filtering (from the ``audit_logs`` SQLite table)
- Application settings info (current user, server count, version)
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.middleware import get_current_user, require_role

router = APIRouter()


@router.get("/audit-logs")
async def list_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    action: Optional[str] = None,
    server_id: Optional[str] = None,
    user=Depends(require_role("admin")),
):
    """List audit log entries (admin only)."""
    db = await get_db()
    try:
        conditions = []
        params: list = []
        if action:
            conditions.append("action = ?")
            params.append(action)
        if server_id:
            conditions.append("server_id = ?")
            params.append(server_id)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        count_cursor = await db.execute(f"SELECT COUNT(*) as total FROM audit_logs{where}", params)
        total = (await count_cursor.fetchone())["total"]

        cursor = await db.execute(
            f"""SELECT id, user_id, username, server_id, action, resource,
                       details, ip_address, created_at
                FROM audit_logs{where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            params + [limit, offset],
        )
        rows = await cursor.fetchall()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "logs": [dict(r) for r in rows],
        }
    finally:
        await db.close()


@router.get("/info")
async def get_system_info(user=Depends(get_current_user)):
    """Get system information (version, stats)."""
    db = await get_db()
    try:
        # User count
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM users")
        user_count = (await cursor.fetchone())["cnt"]

        # Server count
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM server_configs")
        server_count = (await cursor.fetchone())["cnt"]

        # Audit log count
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM audit_logs")
        audit_count = (await cursor.fetchone())["cnt"]

        return {
            "version": "1.0.0",
            "user_count": user_count,
            "server_count": server_count,
            "audit_log_count": audit_count,
            "current_user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
            },
        }
    finally:
        await db.close()


@router.delete("/audit-logs")
async def clear_audit_logs(
    before: Optional[str] = None,
    user=Depends(require_role("admin")),
):
    """Clear audit log entries (admin only).

    If ``before`` is provided (ISO datetime), only entries older than that
    timestamp are deleted. Otherwise all entries are cleared.
    """
    db = await get_db()
    try:
        if before:
            cursor = await db.execute(
                "DELETE FROM audit_logs WHERE created_at < ?", (before,)
            )
        else:
            cursor = await db.execute("DELETE FROM audit_logs")
        await db.commit()
        return {"ok": True, "deleted": cursor.rowcount}
    finally:
        await db.close()

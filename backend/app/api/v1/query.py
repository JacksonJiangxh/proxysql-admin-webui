"""Query execution API endpoints."""
from fastapi import APIRouter, HTTPException, Depends

from pydantic import BaseModel
from typing import Optional

from app.middleware import get_current_user, require_role
from app.services.query_engine import query_engine
from app.utils.db_helpers import get_proxysql_credentials
from app.utils.sql_sanitizer import sanitize_sql

router = APIRouter()


class QueryRequest(BaseModel):
    sql: str
    target: str = "admin"
    database: Optional[str] = None
    limit: int = 100


@router.post("/{server_id}/execute")
async def execute_query(
    server_id: str,
    query: QueryRequest,
    user=Depends(require_role("admin", "operator")),
):
    """Execute a SQL query against the ProxySQL admin interface."""
    # SQL injection hardening: validate and sanitize user-submitted SQL
    is_admin = user["role"] == "admin"
    sanitized_sql, error = sanitize_sql(query.sql, is_admin=is_admin)
    if error:
        raise HTTPException(status_code=400, detail=error)

    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    result = await query_engine.execute(
        host, port, admin_user, password,
        sql=sanitized_sql,
        target=query.target,
        database=query.database,
    )

    # Store query in history
    from app.database import get_db
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO query_history (user_id, server_id, sql_text, target, database_name, execution_time_ms, row_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user["id"], server_id, sanitized_sql, query.target, query.database or "main",
             result.get("elapsed_ms"), result.get("row_count", 0))
        )
        await db.commit()
    finally:
        await db.close()

    # Limit results
    if result.get("type") == "select" and len(result.get("rows", [])) > query.limit:
        result["rows"] = result["rows"][:query.limit]
        result["truncated"] = True

    return result


@router.get("/{server_id}/schema")
async def get_schema(
    server_id: str,
    database: str = "main",
    user=Depends(get_current_user),
):
    """Get database schema."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    return await query_engine.get_schema(host, port, admin_user, password, database)


@router.get("/{server_id}/history")
async def get_query_history(
    server_id: str,
    limit: int = 50,
    user=Depends(get_current_user),
):
    """Get query history for the current user."""
    from app.database import get_db
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, sql_text, target, database_name, execution_time_ms, row_count, created_at
               FROM query_history
               WHERE user_id = ? AND server_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user["id"], server_id, limit)
        )
        rows = await cursor.fetchall()
        return {"history": [dict(r) for r in rows]}
    finally:
        await db.close()


@router.delete("/{server_id}/history")
async def clear_query_history(
    server_id: str,
    user=Depends(get_current_user),
):
    """Clear query history."""
    from app.database import get_db
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM query_history WHERE user_id = ? AND server_id = ?",
            (user["id"], server_id)
        )
        await db.commit()
    finally:
        await db.close()
    return {"ok": True, "message": "Query history cleared"}


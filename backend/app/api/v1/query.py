"""Query execution API endpoints.

Provides SQL execution against ProxySQL admin interface with history tracking,
SQL sanitization, and paginated history search.
""" 
from fastapi import APIRouter, HTTPException, Depends, Query as QueryParam

from pydantic import BaseModel, Field
from typing import Optional

from app.middleware import get_current_user, require_role
from app.schemas.query import (
    QueryResultResponse,
    SchemaResponse,
    QueryHistoryResponse,
)
from app.schemas.response import (
    MessageResponse,
    HTTPError,
    RESPONSE_AUTH,
    RESPONSE_404,
)
from app.services.query_engine import query_engine
from app.utils.db_helpers import get_proxysql_credentials
from app.utils.sql_sanitizer import sanitize_sql

router = APIRouter(tags=["Query"])


class QueryRequest(BaseModel):
    """SQL query execution request."""
    sql: str = Field(
        description="SQL statement to execute.",
        examples=["SELECT * FROM main.mysql_servers"],
    )
    target: str = Field(
        default="admin",
        description="Query target: 'admin' for ProxySQL admin, or runtime name.",
        examples=["admin"],
    )
    database: Optional[str] = Field(
        default=None,
        description="Database context for the query.",
        examples=["main"],
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of rows to return.",
    )


@router.post(
    "/{server_id}/execute",
    response_model=QueryResultResponse,
    responses={
        200: {"description": "Query executed successfully."},
        400: {"description": "SQL validation failed.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Execute SQL query",
    description="Execute a SQL statement against a ProxySQL server's admin interface. "
                "Queries are sanitized for safety before execution.",
)
async def execute_query(
    server_id: str,
    query: QueryRequest,
    user=Depends(require_role("admin", "operator")),
):
    """Execute a SQL query against the ProxySQL admin interface."""
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
        error_msg = result.get("error") if isinstance(result, dict) else None
        await db.execute(
            """INSERT INTO query_history (user_id, server_id, sql_text, target, database_name, execution_time_ms, row_count, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user["id"], server_id, sanitized_sql, query.target, query.database or "main",
             result.get("elapsed_ms"), result.get("row_count", 0), error_msg)
        )
        await db.commit()
    finally:
        await db.close()

    if result.get("type") == "select" and len(result.get("rows", [])) > query.limit:
        result["rows"] = result["rows"][:query.limit]
        result["truncated"] = True

    return result


@router.get(
    "/{server_id}/schema",
    response_model=SchemaResponse,
    responses={**RESPONSE_AUTH},
    summary="Get database schema",
    description="Retrieve table and column metadata from a ProxySQL database.",
)
async def get_schema(
    server_id: str,
    database: str = QueryParam(
        default="main",
        description="Database name (main, disk, monitor, stats).",
    ),
    user=Depends(get_current_user),
):
    """Get database schema."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    return await query_engine.get_schema(host, port, admin_user, password, database)


@router.get(
    "/{server_id}/history",
    response_model=QueryHistoryResponse,
    responses={**RESPONSE_AUTH},
    summary="Get query history",
    description="Retrieve paginated query execution history with optional "
                "search and date-range filters.",
)
async def get_query_history(
    server_id: str,
    limit: int = QueryParam(50, ge=1, le=200, description="Page size."),
    offset: int = QueryParam(0, ge=0, description="Page offset."),
    search: Optional[str] = QueryParam(None, description="Search in SQL text (case-insensitive)."),
    date_from: Optional[str] = QueryParam(None, description="Filter from ISO date, e.g. 2025-01-01."),
    date_to: Optional[str] = QueryParam(None, description="Filter to ISO date, e.g. 2025-12-31."),
    user=Depends(get_current_user),
):
    """Get query history for the current user with search and pagination support.

    - **search**: case-insensitive partial match on sql_text
    - **date_from / date_to**: filter by creation date (inclusive)
    - **limit / offset**: pagination controls
    """
    from app.database import get_db
    db = await get_db()
    try:
        conditions = ["user_id = ?", "server_id = ?"]
        params: list = [user["id"], server_id]

        if search:
            conditions.append("sql_text LIKE ?")
            params.append(f"%{search}%")

        if date_from:
            conditions.append("created_at >= ?")
            params.append(date_from)

        if date_to:
            conditions.append("created_at <= ?")
            params.append(date_to + " 23:59:59")

        where_clause = " AND ".join(conditions)

        count_cursor = await db.execute(
            f"SELECT COUNT(*) FROM query_history WHERE {where_clause}",
            params
        )
        total = (await count_cursor.fetchone())[0]

        cursor = await db.execute(
            f"""SELECT id, sql_text, target, database_name, execution_time_ms, row_count, error, created_at
               FROM query_history
               WHERE {where_clause}
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            params + [limit, offset]
        )
        rows = await cursor.fetchall()
        return {
            "history": [dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    finally:
        await db.close()


@router.delete(
    "/{server_id}/history",
    response_model=MessageResponse,
    responses={**RESPONSE_AUTH},
    summary="Clear query history",
    description="Delete all query history entries for the current user and server.",
)
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
    return {"message": "Query history cleared"}


@router.delete(
    "/{server_id}/history/{history_id}",
    response_model=MessageResponse,
    responses={
        200: {"description": "History entry deleted."},
        404: {"description": "History entry not found.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Delete history entry",
    description="Delete a single query history entry by ID.",
)
async def delete_history_item(
    server_id: str,
    history_id: int,
    user=Depends(get_current_user),
):
    """Delete a single history entry."""
    from app.database import get_db
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM query_history WHERE id = ? AND user_id = ? AND server_id = ?",
            (history_id, user["id"], server_id)
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="History entry not found")
        return {"message": "History entry deleted"}
    finally:
        await db.close()


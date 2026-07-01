"""Response models for query execution API."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class QueryResultResponse(BaseModel):
    """Response from executing a SQL query against ProxySQL admin."""
    type: str = Field(
        description="Query type: 'select', 'modify', or 'error'.",
        examples=["select", "modify"],
    )
    columns: Optional[list[str]] = Field(
        default=None,
        description="Column names (for SELECT queries).",
    )
    rows: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Result rows (for SELECT queries).",
    )
    row_count: Optional[int] = Field(
        default=None,
        description="Number of rows returned or affected.",
    )
    elapsed_ms: Optional[float] = Field(
        default=None,
        description="Query execution time in milliseconds.",
    )
    truncated: Optional[bool] = Field(
        default=None,
        description="True if results were truncated to limit.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if the query failed.",
    )


class SchemaResponse(BaseModel):
    """Database schema information."""
    database: str = Field(description="Database name.")
    tables: list[dict[str, Any]] = Field(
        description="List of table definitions with column metadata.",
    )


class QueryHistoryItem(BaseModel):
    """A single query history entry."""
    id: int = Field(description="History entry ID.")
    sql_text: str = Field(description="Executed SQL text.")
    target: str = Field(default="admin", description="Query target.")
    database_name: Optional[str] = Field(default=None, description="Database context.")
    execution_time_ms: Optional[float] = Field(default=None, description="Execution time in ms.")
    row_count: Optional[int] = Field(default=None, description="Rows returned or affected.")
    error: Optional[str] = Field(default=None, description="Error message if failed.")
    created_at: datetime = Field(description="ISO 8601 execution timestamp.")


class QueryHistoryResponse(BaseModel):
    """Paginated query history."""
    history: list[dict] = Field(description="List of history entries.")
    total: int = Field(description="Total matching entries.")
    limit: int = Field(description="Page size.")
    offset: int = Field(description="Page offset.")

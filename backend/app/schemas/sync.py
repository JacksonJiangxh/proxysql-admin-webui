"""Response models for config sync API."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class TableSyncStatus(BaseModel):
    """Sync status for a single config table."""
    table: str = Field(description="Config table name.")
    in_sync: bool = Field(description="True if Memory matches Runtime.")
    memory_rows: int = Field(description="Rows in Memory layer.")
    runtime_rows: int = Field(description="Rows in Runtime layer.")


class SyncStatusResponse(BaseModel):
    """Full sync status across all config tables."""
    server_id: str = Field(description="ProxySQL server identifier.")
    tables: list[dict[str, Any]] = Field(description="Per-table sync status.")
    total_tables: int = Field(description="Total tables checked.")
    in_sync_count: int = Field(description="Tables fully in sync.")
    out_of_sync_count: int = Field(description="Tables with pending changes.")


class SyncActionResult(BaseModel):
    """Result of a sync action (apply/save/discard/load)."""
    action: str = Field(
        description="Action performed: 'apply', 'save', 'discard', or 'load'.",
        examples=["apply", "save"],
    )
    success: bool = Field(description="Whether the action completed successfully.")
    tables_affected: Optional[int] = Field(
        default=None,
        description="Number of tables affected.",
    )
    message: Optional[str] = Field(
        default=None,
        description="Human-readable result message.",
    )
    details: Optional[dict[str, Any]] = Field(
        default=None,
        description="Detailed per-table results.",
    )

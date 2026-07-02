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
    total_unapplied: int = Field(default=0, description="Tables with unapplied changes.")
    total_unsaved: int = Field(default=0, description="Tables with unsaved changes.")


class SyncActionResult(BaseModel):
    """Result of a sync action (apply/save/discard/load)."""
    action: str = Field(
        description="Action performed: 'apply', 'save', 'discard', or 'load'.",
        examples=["apply", "save"],
    )
    results: list[dict[str, Any]] = Field(default_factory=list, description="Per-table results.")
    total: int = Field(default=0, description="Total tables processed.")
    succeeded: int = Field(default=0, description="Tables successfully processed.")
    failed: int = Field(default=0, description="Tables that failed.")

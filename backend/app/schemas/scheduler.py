"""Response models for scheduler API endpoints."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ScheduleItem(BaseModel):
    """An auto-backup schedule entry."""
    id: int = Field(description="Schedule ID.")
    server_id: str = Field(description="Target ProxySQL server.")
    cron_expression: str = Field(
        description="CRON expression (minute hour day month weekday).",
        examples=["0 3 * * *"],
    )
    enabled: bool = Field(default=True, description="Whether the schedule is active.")
    last_run: Optional[datetime] = Field(
        default=None,
        description="ISO 8601 timestamp of last execution.",
    )
    next_run: Optional[datetime] = Field(
        default=None,
        description="ISO 8601 timestamp of next scheduled execution.",
    )
    created_at: datetime = Field(description="Creation timestamp.")


class ScheduleListResponse(BaseModel):
    """List of all auto-backup schedules."""
    schedules: list[ScheduleItem] = Field(description="All configured backup schedules.")


class ScheduleCreateResponse(BaseModel):
    """Response after creating a new schedule."""
    id: int = Field(description="Newly created schedule ID.")
    server_id: str
    cron_expression: str
    message: str = Field(default="Schedule created successfully")

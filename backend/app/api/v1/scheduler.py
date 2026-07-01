"""Scheduler API endpoints for managing auto-backup schedules.

Provides CRUD operations for APScheduler-based auto-backup jobs with CRON support.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.middleware import get_current_user, require_role
from app.schemas.scheduler import (
    ScheduleListResponse,
    ScheduleCreateResponse,
)
from app.schemas.response import (
    MessageResponse,
    HTTPError,
    RESPONSE_AUTH,
)
from app.services.scheduler_service import scheduler_service

router = APIRouter(tags=["Scheduler"])


class CreateScheduleRequest(BaseModel):
    """Request to create a new auto-backup schedule."""
    server_id: str = Field(
        description="Target ProxySQL server to back up.",
        examples=["srv1"],
    )
    cron_expression: str = Field(
        description="CRON expression: minute hour day month weekday.",
        examples=["0 3 * * *"],
        pattern=r"^(\*|[0-5]?\d)\s+(\*|[0-1]?\d|2[0-3])\s+(\*|[1-2]?\d|3[01])\s+(\*|1[0-2]?|[1-9])\s+(\*|[0-6])$",
    )


@router.get(
    "/status",
    response_model=ScheduleListResponse,
    responses={**RESPONSE_AUTH},
    summary="List schedules",
    description="Retrieve all configured auto-backup schedules.",
)
async def get_schedules(user=Depends(get_current_user)):
    """List all auto-backup schedules."""
    schedules = await scheduler_service.list_schedules()
    return {"schedules": schedules}


@router.post(
    "/backup",
    response_model=ScheduleCreateResponse,
    responses={
        200: {"description": "Schedule created."},
        500: {"description": "Schedule creation failed.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Create backup schedule",
    description="Create an auto-backup schedule for a server. "
                "CRON format: `minute hour day month weekday`. "
                "Example: `0 3 * * *` = daily at 3:00 AM.",
)
async def create_backup_schedule(
    req: CreateScheduleRequest,
    user=Depends(require_role("admin")),
):
    """Create an auto-backup schedule for a server.

    cron_expression format: minute hour day month day-of-week
    Example: "0 3 * * *" = daily at 3:00 AM
    """
    try:
        result = await scheduler_service.add_backup_schedule(
            req.server_id,
            req.cron_expression,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/backup/{schedule_id}",
    response_model=MessageResponse,
    responses={
        200: {"description": "Schedule removed."},
        404: {"description": "Schedule not found.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Delete schedule",
    description="Remove an auto-backup schedule. Requires admin role.",
)
async def delete_backup_schedule(
    schedule_id: int,
    user=Depends(require_role("admin")),
):
    """Remove an auto-backup schedule."""
    deleted = await scheduler_service.remove_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"message": "Schedule removed"}

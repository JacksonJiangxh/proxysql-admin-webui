"""Configuration backup and restore API endpoints.

Provides single and batch backup operations for ProxySQL server configurations.
Backups are stored in SQLite and can be downloaded, restored, or deleted.
""" 
import json
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional

from app.middleware import get_current_user
from app.schemas.backup import (
    BackupListResponse,
    BackupCreateResponse,
    BackupRestoreResponse,
    BatchDeleteResponse,
    BatchCreateResponse,
    BatchCreateResult,
)
from app.schemas.response import (
    MessageResponse,
    HTTPError,
    RESPONSE_AUTH,
    RESPONSE_STANDARD,
)
from app.services.backup_service import backup_service
from app.utils.db_helpers import get_proxysql_credentials

router = APIRouter(tags=["Backup"])


class CreateBackupRequest(BaseModel):
    """Request to create a new configuration backup."""
    name: Optional[str] = Field(
        default=None,
        description="Human-readable name for the backup.",
        examples=["pre-upgrade-20250101"],
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional description or notes.",
        examples=["Before upgrading to v2.3.0"],
    )


class RestoreRequest(BaseModel):
    """Request to restore configuration from a backup."""
    tables: Optional[list[str]] = Field(
        default=None,
        description="Specific tables to restore. If omitted, all tables are restored.",
        examples=[["mysql_servers", "mysql_users"]],
    )


class BatchDeleteRequest(BaseModel):
    """Request to delete multiple backups at once."""
    backup_ids: list[int] = Field(
        description="List of backup IDs to delete.",
        min_length=1,
        examples=[[1, 2, 3]],
    )


class BatchCreateRequest(BaseModel):
    """Request to create backups for multiple servers simultaneously."""
    server_ids: list[str] = Field(
        description="List of server IDs to back up.",
        min_length=1,
        examples=[["srv1", "srv2"]],
    )
    name_prefix: Optional[str] = Field(
        default=None,
        description="Prefix for backup names (e.g. 'nightly-').",
        examples=["nightly-"],
    )


@router.post(
    "/{server_id}/create",
    response_model=BackupCreateResponse,
    responses={
        200: {"description": "Backup created successfully."},
        500: {"description": "Backup creation failed — ProxySQL unreachable.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Create backup",
    description="Take a configuration snapshot from the selected ProxySQL server. "
                "Requires admin or operator role.",
)
async def create_backup(
    server_id: str,
    req: CreateBackupRequest = CreateBackupRequest(),
    user=Depends(get_current_user),
):
    """Create a configuration backup snapshot from the selected server."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    try:
        result = await backup_service.create_backup(
            server_id=server_id,
            user_id=user["id"],
            host=host,
            port=port,
            user=admin_user,
            password=password,
            name=req.name,
            description=req.description,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


@router.get(
    "/{server_id}/list",
    response_model=BackupListResponse,
    responses={**RESPONSE_AUTH},
    summary="List backups",
    description="Retrieve all backups for the specified server, sorted newest first.",
)
async def list_backups(
    server_id: str,
    user=Depends(get_current_user),
):
    """List all backups for a server."""
    return {"backups": await backup_service.list_backups(server_id)}


@router.get(
    "/{server_id}/{backup_id}/download",
    responses={
        200: {
            "description": "Backup data as downloadable JSON file.",
            "content": {"application/json": {}},
        },
        404: {"description": "Backup not found.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Download backup",
    description="Download a backup's data as a JSON file attachment.",
)
async def download_backup(
    server_id: str,
    backup_id: int,
    user=Depends(get_current_user),
):
    """Download a backup as JSON file."""
    result = await backup_service.download_backup(backup_id)
    if not result:
        raise HTTPException(status_code=404, detail="Backup not found")
    filename, data = result
    return Response(
        content=data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/{server_id}/{backup_id}/restore",
    response_model=BackupRestoreResponse,
    responses={
        200: {"description": "Backup restored successfully."},
        404: {"description": "Backup or server not found.", "model": HTTPError},
        500: {"description": "Restore failed — ProxySQL unreachable.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Restore backup",
    description="Restore ProxySQL configuration from a backup. "
                "Optionally filter which tables to restore.",
)
async def restore_backup(
    server_id: str,
    backup_id: int,
    req: RestoreRequest = RestoreRequest(),
    user=Depends(get_current_user),
):
    """Restore configuration from a backup."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    try:
        result = await backup_service.restore_backup(
            backup_id=backup_id,
            host=host,
            port=port,
            user=admin_user,
            password=password,
            table_filter=req.tables,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")


@router.delete(
    "/{server_id}/{backup_id}",
    response_model=MessageResponse,
    responses={
        200: {"description": "Backup deleted."},
        404: {"description": "Backup not found.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Delete backup",
    description="Permanently delete a single backup.",
)
async def delete_backup(
    server_id: str,
    backup_id: int,
    user=Depends(get_current_user),
):
    """Delete a backup."""
    deleted = await backup_service.delete_backup(backup_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Backup not found")
    return {"message": "Backup deleted"}


@router.post(
    "/batch-delete",
    response_model=BatchDeleteResponse,
    responses={
        200: {"description": "Backups deleted."},
        **RESPONSE_AUTH,
        **{422: {"description": "Validation error — empty or invalid backup_ids.", "model": HTTPError}},
    },
    summary="Batch delete backups",
    description="Delete multiple backups at once by their IDs. Requires admin or operator role.",
)
async def batch_delete_backups(
    req: BatchDeleteRequest,
    user=Depends(get_current_user),
):
    """Delete multiple backups at once."""
    deleted = await backup_service.delete_backups(req.backup_ids)
    return {"ok": True, "deleted_count": deleted}


@router.post(
    "/batch-create",
    response_model=BatchCreateResponse,
    responses={
        200: {"description": "Batch backup operation completed (check per-server results)."},
        **RESPONSE_AUTH,
        **{422: {"description": "Validation error.", "model": HTTPError}},
    },
    summary="Batch create backups",
    description="Create backups for multiple servers in a single request. "
                "Each server's result is reported individually.",
)
async def batch_create_backups(
    req: BatchCreateRequest,
    user=Depends(get_current_user),
):
    """Create backups for multiple servers at once."""
    results = await backup_service.create_backups_for_servers(
        server_ids=req.server_ids,
        user_id=user["id"],
        name_prefix=req.name_prefix,
    )
    succeeded = sum(1 for r in results if r["success"])
    return {
        "ok": True,
        "total": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "results": results,
    }

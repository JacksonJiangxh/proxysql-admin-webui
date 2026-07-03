"""Configuration sync API endpoints.

Manages ProxySQL config lifecycle: check status, apply to runtime,
save to disk, discard changes, load from disk.
"""
from fastapi import APIRouter, Depends, Query

from app.middleware import get_current_user
from app.schemas.sync import SyncStatusResponse, SyncActionResult
from app.schemas.response import RESPONSE_AUTH, RESPONSE_500, HTTPError
from app.services.cache_service import cache_service
from app.services.sync_service import sync_service, SyncAction
from app.utils.db_helpers import get_proxysql_credentials

router = APIRouter(tags=["Config Sync"])


@router.get(
    "/{server_id}/status",
    response_model=SyncStatusResponse,
    responses={**RESPONSE_AUTH},
    summary="Get sync status",
    description="Check which config tables have pending changes "
                "(Memory differs from Runtime).",
)
async def get_sync_status(
    server_id: str,
    user=Depends(get_current_user),
):
    """Get configuration sync status for all tables."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    status = await sync_service.get_sync_status(host, port, admin_user, password)
    return {"server_id": server_id, **status}


@router.post(
    "/{server_id}/apply",
    response_model=SyncActionResult,
    responses={
        200: {"description": "Config applied to runtime."},
        500: {"description": "Apply failed — ProxySQL error.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Apply to runtime",
    description="Apply pending Memory changes to Runtime. "
                "Invalidates config diff cache for this server.",
)
async def apply_config(
    server_id: str,
    tables: list[str] = Query(
        default=None,
        description="Specific tables to apply. If omitted, all changed tables.",
    ),
    user=Depends(get_current_user),
):
    """Apply configuration changes to runtime."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    result = await sync_service.sync_action(
        host, port, admin_user, password, SyncAction.APPLY, tables
    )
    # Invalidate config diff cache
    cache_service.invalidate_config_diff(server_id)
    return result


@router.post(
    "/{server_id}/save",
    response_model=SyncActionResult,
    responses={
        200: {"description": "Config saved to disk."},
        500: {"description": "Save failed — disk error.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Save to disk",
    description="Persist current Runtime config to disk. "
                "Invalidates config diff cache for this server.",
)
async def save_config(
    server_id: str,
    tables: list[str] = Query(
        default=None,
        description="Specific tables to save. If omitted, all tables.",
    ),
    user=Depends(get_current_user),
):
    """Save configuration to disk."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    result = await sync_service.sync_action(
        host, port, admin_user, password, SyncAction.SAVE, tables
    )
    cache_service.invalidate_config_diff(server_id)
    return result


@router.post(
    "/{server_id}/discard",
    response_model=SyncActionResult,
    responses={
        200: {"description": "Changes discarded, reloaded from runtime."},
        500: {"description": "Discard failed.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Discard changes",
    description="Discard pending Memory changes and reload from Runtime. "
                "Invalidates config diff cache for this server.",
)
async def discard_changes(
    server_id: str,
    tables: list[str] = Query(
        default=None,
        description="Specific tables to discard. If omitted, all changed tables.",
    ),
    user=Depends(get_current_user),
):
    """Discard changes and reload from runtime."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    result = await sync_service.sync_action(
        host, port, admin_user, password, SyncAction.DISCARD, tables
    )
    cache_service.invalidate_config_diff(server_id)
    return result


@router.post(
    "/{server_id}/load",
    response_model=SyncActionResult,
    responses={
        200: {"description": "Config loaded from disk."},
        500: {"description": "Load failed.", "model": HTTPError},
        **RESPONSE_AUTH,
    },
    summary="Load from disk",
    description="Load configuration from disk into Memory. "
                "Invalidates config diff cache for this server.",
)
async def load_from_disk(
    server_id: str,
    tables: list[str] = Query(
        default=None,
        description="Specific tables to load. If omitted, all tables.",
    ),
    user=Depends(get_current_user),
):
    """Load configuration from disk."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    result = await sync_service.sync_action(
        host, port, admin_user, password, SyncAction.LOAD, tables
    )
    cache_service.invalidate_config_diff(server_id)
    return result

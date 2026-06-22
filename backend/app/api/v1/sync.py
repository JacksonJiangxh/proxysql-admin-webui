"""Configuration sync API endpoints."""
from fastapi import APIRouter, Depends

from app.middleware import get_current_user, require_role
from app.services.sync_service import sync_service, SyncAction
from app.utils.db_helpers import get_proxysql_credentials

router = APIRouter()


@router.get("/{server_id}/status")
async def get_sync_status(
    server_id: str,
    user=Depends(get_current_user),
):
    """Get configuration sync status for all tables."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    status = await sync_service.get_sync_status(host, port, admin_user, password)
    return {"server_id": server_id, **status}


@router.post("/{server_id}/apply")
async def apply_config(
    server_id: str,
    tables: list[str] = None,
    user=Depends(require_role("admin", "operator")),
):
    """Apply configuration changes to runtime."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    result = await sync_service.sync_action(
        host, port, admin_user, password, SyncAction.APPLY, tables
    )
    return result


@router.post("/{server_id}/save")
async def save_config(
    server_id: str,
    tables: list[str] = None,
    user=Depends(require_role("admin", "operator")),
):
    """Save configuration to disk."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    result = await sync_service.sync_action(
        host, port, admin_user, password, SyncAction.SAVE, tables
    )
    return result


@router.post("/{server_id}/discard")
async def discard_changes(
    server_id: str,
    tables: list[str] = None,
    user=Depends(require_role("admin", "operator")),
):
    """Discard changes and reload from runtime."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    result = await sync_service.sync_action(
        host, port, admin_user, password, SyncAction.DISCARD, tables
    )
    return result


@router.post("/{server_id}/load")
async def load_from_disk(
    server_id: str,
    tables: list[str] = None,
    user=Depends(require_role("admin", "operator")),
):
    """Load configuration from disk."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    result = await sync_service.sync_action(
        host, port, admin_user, password, SyncAction.LOAD, tables
    )
    return result

"""Dashboard monitoring API endpoints.

Provides real-time ProxySQL metrics via REST snapshot and WebSocket push.
""" 
import asyncio
import json
import logging
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query

from app.middleware import get_current_user
from app.schemas.dashboard import DashboardSnapshotResponse
from app.schemas.response import RESPONSE_AUTH
from app.services.cache_service import cache_service
from app.services.dashboard_service import dashboard_service
from app.utils.db_helpers import get_proxysql_credentials
from app.utils.security import decode_token

router = APIRouter(tags=["Dashboard"])
ws_router = APIRouter(tags=["Dashboard WS"])
logger = logging.getLogger(__name__)


@router.get(
    "/{server_id}/snapshot",
    response_model=DashboardSnapshotResponse,
    responses={**RESPONSE_AUTH},
    summary="Get dashboard snapshot",
    description="Retrieve a real-time monitoring snapshot from a ProxySQL server.",
)
async def get_dashboard_snapshot(
    server_id: str,
    digest_limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of query digest entries to return.",
    ),
    user=Depends(get_current_user),
):
    """Get current monitoring snapshot."""
    # Try cache first
    cached = cache_service.get_dashboard_snapshot(server_id, digest_limit)
    if cached is not None:
        return cached

    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    snapshot = await dashboard_service.get_snapshot(
        host, port, admin_user, password, digest_limit
    )
    result = {"server_id": server_id, **snapshot}

    # Store in cache
    cache_service.set_dashboard_snapshot(server_id, digest_limit, result)

    return result


async def _authenticate_ws(websocket: WebSocket) -> dict | None:
    """Validate JWT token for WebSocket connection."""
    token = websocket.query_params.get("token")
    if not token:
        return None

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    return payload


@ws_router.websocket("/{server_id}")
async def dashboard_ws(
    websocket: WebSocket,
    server_id: str,
    interval: int = Query(default=5, ge=1, le=300),
):
    """WebSocket endpoint that pushes dashboard snapshots periodically.

    Query parameters:
        token: JWT access token (required for auth).
        interval: refresh interval in seconds (1-300, default 5).
    """
    user = await _authenticate_ws(websocket)
    if user is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    try:
        while True:
            try:
                host, port, admin_user, password = await get_proxysql_credentials(server_id)
                snapshot = await dashboard_service.get_snapshot(
                    host, port, admin_user, password, digest_limit=10
                )
                await websocket.send_text(json.dumps({
                    "type": "metrics_update",
                    "server_id": server_id,
                    "data": snapshot,
                }))
            except WebSocketDisconnect:
                # Client disconnected during send — exit the outer loop cleanly
                return
            except Exception as e:
                # Surface the error but keep the connection alive so the client
                # can recover once the backend becomes reachable again.
                try:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": str(e),
                    }))
                except WebSocketDisconnect:
                    return
                except RuntimeError:
                    # Connection already closed — stop pushing
                    return
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        return

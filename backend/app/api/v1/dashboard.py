"""Dashboard monitoring API endpoints."""
import asyncio
import json
import logging
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query

from app.middleware import get_current_user
from app.services.dashboard_service import dashboard_service
from app.utils.db_helpers import get_proxysql_credentials
from app.utils.security import decode_token
from app.config import settings

router = APIRouter()
ws_router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{server_id}/snapshot")
async def get_dashboard_snapshot(
    server_id: str,
    digest_limit: int = 10,
    user=Depends(get_current_user),
):
    """Get current monitoring snapshot."""
    host, port, admin_user, password = await get_proxysql_credentials(server_id)
    snapshot = await dashboard_service.get_snapshot(host, port, admin_user, password, digest_limit)
    return {"server_id": server_id, **snapshot}


async def _authenticate_ws(websocket: WebSocket) -> dict | None:
    """Validate JWT token for WebSocket connection.

    Security measures:
    1. Validate JWT token via decode_token (handles expiry, signature)
    2. Verify Origin header to prevent cross-origin attacks
    3. Log connection attempts for audit trail

    Note: Token is passed via query parameter because browsers cannot set
    custom Authorization headers on WebSocket connections. To mitigate URL
    logging risks:
    - Tokens have short expiry (configured via ACCESS_TOKEN_EXPIRE_MINUTES)
    - All connections are logged for audit
    - Origin header validation prevents cross-site usage
    """
    # 1. Validate token presence and format
    token = websocket.query_params.get("token")
    if not token:
        logger.warning(f"WebSocket auth failed: missing token")
        return None

    # 2. Decode and validate JWT (checks expiry, signature, type)
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        logger.warning(f"WebSocket auth failed: invalid token payload")
        return None

    # 3. Validate Origin header to prevent cross-origin WebSocket hijacking
    origin = websocket.headers.get("origin")
    if origin:
        # Parse allowed origins from settings
        allowed_origins = settings.CORS_ORIGINS
        if allowed_origins and "*" not in allowed_origins:
            from urllib.parse import urlparse
            parsed_origin = urlparse(origin)
            origin_host = f"{parsed_origin.hostname}:{parsed_origin.port or (443 if parsed_origin.scheme == 'https' else 80)}"

            # Check if origin matches any allowed origin
            is_allowed = False
            for allowed in allowed_origins:
                allowed_parsed = urlparse(allowed)
                allowed_host = f"{allowed_parsed.hostname}:{allowed_parsed.port or (443 if allowed_parsed.scheme == 'https' else 80)}"
                if origin_host == allowed_host:
                    is_allowed = True
                    break

            if not is_allowed:
                logger.warning(f"WebSocket auth failed: invalid origin {origin}")
                return None

    # 4. Log successful authentication for audit
    user_id = payload.get("sub")
    username = payload.get("username", "unknown")
    logger.info(f"WebSocket authenticated: user={username} (id={user_id})")

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
            except Exception as e:
                # Surface the error but keep the connection alive so the client
                # can recover once the backend becomes reachable again.
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": str(e),
                }))
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        return

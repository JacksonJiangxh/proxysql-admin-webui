"""Request body size limit middleware.

Rejects requests with Content-Length exceeding a configurable maximum
to prevent memory exhaustion / DoS attacks via oversized payloads.

Configuration:
    MAX_REQUEST_BODY_SIZE — max body size in bytes (default: 10 MB)

Implemented as pure ASGI middleware (not BaseHTTPMiddleware) to avoid the
Starlette BaseHTTPMiddleware bug where HTTPException inside a TaskGroup
gets swallowed and converted to 500.
"""

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

# Excluded paths that may legitimately have large payloads
_EXCLUDED_PREFIXES = (
    "/api/v1/export/",  # file exports return blobs, not large uploads
)


class BodyLimitMiddleware:
    """Rejects requests whose Content-Length exceeds MAX_REQUEST_BODY_SIZE.

    Placed AFTER CORS and BEFORE CSRF so that preflight requests and
    security checks are not affected. Only POST/PUT/PATCH are checked;
    GET/DELETE/OPTIONS are always allowed.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # Only check state-changing methods — GET/HEAD/OPTIONS/DELETE
        if request.method not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return

        # Skip excluded paths
        for prefix in _EXCLUDED_PREFIXES:
            if request.url.path.startswith(prefix):
                await self.app(scope, receive, send)
                return

        max_bytes = settings.MAX_REQUEST_BODY_SIZE
        content_length = request.headers.get("content-length")

        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                logger.warning(
                    "Invalid Content-Length header from %s: %s",
                    request.client.host if request.client else "unknown",
                    content_length,
                )
                response = JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )
                await response(scope, receive, send)
                return

            if size > max_bytes:
                logger.warning(
                    "Request body too large from %s: %d bytes (max %d)",
                    request.client.host if request.client else "unknown",
                    size,
                    max_bytes,
                )
                response = JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Request body too large. "
                            f"Maximum: {max_bytes // (1024 * 1024)} MB"
                        )
                    },
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)

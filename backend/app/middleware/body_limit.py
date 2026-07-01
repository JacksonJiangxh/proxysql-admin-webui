"""Request body size limit middleware.

Rejects requests with Content-Length exceeding a configurable maximum
to prevent memory exhaustion / DoS attacks via oversized payloads.

Configuration:
    MAX_REQUEST_BODY_SIZE — max body size in megabytes (default: 10 MB)
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

# Excluded paths that may legitimately have large payloads
_EXCLUDED_PREFIXES = (
    "/api/v1/export/",  # file exports return blobs, not large uploads
)


class BodyLimitMiddleware(BaseHTTPMiddleware):
    """Rejects requests whose Content-Length exceeds MAX_REQUEST_BODY_SIZE.

    Placed AFTER CORS and BEFORE CSRF so that preflight requests and
    security checks are not affected. Only POST/PUT/PATCH are checked;
    GET/DELETE/OPTIONS are always allowed.
    """

    async def dispatch(self, request: Request, call_next):
        # Only check state-changing methods — GET/HEAD/OPTIONS/DELETE
        # (DELETE rarely has a body)
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        # Skip excluded paths
        for prefix in _EXCLUDED_PREFIXES:
            if request.url.path.startswith(prefix):
                return await call_next(request)

        max_bytes = settings.MAX_REQUEST_BODY_SIZE  # already in bytes
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
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )

            if size > max_bytes:
                logger.warning(
                    "Request body too large from %s: %d bytes (max %d)",
                    request.client.host if request.client else "unknown",
                    size,
                    max_bytes,
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Request body too large. "
                            f"Maximum: {max_bytes // (1024 * 1024)} MB"
                        )
                    },
                )

        # Note: if Content-Length is missing, the request will naturally
        # fail at the application level if the body is too large. The
        # uvicorn layer also enforces its own limit via --limit-max-requests,
        # but that's a connection-level timeout, not a size limit.

        return await call_next(request)

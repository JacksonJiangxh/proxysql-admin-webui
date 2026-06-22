"""Middleware for adding caching headers to API responses.

Sets Cache-Control and ETag headers based on endpoint characteristics:
- Static assets (/assets/): 1 year cache (immutable, content-hashed)
- Dashboard / health: short 30s cache (frequently changing data)
- Wizard definitions: 5 minute cache (rarely changes)
- Other GET endpoints: no-store (dynamic data)
- POST/PUT/DELETE: no-store (always fresh)
"""

import time
import hashlib
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CacheHeadersMiddleware(BaseHTTPMiddleware):
    """Adds appropriate Cache-Control and ETag headers to responses."""

    # Cache durations in seconds
    STATIC_CACHE = 31536000   # 1 year for content-hashed static assets
    SHORT_CACHE = 30          # 30 seconds for frequently updated data
    MEDIUM_CACHE = 300        # 5 minutes for semi-static data (wizard defs)
    LONG_CACHE = 3600         # 1 hour for stable config

    # Path patterns for different cache durations
    SHORT_CACHE_PREFIXES = ("/api/v1/dashboard", "/api/v1/health")
    MEDIUM_CACHE_PREFIXES = ("/api/v1/wizards",)
    LONG_CACHE_PREFIXES = ("/assets/",)

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Only cache successful GET/HEAD responses
        if request.method not in ("GET", "HEAD"):
            response.headers["Cache-Control"] = "no-store"
            return response

        if response.status_code >= 400:
            response.headers["Cache-Control"] = "no-store"
            return response

        path = request.url.path

        # Determine cache duration based on path
        if any(path.startswith(p) for p in self.LONG_CACHE_PREFIXES):
            max_age = self.STATIC_CACHE
            cache_control = f"public, max-age={max_age}, immutable"
        elif any(path.startswith(p) for p in self.MEDIUM_CACHE_PREFIXES):
            max_age = self.MEDIUM_CACHE
            cache_control = f"public, max-age={max_age}, stale-while-revalidate={max_age}"
        elif any(path.startswith(p) for p in self.SHORT_CACHE_PREFIXES):
            max_age = self.SHORT_CACHE
            cache_control = f"public, max-age={max_age}, stale-while-revalidate={max_age}"
        else:
            cache_control = "no-store"

        response.headers["Cache-Control"] = cache_control

        # Add weak ETag for content-based caching (skip for streaming/large responses)
        body = getattr(response, "body", None)
        if body and len(body) < 1024 * 100:  # Only for responses < 100KB
            etag = hashlib.md5(body).hexdigest()
            response.headers["ETag"] = f'W/"{etag}"'

        return response

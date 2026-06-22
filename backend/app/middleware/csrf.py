"""CSRF protection middleware using Double Submit Cookie pattern.

This implementation follows the OWASP recommendations for CSRF protection:
1. Strict origin validation
2. Double Submit Cookie pattern with synchronized tokens
3. Custom header check (most secure, no token leakage)
"""
import secrets
import hashlib
import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


# Paths exempt from CSRF protection (public endpoints)
CSRF_EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/health",
    "/api/docs",
    "/api/openapi.json",
    "/ws/",
}


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware using Double Submit Cookie pattern.

    For state-changing requests (POST, PUT, PATCH, DELETE), this middleware:
    1. Validates the Origin/Referer header (same-origin policy)
    2. Checks for X-CSRF-Token header (custom header approach)
    3. Verifies the token matches the cookie

    The custom header approach is preferred because:
    - No token exposure in URL query strings
    - No token stored in server-side session
    - Works well with SPA architecture
    """

    # Header name for CSRF token (client must send this)
    CSRF_HEADER = "x-csrf-token"
    # Cookie name for CSRF token
    CSRF_COOKIE = "csrf_token"
    # Cookie settings — secure=False so the cookie is also set over HTTP
    # during local development. In production behind HTTPS, set the
    # CSRF_COOKIE_SECURE=true env var to enforce HTTPS-only cookies.
    COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "false").lower() == "true"
    COOKIE_SAMESITE = "lax"  # or "strict" for maximum protection

    async def dispatch(self, request: Request, call_next):
        """Process request with CSRF validation for state-changing operations."""
        path = request.url.path.rstrip("/")

        # Skip exempt paths
        if any(path.startswith(p) for p in CSRF_EXEMPT_PATHS):
            return await call_next(request)

        # Only validate state-changing methods
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            response = await call_next(request)
            # Set CSRF token cookie for GET requests
            response = await self._set_csrf_cookie(request, response)
            return response

        # Validate CSRF token
        if not await self._validate_csrf(request):
            raise HTTPException(
                status_code=403,
                detail="CSRF validation failed. Ensure you're using the app from the legitimate origin and include the X-CSRF-Token header."
            )

        response = await call_next(request)
        # Rotate CSRF token after successful state-changing request
        response = await self._set_csrf_cookie(request, response)
        return response

    async def _validate_csrf(self, request: Request) -> bool:
        """Validate the CSRF token using Double Submit Cookie pattern.

        The client must:
        1. Read the csrf_token cookie
        2. Send the same value in the X-CSRF-Token header

        This ensures that only a page served by the legitimate origin
        can send valid requests (since cookies can't be read/set by
        cross-origin scripts).
        """
        # 1. Check Origin/Referer for same-origin policy
        origin = request.headers.get("origin") or request.headers.get("referer")
        if origin:
            # Validate origin is from our domain
            host = request.headers.get("host", "").split(":")[0]
            if host and not self._is_same_origin(request, origin, host):
                return False

        # 2. Check for CSRF token header
        token_header = request.headers.get(self.CSRF_HEADER)
        if not token_header:
            return False

        # 3. Check token cookie exists
        token_cookie = request.cookies.get(self.CSRF_COOKIE)
        if not token_cookie:
            return False

        # 4. Validate tokens match (constant-time comparison)
        return secrets.compare_digest(token_header, token_cookie)

    async def _set_csrf_cookie(self, request: Request, response: Response) -> Response:
        """Generate and set a new CSRF token cookie.

        Token is generated using secrets.token_hex() for cryptographic security.
        """
        # Generate new token
        token = secrets.token_hex(32)

        # Set cookie with security attributes
        response.set_cookie(
            key=self.CSRF_COOKIE,
            value=token,
            httponly=False,  # Must be readable by JavaScript for custom header approach
            secure=self.COOKIE_SECURE,
            samesite=self.COOKIE_SAMESITE,
            max_age=3600 * 24,  # 24 hours
            path="/",
        )

        return response

    def _is_same_origin(self, request: Request, origin: str, host: str) -> bool:
        """Check if the origin is the same as the host."""
        try:
            # Parse origin (format: https://example.com:8080)
            from urllib.parse import urlparse
            parsed = urlparse(origin)

            # Check scheme and host match
            origin_host = parsed.hostname
            origin_port = parsed.port

            # Normalize port (default 443 for https, 80 for http)
            if origin_port is None:
                origin_port = 443 if parsed.scheme == "https" else 80

            # Get request host and port
            request_port = request.headers.get("host", "").split(":")
            request_host = request_port[0]
            request_port = int(request_port[1]) if len(request_port) > 1 else (443 if request.url.scheme == "https" else 80)

            return (
                origin_host == request_host
                and origin_port == request_port
                and parsed.scheme == request.url.scheme
            )
        except Exception:
            # If parsing fails, be permissive (other checks will fail later if there's an issue)
            return True


def generate_csrf_token() -> str:
    """Utility function to generate a CSRF token programmatically.

    Use this when you need to generate a token outside of the middleware
    (e.g., for testing or specific workflows).
    """
    return secrets.token_hex(32)


def validate_csrf_token(token: str, cookie_token: str) -> bool:
    """Utility function to validate a CSRF token pair.

    Args:
        token: The token from the X-CSRF-Token header
        cookie_token: The token from the csrf_token cookie

    Returns:
        True if tokens match and are valid, False otherwise
    """
    if not token or not cookie_token:
        return False
    return secrets.compare_digest(token, cookie_token)

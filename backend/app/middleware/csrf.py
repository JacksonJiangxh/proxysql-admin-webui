"""CSRF protection middleware using Double Submit Cookie pattern.

This implementation follows the OWASP recommendations for CSRF protection:
1. Strict origin validation (configurable trusted origins for reverse-proxy setups)
2. Double Submit Cookie pattern with synchronized tokens
3. Custom header check (most secure, no token leakage)

When deployed behind a reverse proxy, set TRUSTED_ORIGINS to the external
domain(s) users will access from (e.g. "https://proxysql.example.com").
"""
import secrets
import hashlib
import os
from urllib.parse import urlparse

from fastapi import Request
from starlette.responses import Response, JSONResponse


# Paths exempt from CSRF protection (public endpoints)
CSRF_EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/health",
    "/api/docs",
    "/api/openapi.json",
    "/ws/",
}

# Trusted external origins — set via TRUSTED_ORIGINS env var (comma-separated).
# Required when the app sits behind a reverse proxy where the Host header
# seen by the backend differs from the Origin header sent by the browser.
# Example: TRUSTED_ORIGINS=https://proxysql.example.com,https://other.example.com
_TRUSTED_ORIGINS = {
    o.strip()
    for o in os.getenv("TRUSTED_ORIGINS", "").split(",")
    if o.strip()
}

# Whether to skip origin validation entirely (e.g. for internal/trusted networks).
# Default: false. Set CSRF_SKIP_ORIGIN_CHECK=true if your proxy strips Origin/Referer.
_SKIP_ORIGIN_CHECK = os.getenv("CSRF_SKIP_ORIGIN_CHECK", "false").lower() in ("1", "true", "yes")


class CSRFMiddleware:
    """CSRF protection middleware using Double Submit Cookie pattern.

    Implemented as pure ASGI middleware (not BaseHTTPMiddleware) to avoid the
    Starlette BaseHTTPMiddleware bug where HTTPException inside a TaskGroup
    gets swallowed and converted to 500.

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

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path.rstrip("/")

        # Skip exempt paths
        if any(path.startswith(p) for p in CSRF_EXEMPT_PATHS):
            await self.app(scope, receive, send)
            return

        # Only validate state-changing methods
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            # For safe methods, pass through and attach CSRF cookie on response
            await self._wrap_with_csrf_cookie(scope, receive, send, request)
            return

        # Validate CSRF token for state-changing requests
        csrf_result = await self._validate_csrf(request)
        if not csrf_result[0]:
            reason = csrf_result[1]
            # Generate a fresh CSRF token in the 403 response so the client
            # can retry without needing a separate GET request first.
            token = secrets.token_hex(32)
            cookie_value = (
                f"{self.CSRF_COOKIE}={token}; "
                f"Path=/; "
                f"Max-Age={3600 * 24}; "
                f"SameSite={self.COOKIE_SAMESITE}"
            )
            if self.COOKIE_SECURE:
                cookie_value += "; Secure"
            response = JSONResponse(
                status_code=403,
                content={
                    "detail": f"CSRF validation failed: {reason}",
                    "csrf_token": token,
                },
                headers={"Set-Cookie": cookie_value},
            )
            await response(scope, receive, send)
            return

        # Pass through and rotate CSRF cookie
        await self._wrap_with_csrf_cookie(scope, receive, send, request)

    async def _wrap_with_csrf_cookie(self, scope, receive, send, request: Request = None):
        """Call the inner app and ensure a CSRF cookie is set on the response.

        Only sets a new cookie if one doesn't already exist on the request,
        avoiding unnecessary token rotation that can cause race conditions
        when multiple GET requests are in flight concurrently.
        """
        # Use the provided request or create one if not available
        if request is None:
            request = Request(scope, receive)
        existing_token = request.cookies.get(self.CSRF_COOKIE)

        async def _send(message):
            if message["type"] == "http.response.start":
                # Re-use existing token if present; generate new one only on first visit
                token = existing_token or secrets.token_hex(32)
                cookie_value = (
                    f"{self.CSRF_COOKIE}={token}; "
                    f"Path=/; "
                    f"Max-Age={3600 * 24}; "
                    f"SameSite={self.COOKIE_SAMESITE}"
                )
                if self.COOKIE_SECURE:
                    cookie_value += "; Secure"
                # Append as an additional set-cookie header (don't overwrite existing ones)
                headers = list(message.get("headers", []))
                headers.append((b"set-cookie", cookie_value.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, _send)

    async def _validate_csrf(self, request: Request) -> tuple:
        """Validate the CSRF token using Double Submit Cookie pattern.

        Returns:
            (True, "") on success, or (False, "reason") on failure.
        """
        # 1. Check Origin/Referer for same-origin policy
        if not _SKIP_ORIGIN_CHECK:
            origin = request.headers.get("origin") or request.headers.get("referer")
            if origin:
                host = request.headers.get("host", "").split(":")[0]
                if host and not self._is_same_origin(request, origin, host):
                    return (False, f"origin mismatch: {origin} vs host {host}")

        # 2. Check for CSRF token header
        token_header = request.headers.get(self.CSRF_HEADER)
        if not token_header:
            return (False, "missing X-CSRF-Token header")

        # 3. Check token cookie exists
        token_cookie = request.cookies.get(self.CSRF_COOKIE)
        if not token_cookie:
            return (False, "missing csrf_token cookie")

        # 4. Validate tokens match (constant-time comparison)
        if not secrets.compare_digest(token_header, token_cookie):
            return (False, "token mismatch")

        return (True, "")

    def _is_same_origin(self, request: Request, origin: str, host: str) -> bool:
        """Check if the origin matches either the request host or a trusted origin.

        When deployed behind a reverse proxy, the Host header may be the
        internal backend address (e.g. "proxysql-webui:8080"), while the
        Origin header is the external user-facing domain. Set TRUSTED_ORIGINS
        to allow these external origins through CSRF checks.
        """
        # First check: is origin in the trusted origins list?
        if _TRUSTED_ORIGINS:
            origin_normalized = origin.rstrip("/")
            if origin_normalized in _TRUSTED_ORIGINS:
                return True

        # Second check: strict same-origin via Host header
        try:
            parsed = urlparse(origin)

            origin_host = parsed.hostname
            origin_port = parsed.port
            if origin_port is None:
                origin_port = 443 if parsed.scheme == "https" else 80

            request_port_parts = request.headers.get("host", "").split(":")
            request_host = request_port_parts[0]
            # Respect X-Forwarded-Proto when behind a reverse proxy
            forwarded_proto = request.headers.get("x-forwarded-proto", "")
            scheme = forwarded_proto if forwarded_proto in ("http", "https") else request.url.scheme
            request_port = (
                int(request_port_parts[1]) if len(request_port_parts) > 1
                else (443 if scheme == "https" else 80)
            )

            return (
                origin_host == request_host
                and origin_port == request_port
                and parsed.scheme == scheme
            )
        except Exception:
            # If parsing fails, be permissive
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

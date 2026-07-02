"""Security headers middleware for HTTP response hardening.

Adds Content-Security-Policy, X-Content-Type-Options, X-Frame-Options,
X-XSS-Protection, Strict-Transport-Security, Referrer-Policy, and
Permissions-Policy headers to every response.
"""
import os
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security-related HTTP headers to every response.

    This middleware applies defense-in-depth headers recommended by OWASP:
    - Content-Security-Policy: Restrict script/style sources
    - X-Content-Type-Options: Prevent MIME sniffing
    - X-Frame-Options: Prevent clickjacking
    - X-XSS-Protection: Enable browser XSS filter
    - Strict-Transport-Security: Enforce HTTPS
    - Referrer-Policy: Control referrer information
    - Permissions-Policy: Disable sensitive browser features
    """

    # Content-Security-Policy that allows:
    # - Same-origin scripts, styles, images, fonts, connections
    # - Inline styles (needed by React and many UI libraries)
    # - 'unsafe-inline' for styles is the only relaxation
    # - script-src 'self' is sufficient for same-origin SPA deployments.
    #   We deliberately avoid 'strict-dynamic' because the Vite build output
    #   uses <script type="module" src="..."> without nonces, which would be
    #   blocked by 'strict-dynamic'.
    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-src 'none'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "worker-src 'self' blob:; "
    )

    # Check if the request came over HTTPS (directly or via proxy)
    @staticmethod
    def _is_https(request: Request) -> bool:
        """Determine if the request is over HTTPS."""
        # Check forwarded proto header (set by reverse proxies like nginx)
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        if forwarded_proto.lower() == "https":
            return True
        # Check the request URL scheme
        if request.url.scheme == "https":
            return True
        return False

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and attach security headers to the response."""
        response = await call_next(request)

        # Content-Security-Policy
        response.headers["Content-Security-Policy"] = self.CSP_POLICY

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Enable browser XSS filter (legacy but still useful for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # HSTS - only set when the connection is over HTTPS
        if self._is_https(request):
            response.headers[
                "Strict-Transport-Security"
            ] = "max-age=31536000; includeSubDomains"

        # Restrict referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy: disable camera, microphone, geolocation
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        return response

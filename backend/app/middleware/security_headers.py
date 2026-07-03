"""Security headers middleware for HTTP response hardening.

Adds Content-Security-Policy, X-Content-Type-Options, X-Frame-Options,
X-XSS-Protection, Strict-Transport-Security, Referrer-Policy, and
Permissions-Policy headers to every response.

Implemented as pure ASGI middleware (not BaseHTTPMiddleware) to avoid the
Starlette BaseHTTPMiddleware bug where HTTPException inside a TaskGroup
gets swallowed and converted to 500.
"""
from fastapi import Request


class SecurityHeadersMiddleware:
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

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        is_https = self._is_https(request)

        async def _send(message):
            if message["type"] == "http.response.start":
                headers_list = list(message.get("headers", []))

                # Content-Security-Policy
                headers_list.append((b"content-security-policy", self.CSP_POLICY.encode("latin-1")))
                # Prevent MIME type sniffing
                headers_list.append((b"x-content-type-options", b"nosniff"))
                # Prevent clickjacking
                headers_list.append((b"x-frame-options", b"DENY"))
                # Enable browser XSS filter
                headers_list.append((b"x-xss-protection", b"1; mode=block"))
                # HSTS - only set when the connection is over HTTPS
                if is_https:
                    headers_list.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                # Restrict referrer information
                headers_list.append(
                    (b"referrer-policy", b"strict-origin-when-cross-origin")
                )
                # Permissions-Policy
                headers_list.append(
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()")
                )

                message["headers"] = headers_list
            await send(message)

        await self.app(scope, receive, _send)

    @staticmethod
    def _is_https(request: Request) -> bool:
        """Determine if the request is over HTTPS."""
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        if forwarded_proto.lower() == "https":
            return True
        if request.url.scheme == "https":
            return True
        return False

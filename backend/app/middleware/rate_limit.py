"""Rate limiting middleware with endpoint-specific and user-based limits.

Reads configuration from ``app.config.settings`` so that limits can be
customized via environment variables without code changes.

Response headers (RFC 6585 / draft‑rate‑limit‑headers):
  - ``Retry-After``   : seconds until the client may retry (429 only)
  - ``X-RateLimit-Limit``     : max requests per window
  - ``X-RateLimit-Remaining``  : requests remaining in current window
  - ``X-RateLimit-Reset``      : seconds until the window resets

Implemented as pure ASGI middleware (not BaseHTTPMiddleware) to avoid the
Starlette BaseHTTPMiddleware bug where HTTPException inside a TaskGroup
gets swallowed and converted to 500.
"""
import time
from collections import defaultdict, deque
from typing import Optional
from fastapi import Request
from starlette.responses import JSONResponse

from app.config import settings


# ── Per-endpoint limit overrides ──────────────────────────────────
# Format: { "path_prefix": (max_requests, window_seconds) }
# These are stricter than the global limit for sensitive operations.
_DEFAULT_ENDPOINT_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/wizards/execute": (10, 60),
    "/api/v1/query/": (20, 60),
    "/api/v1/auth/login": (5, 60),
}


class SimpleRateLimiter:
    """Sliding-window rate limiter backed by an in-memory dict.

    NOTE: this is a single-process implementation.  For multi-replica
    deployments, replace with a shared store (Redis, Memcached).
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._store: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, key: str) -> tuple[bool, dict[str, str]]:
        """Check if ``key`` is allowed and return rate-limit headers.

        Returns:
            (allowed, headers_dict)
        """
        now = time.time()
        window = self._store[key]
        # Evict timestamps outside the current window
        while window and window[0] < now - self.window_seconds:
            window.popleft()

        remaining = max(0, self.max_requests - len(window))
        headers = {
            "X-RateLimit-Limit": str(self.max_requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(self.window_seconds - (now % self.window_seconds))),
        }

        if len(window) < self.max_requests:
            window.append(now)
            return True, headers

        # Calculate Retry-After: seconds until the oldest request in the
        # window expires.
        retry_after = int(window[0] - (now - self.window_seconds)) + 1
        headers["Retry-After"] = str(max(retry_after, 1))
        return False, headers


class RateLimitMiddleware:
    """Global + per-endpoint rate limiter (pure ASGI middleware).

    Middleware is **disabled** when ``settings.RATE_LIMIT_ENABLED`` is
    ``False`` — useful for internal deployments or debugging.
    """

    # Paths that are never rate-limited (health-check, docs, etc.)
    EXEMPT_PATHS: set[str] = {
        "/api/v1/health",
        "/api/docs",
        "/api/openapi.json",
        "/ws/",
    }

    def __init__(self, app):
        self.app = app
        # Global limiter — values from settings (env-overridable)
        self.global_limiter = SimpleRateLimiter(
            max_requests=settings.RATE_LIMIT_GLOBAL_MAX,
            window_seconds=settings.RATE_LIMIT_GLOBAL_WINDOW,
        )
        # Per-endpoint limiters (lazily created)
        self._endpoint_limiters: dict[str, SimpleRateLimiter] = {}
        self._build_endpoint_limits()

    def _build_endpoint_limits(self) -> None:
        """Build the endpoint limit map from settings or defaults."""
        self.endpoint_limits: dict[str, tuple[int, int]] = dict(_DEFAULT_ENDPOINT_LIMITS)

    def _get_endpoint_limiter(self, max_req: int, window: int) -> SimpleRateLimiter:
        """Get or create a per-endpoint limiter (keyed by "max:window")."""
        key = f"{max_req}:{window}"
        if key not in self._endpoint_limiters:
            self._endpoint_limiters[key] = SimpleRateLimiter(
                max_requests=max_req, window_seconds=window
            )
        return self._endpoint_limiters[key]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Skip entirely when rate-limiting is disabled
        if not settings.RATE_LIMIT_ENABLED:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path.rstrip("/")

        # Exempt paths (health-check, docs, WebSockets)
        if any(path.startswith(p.rstrip("/")) for p in self.EXEMPT_PATHS):
            await self.app(scope, receive, send)
            return

        # ── 1. Global rate limit (IP-based) ───────────────────────
        ip_key = self._client_key(request)
        allowed, headers = self.global_limiter.is_allowed(ip_key)
        if not allowed:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Global rate limit exceeded. Please retry later."},
                headers=headers,
            )
            await response(scope, receive, send)
            return

        # ── 2. Per-endpoint stricter limits ─────────────────────────
        for prefix, (max_req, window) in self.endpoint_limits.items():
            if path.startswith(prefix):
                ep_limiter = self._get_endpoint_limiter(max_req, window)
                ep_allowed, ep_headers = ep_limiter.is_allowed(ip_key)
                if not ep_allowed:
                    response = JSONResponse(
                        status_code=429,
                        content={
                            "detail": (
                                f"Rate limit exceeded for this endpoint "
                                f"({max_req} requests per {window}s). "
                                f"Please retry in {ep_headers.get('Retry-After', '?')}s."
                            )
                        },
                        headers=ep_headers,
                    )
                    await response(scope, receive, send)
                    return
                break

        # ── 3. User-based rate limiting (authenticated requests) ───
        user_id: Optional[int] = getattr(request.state, "user_id", None)
        if user_id is not None:
            user_key = f"user:{user_id}"
            user_allowed, _ = self.global_limiter.is_allowed(user_key)
            if not user_allowed:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "User rate limit exceeded. Please retry later."},
                )
                await response(scope, receive, send)
                return

        # Pass through and attach rate-limit headers to response
        await self._wrap_with_headers(scope, receive, send, headers)

    async def _wrap_with_headers(self, scope, receive, send, extra_headers: dict[str, str]):
        """Call the inner app and append rate-limit headers to the response."""

        async def _send(message):
            if message["type"] == "http.response.start":
                headers_list = list(message.get("headers", []))
                for h, v in extra_headers.items():
                    headers_list.append(
                        (h.encode("latin-1"), v.encode("latin-1"))
                    )
                message["headers"] = headers_list
            await send(message)

        await self.app(scope, receive, _send)

    @staticmethod
    def _client_key(request: Request) -> str:
        """Determine a rate-limiting key for the client.

        Prefers ``X-Forwarded-For`` (respects proxies), falls back to
        ``request.client.host``.
        """
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"


# ── Login-specific rate limiter (dependency) ───────────────────────
# This is used as a ``Depends(...)`` on the login endpoint *in addition*
# to the middleware, providing defense-in-depth.
_login_limiter = SimpleRateLimiter(
    max_requests=settings.RATE_LIMIT_LOGIN_MAX,
    window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW,
)


class LoginRateLimiter:
    """FastAPI dependency that rate-limits the login endpoint."""

    def __call__(self, request: Request):
        key = RateLimitMiddleware._client_key(request)
        allowed, headers = _login_limiter.is_allowed(key)
        if not allowed:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts. Please wait before retrying.",
                headers=headers,
            )
        return key


login_rate_limiter = LoginRateLimiter()

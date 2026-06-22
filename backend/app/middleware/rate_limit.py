"""Simple in-memory rate limiting middleware with endpoint-specific and user-based limits."""
import time
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class SimpleRateLimiter:
    """Token-bucket-ish sliding window rate limiter backed by an in-memory dict."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._store: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window = self._store[key]
        # Remove timestamps outside the window
        while window and window[0] < now - self.window_seconds:
            window.popleft()
        if len(window) < self.max_requests:
            window.append(now)
            return True
        return False


# Endpoint-specific rate limit configurations: (max_requests, window_seconds)
ENDPOINT_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/wizards/execute": (10, 60),   # 10 wizard executions per minute
    "/api/v1/query/": (20, 60),             # 20 query executions per minute (prefix match)
    "/api/v1/auth/login": (5, 60),          # 5 login attempts per minute
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Global API rate limiter with endpoint-specific and user-based limits.

    Uses client IP as the primary key. Supports per-endpoint overrides for
    stricter limits on sensitive operations (wizards, query execution, login).

    Also supports user-based rate limiting when the user is authenticated.
    """

    EXEMPT_PATHS = {
        "/api/v1/health",
        "/api/docs",
        "/api/openapi.json",
    }

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.global_limiter = SimpleRateLimiter(max_requests=max_requests, window_seconds=window_seconds)
        # Per-endpoint limiters (created on-demand)
        self._endpoint_limiters: dict[str, SimpleRateLimiter] = {}

    def _get_endpoint_limiter(self, max_req: int, window: int) -> SimpleRateLimiter:
        """Get or create an endpoint-specific rate limiter."""
        key = f"{max_req}:{window}"
        if key not in self._endpoint_limiters:
            self._endpoint_limiters[key] = SimpleRateLimiter(max_requests=max_req, window_seconds=window)
        return self._endpoint_limiters[key]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/")
        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        # 1. Global rate limit (IP-based)
        ip_key = self._client_key(request)
        if not self.global_limiter.is_allowed(ip_key):
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")

        # 2. Endpoint-specific rate limits (more restrictive)
        for prefix, (max_req, window) in ENDPOINT_LIMITS.items():
            if path.startswith(prefix):
                endpoint_limiter = self._get_endpoint_limiter(max_req, window)
                if not endpoint_limiter.is_allowed(ip_key):
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded for this endpoint ({max_req} requests per {window}s). Try again later."
                    )
                break

        # 3. User-based rate limiting (if authenticated)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            user_key = f"user:{user_id}"
            if not self.global_limiter.is_allowed(user_key):
                raise HTTPException(status_code=429, detail="User rate limit exceeded. Try again later.")

        return await call_next(request)

    @staticmethod
    def _client_key(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"


class LoginRateLimiter:
    """Dependency for rate limiting the login endpoint by client IP."""

    _limiter = SimpleRateLimiter(max_requests=5, window_seconds=60)

    def __call__(self, request: Request):
        key = RateLimitMiddleware._client_key(request)
        if not self._limiter.is_allowed(key):
            raise HTTPException(status_code=429, detail="Too many login attempts")
        return key


login_rate_limiter = LoginRateLimiter()

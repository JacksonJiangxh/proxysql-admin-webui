"""Prometheus metrics middleware and /metrics endpoint.

Exposes standard HTTP metrics for monitoring via Prometheus/Grafana:
- http_requests_total: Counter by method, path template, and status code
- http_request_duration_seconds: Histogram by method and path template
- http_requests_in_flight: Gauge of currently active requests

The /metrics endpoint returns text/plain Prometheus exposition format.
"""

import time
import re
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# ── Metric definitions ──────────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests handled",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_REQUESTS_IN_FLIGHT = Gauge(
    "http_requests_in_flight",
    "Number of HTTP requests currently being processed",
    ["method"],
)

# Regex: match UUIDs, numeric IDs in path segments
_PATH_NORMALIZE_RE = re.compile(
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|"
    r"/\d+(?=/|$)"
)


def _normalize_path(path: str) -> str:
    """Replace path parameters with placeholders to avoid label cardinality explosion.

    Examples:
        /api/v1/backup/abc-123/create  →  /api/v1/backup/:id/create
        /api/v1/servers/5              →  /api/v1/servers/:id
    """
    return _PATH_NORMALIZE_RE.sub("/:id", path)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Records HTTP request count, latency, and in-flight gauge.

    Should be placed early in the middleware stack (after GZip, before
    security/audit) to capture accurate timing.  Requests to /metrics
    itself are excluded to avoid noise and recursion.
    """

    EXEMPT_PREFIXES = ("/metrics", "/api/v1/metrics", "/health")

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)

        method = request.method
        HTTP_REQUESTS_IN_FLIGHT.labels(method=method).inc()
        start = time.time()

        try:
            response = await call_next(request)
            status = str(response.status_code)
        except Exception:
            status = "500"
            raise
        finally:
            HTTP_REQUESTS_IN_FLIGHT.labels(method=method).dec()

        normalized = _normalize_path(path)
        HTTP_REQUESTS_TOTAL.labels(method=method, path=normalized, status=status).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=normalized).observe(
            time.time() - start
        )

        return response


async def metrics_endpoint() -> Response:
    """Prometheus /metrics endpoint returning text format."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )

"""Main FastAPI application entry point.

Single-process deployment: the FastAPI app serves both the REST/WebSocket
API *and* the built frontend (frontend/dist) as static files on the same
origin. This mirrors the architecture of the reference projects (proxui,
proxyweb) and removes the need for an nginx reverse proxy — the whole UI
runs from one `uvicorn` process.

Development:
    `make dev-frontend` runs Vite on :5173 with a proxy to :8080.
Production / bare-metal:
    `make build-frontend` builds frontend/dist, then `make run` serves
    everything from http://localhost:8080.
PyInstaller single-binary:
    `pyinstaller --onefile backend/run.py` bundles frontend + backend into
    one executable.  At runtime `sys._MEIPASS` points to the unpacked bundle.
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.api.v1 import (
    auth, tables, sync, query, dashboard, users, servers, wizards,
    config_diff, clusters, templates, backup, export, scheduler,
)
from app.api.v1 import settings as settings_api
from app.middleware.csrf import CSRFMiddleware
from app.middleware.audit import AuditMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.cache_headers import CacheHeadersMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.metrics import MetricsMiddleware, metrics_endpoint
from app.middleware.body_limit import BodyLimitMiddleware
from app.schemas.response import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB, start scheduler, setup structured logging."""
    from app.utils.logger import setup_logging
    setup_logging(
        log_level=settings.LOG_LEVEL,
        json_format=os.getenv("LOG_FORMAT", "").lower() != "text",
    )
    await init_db()
    # Initialize cache TTLs from settings
    from app.services.cache_service import cache_service
    cache_service._dashboard_ttl = settings.CACHE_TTL_DASHBOARD
    cache_service._config_diff_ttl = settings.CACHE_TTL_CONFIG_DIFF
    # Start the APScheduler for auto-backup tasks
    from app.services.scheduler_service import scheduler_service
    await scheduler_service.start()
    yield
    await scheduler_service.shutdown()


app = FastAPI(
    title="ProxySQL Admin WebUI",
    description="Web-based management interface for ProxySQL",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ═══════════════════════════════════════════════════════════════════
# Middleware Stack (order matters!)
# ═══════════════════════════════════════════════════════════════════
#
# Requests flow through middlewares in the order they are added below.
# Each middleware's position is carefully chosen for security and correctness.
#
# ALL custom middlewares are implemented as pure ASGI middleware (not
# BaseHTTPMiddleware) to avoid the Starlette BaseHTTPMiddleware bug where
# HTTPException inside a TaskGroup gets swallowed and converted to 500.
#
# Ordering rationale:
#   1. CORSMiddleware        — Handles OPTIONS pre-flight FIRST, before any
#                            auth/CSRF logic runs. In production (same-origin
#                            SPA serving) CORS is effectively a no-op.
#   2. GZipMiddleware       — Compresses the response body. Placed early so
#                            that downstream middlewares still see uncompressed
#                            bodies (simplifies ETag calculation).
#   3. MetricsMiddleware    — Records request counts, latency, and in-flight
#                            gauge. After GZip so compression overhead is
#                            included in timing.
#   4. CacheHeadersMiddleware — Adds Cache-Control. Reads the final
#                            response body AFTER compression.
#   5. SecurityHeadersMw    — Injects CSP, HSTS, X-Frame-Options, etc.
#                            Must run for ALL responses (including errors).
#   6. AuditMiddleware       — Logs the request BEFORE CSRF validation, so
#                            that suspicious requests are still recorded.
#   7. CSRFMiddleware       — Validates double-submit CSRF token. Runs
#                            AFTER audit (so attacks are logged) but BEFORE
#                            rate-limiting (to prevent attackers from exhausting
#                            rate-limit quotas with fake requests).
#   8. RateLimitMiddleware  — Throttles requests per IP and per endpoint.
#                            Runs after CSRF so only legitimate traffic is counted.
#   9. BodyLimitMiddleware  — Checks Content-Length. Rejects oversized
#                            payloads early (413) to prevent memory exhaustion.
# ═══════════════════════════════════════════════════════════════════

# 1. CORS (only relevant for the Vite dev server on :5173; in production the
#    frontend is served same-origin and CORS is a no-op).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-CSRF-Token",
        "X-Requested-With",
    ],
)

# 2. GZip compression: reduces response size for text-based content (JSON, HTML, CSS, JS).
#    Only compresses responses > 500 bytes to avoid overhead on tiny payloads.
app.add_middleware(
    GZipMiddleware,
    minimum_size=500,
)

# 2a. Metrics: records request counts, latency histograms, and in-flight gauge.
#    Placed after GZip so compression overhead is included in timing, but before
#    security/audit middlewares so ALL requests (including rejected ones) are counted.
app.add_middleware(MetricsMiddleware)

# 3. Cache headers: adds ETag and Cache-Control headers for browser/CDN caching.
#    Must be added after other middlewares to see the final response body for ETag.
app.add_middleware(CacheHeadersMiddleware)

# 4. Security headers: adds CSP, HSTS, X-Frame-Options, and other security headers.
#    This runs for EVERY response (including 4xx/5xx) to ensure security headers
#    are always present.
app.add_middleware(SecurityHeadersMiddleware)

# 5. Audit logging: records all requests for audit trail.
#    Runs BEFORE CSRF checks so that even rejected requests are logged.
app.add_middleware(AuditMiddleware)

# 7. CSRF protection: validates double-submit CSRF token for state-changing requests.
#    Runs AFTER audit (attacks are logged) and BEFORE rate-limiting (prevents
#    attackers from wasting rate-limit quotas).
#    Pure ASGI middleware — no BaseHTTPMiddleware TaskGroup bug.
app.add_middleware(CSRFMiddleware)

# 8. Rate limiting: throttles requests per IP and per endpoint.
#    Pure ASGI middleware — no BaseHTTPMiddleware TaskGroup bug.
app.add_middleware(RateLimitMiddleware)

# 9. Body size limiting: rejects oversized POST/PUT/PATCH payloads.
#    Pure ASGI middleware — no BaseHTTPMiddleware TaskGroup bug.
app.add_middleware(BodyLimitMiddleware)

# Register API routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(tables.router, prefix="/api/v1", tags=["Tables"])
app.include_router(sync.router, prefix="/api/v1/sync", tags=["Config Sync"])
app.include_router(query.router, prefix="/api/v1/query", tags=["Query"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(servers.router, prefix="/api/v1/servers", tags=["Servers"])
app.include_router(wizards.router, prefix="/api/v1/wizards", tags=["Wizards"])
app.include_router(templates.router, prefix="/api/v1/wizards", tags=["Templates"])
app.include_router(settings_api.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(config_diff.router, prefix="/api/v1/config-diff", tags=["Config Diff"])
app.include_router(clusters.router, prefix="/api/v1/clusters", tags=["Clusters"])
app.include_router(backup.router, prefix="/api/v1/backup", tags=["Backup"])
app.include_router(export.router, prefix="/api/v1/export", tags=["Export"])
app.include_router(scheduler.router, prefix="/api/v1/scheduler", tags=["Scheduler"])

# WebSocket routes (per TECHNICAL_DOCUMENTATION: /ws/dashboard/{server_id})
app.include_router(dashboard.ws_router, prefix="/ws/dashboard", tags=["Dashboard WS"])


@app.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Deep health check: verifies API availability and database connectivity.

    Returns:
        JSON with ``status``, ``version``, and ``database`` fields.
    """
    db_ok = False
    try:
        from app.database import get_db
        db = await get_db()
        try:
            await db.execute("SELECT 1")
            db_ok = True
        finally:
            await db.close()
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "version": "1.0.0",
        "database": "ok" if db_ok else "error",
    }


# Debug endpoint to check if frontend assets are configured correctly
@app.get("/api/v1/debug/assets-info", tags=["Debug"])
async def assets_info():
    """Debug endpoint to check frontend assets configuration."""
    # Check if assets dir was mounted
    _assets_dir_path = None
    _assets_mounted = False
    if not _DEV_MODE and _FRONTEND_DIST.is_dir():
        _assets_dir_path = _FRONTEND_DIST / "assets"
        _assets_mounted = _assets_dir_path.exists()
    
    return {
        "frontend_dist": str(_FRONTEND_DIST),
        "frontend_dist_exists": _FRONTEND_DIST.exists(),
        "frontend_dist_is_dir": _FRONTEND_DIST.is_dir() if _FRONTEND_DIST.exists() else False,
        "assets_dir": str(_assets_dir_path) if _assets_dir_path else "not configured",
        "assets_mounted": _assets_mounted,
        "dev_mode": _DEV_MODE,
    }


@app.get("/api/v1/metrics", tags=["System"])
async def prometheus_metrics():
    """Prometheus /metrics endpoint returning OpenMetrics text format.

    Exposes:
        http_requests_total, http_request_duration_seconds,
        http_requests_in_flight, and any process-level metrics from
        the prometheus_client library.
    """
    return await metrics_endpoint()


# ── Serve the built frontend (SPA) from the same origin ──────────────
# Resolve the frontend dist directory. It can be overridden via the
# FRONTEND_DIST env var (used by the Docker image) and defaults to
# ../frontend/dist relative to this file (bare-metal `make run`).
#
# When DEV_MODE=true (set by `make dev-backend`), we skip serving the
# frontend so that the Vite dev server on :5173 handles it with hot-reload.
_DEV_MODE = os.getenv("DEV_MODE", "").lower() in ("1", "true", "yes")
_DIST_ENV = os.getenv("FRONTEND_DIST")

if getattr(sys, "frozen", False):
    # Running as a PyInstaller single-file bundle: frontend/dist is
    # embedded via --add-data and unpacked into sys._MEIPASS at runtime.
    _FRONTEND_DIST = Path(sys._MEIPASS) / "frontend" / "dist"
elif _DIST_ENV:
    _FRONTEND_DIST = Path(_DIST_ENV).resolve()
else:
    _FRONTEND_DIST = (
        Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    )

if not _DEV_MODE and _FRONTEND_DIST.is_dir():
    # Mount static assets (js/css/images) at /assets.
    _ASSETS_DIR = _FRONTEND_DIST / "assets"
    if _ASSETS_DIR.is_dir():
        # Use StaticFiles with check_dir=False for better compatibility
        app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR), check_dir=False), name="assets")
        print(f"[StaticFiles] Mounted /assets at {_ASSETS_DIR}")
    else:
        print(f"[StaticFiles] WARNING: assets directory not found at {_ASSETS_DIR}")

    _INDEX_HTML = _FRONTEND_DIST / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """Catch-all that serves index.html for any non-API path.

        This implements client-side routing: visiting /dashboard,
        /wizards/W01, etc. returns the SPA shell which then renders the
        matching route. Real files under /assets are handled by the
        StaticFiles mount above and never reach this handler.
        """
        # Never shadow API / WebSocket / docs routes.
        if full_path.startswith(("api/", "ws/")):
            return {"detail": "Not Found"}
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_INDEX_HTML))
else:
    # No built frontend present, or DEV_MODE=true.
    # Surface a helpful message instead of 404'ing every request.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def _no_frontend(full_path: str):
        if full_path.startswith(("api/", "ws/")):
            return {"detail": "Not Found"}
        if _DEV_MODE:
            return {
                "detail": (
                    "Backend-only dev mode. Frontend is served by Vite on "
                    "http://localhost:5173 (run `make dev-frontend` in another terminal)."
                )
            }
        return {
            "detail": (
                "Frontend build not found. Run `make build-frontend` "
                f"(expected at {_FRONTEND_DIST})."
            )
        }

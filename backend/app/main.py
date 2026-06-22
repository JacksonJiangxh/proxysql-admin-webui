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
    config_diff, clusters, templates,
)
from app.api.v1 import settings as settings_api
from app.middleware.csrf import CSRFMiddleware
from app.middleware.audit import AuditMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.cache_headers import CacheHeadersMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB on startup."""
    await init_db()
    yield


app = FastAPI(
    title="ProxySQL Admin WebUI",
    description="Web-based management interface for ProxySQL",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS (only relevant for the Vite dev server on :5173; in production the
# frontend is served same-origin and CORS is a no-op).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression: reduces response size for text-based content (JSON, HTML, CSS, JS).
# Only compresses responses > 500 bytes to avoid overhead on tiny payloads.
app.add_middleware(
    GZipMiddleware,
    minimum_size=500,
)

# Cache headers: adds ETag and Cache-Control headers for browser/CDN caching.
# Must be added after other middlewares to see the final response body for ETag.
app.add_middleware(CacheHeadersMiddleware)

# Security headers: adds CSP, HSTS, X-Frame-Options, and other security headers
app.add_middleware(SecurityHeadersMiddleware)

# Security middlewares (order: AuditMiddleware first, then CSRFMiddleware)
# This ensures CSRF checks run before audit logging captures the request
app.add_middleware(AuditMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(RateLimitMiddleware)

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

# WebSocket routes (per TECHNICAL_DOCUMENTATION: /ws/dashboard/{server_id})
app.include_router(dashboard.ws_router, prefix="/ws/dashboard", tags=["Dashboard WS"])


@app.get("/api/v1/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}


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
        app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="assets")

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

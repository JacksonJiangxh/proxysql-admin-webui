"""Audit logging middleware - records all API operations to audit_logs table.

Implemented as pure ASGI middleware (not BaseHTTPMiddleware) to avoid the
Starlette BaseHTTPMiddleware bug where HTTPException inside a TaskGroup
gets swallowed and converted to 500.
"""
import json
import uuid
from fastapi import Request

from app.database import get_db


# Paths that should not be logged
AUDIT_EXEMPT_PATHS = {
    "/api/v1/health",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/docs",
    "/api/openapi.json",
    "/ws/",
}


class AuditMiddleware:
    """Middleware that logs all mutating API operations to the audit_logs table."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        method = request.method
        path = request.url.path.rstrip("/")

        # Skip exempt paths
        if any(path.startswith(p) for p in AUDIT_EXEMPT_PATHS):
            await self.app(scope, receive, send)
            return

        # Determine if this is a state-changing operation
        is_write = method in ("POST", "PUT", "PATCH", "DELETE")
        is_read = method == "GET" and not any(
            path.startswith(p) for p in ("/api/v1/settings", "/api/v1/users")
        )

        # Skip routine read operations
        if is_read:
            await self.app(scope, receive, send)
            return

        # Extract user info if available (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        username = getattr(request.state, "username", None)

        # Extract client IP
        client_ip = self._get_client_ip(request)

        # Generate request ID for correlation
        request_id = str(uuid.uuid4())[:8]

        # Store request_id in state for access by route handlers
        request.state.request_id = request_id

        # Determine the action from HTTP method and path
        action = self._determine_action(method, path)
        resource = self._determine_resource(path)

        # Capture response status code via send wrapper
        status_code = [200]  # mutable container

        async def _send(message):
            if message["type"] == "http.response.start":
                status_code[0] = message.get("status", 200)
            await send(message)

        await self.app(scope, receive, _send)

        # Log to database (fire-and-forget, never break the app)
        try:
            db = await get_db()
            try:
                await db.execute(
                    """INSERT INTO audit_logs
                       (user_id, username, server_id, action, resource, details, ip_address)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user_id,
                        username,
                        getattr(request.state, "server_id", None),
                        action,
                        resource,
                        json.dumps({
                            "method": method,
                            "path": path,
                            "status_code": status_code[0],
                            "request_id": request_id,
                        }),
                        client_ip,
                    ),
                )
                await db.commit()
            finally:
                await db.close()
        except Exception:
            # Audit logging should never break the application
            pass

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP, considering proxies."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        if request.client:
            return request.client.host
        return "unknown"

    def _determine_action(self, method: str, path: str) -> str:
        """Map HTTP method to audit action name."""
        action_map = {
            "POST": "create",
            "PUT": "update",
            "PATCH": "partial_update",
            "DELETE": "delete",
        }
        return action_map.get(method, method.lower())

    def _determine_resource(self, path: str) -> str:
        """Extract resource name from API path."""
        parts = path.split("/")
        for i, part in enumerate(parts):
            if part in ("api", "v1"):
                continue
            if part in ("execute", "preview", "history"):
                continue
            return part
        return path


async def audit_log(
    user_id: int,
    username: str,
    action: str,
    resource: str,
    details: dict,
    server_id: str = None,
    ip_address: str = None,
):
    """Programmatic audit logging function for use in route handlers.

    Use this when you need to log additional context that the middleware
    cannot capture (e.g., wizard execution details, query text).
    """
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO audit_logs
               (user_id, username, server_id, action, resource, details, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                username,
                server_id,
                action,
                resource,
                json.dumps(details),
                ip_address,
            ),
        )
        await db.commit()
    finally:
        await db.close()

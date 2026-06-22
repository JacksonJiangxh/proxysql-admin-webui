"""Audit logging middleware - records all API operations to audit_logs table."""
import json
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

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


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all mutating API operations to the audit_logs table."""

    async def dispatch(self, request: Request, call_next):
        """Process request and log audit trail for state-changing operations."""
        # Only audit mutating methods or specific read endpoints
        method = request.method
        path = request.url.path.rstrip("/")

        # Skip exempt paths
        if any(path.startswith(p) for p in AUDIT_EXEMPT_PATHS):
            return await call_next(request)

        # Determine if this is a state-changing operation
        is_write = method in ("POST", "PUT", "PATCH", "DELETE")
        is_read = method == "GET" and not any(
            path.startswith(p) for p in ("/api/v1/settings", "/api/v1/users")
        )

        # Skip routine read operations
        if is_read:
            return await call_next(request)

        # Extract user info if available (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        username = getattr(request.state, "username", None)

        # Extract client IP
        client_ip = self._get_client_ip(request)

        # Generate request ID for correlation
        request_id = str(uuid.uuid4())[:8]

        # Store request_id in state for access by route handlers
        request.state.request_id = request_id

        # Process the request
        response = await call_next(request)

        # Determine the action from HTTP method and path
        action = self._determine_action(method, path)
        resource = self._determine_resource(path)

        # Log to database
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
                            "status_code": response.status_code,
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

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP, considering proxies."""
        # Check X-Forwarded-For header first (for reverse proxy setups)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
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
        # Strip api prefix and extract resource
        parts = path.split("/")
        # /api/v1/users -> users
        # /api/v1/servers/test -> servers
        # /api/v1/wizards/execute -> wizards
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

"""Authentication middleware for JWT-based access control.

Simple JWT verification — this is an internal tool, no complex RBAC needed.
"""
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.utils.security import decode_token

security = HTTPBearer()

PUBLIC_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/health",
    "/api/docs",
    "/api/openapi.json",
}


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Extract current user from JWT token. Returns None for public paths."""
    path = request.url.path.rstrip("/")

    if path in PUBLIC_PATHS:
        return None

    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token. Please log in again.",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = {
        "id": int(user_id),
        "username": payload.get("username", ""),
        "role": payload.get("role", "viewer"),
    }
    return user

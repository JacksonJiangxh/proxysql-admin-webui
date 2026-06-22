"""Authentication middleware for JWT-based access control."""
from datetime import datetime, timezone

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, ExpiredSignatureError

from app.utils.security import decode_token, decode_token_with_error
from app.database import get_db

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
    """Extract current user from JWT token."""
    path = request.url.path.rstrip("/")

    if path in PUBLIC_PATHS:
        return None

    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token. Please refresh your token or log in again.",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload: missing user identifier")

    # Check if token is blacklisted (logout)
    from hashlib import sha256
    token_hash = sha256(credentials.credentials.encode()).hexdigest()
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT 1 FROM token_blacklist WHERE token_hash = ?",
            (token_hash,)
        )
        if await cursor.fetchone():
            raise HTTPException(
                status_code=401,
                detail="This token has been revoked. Please log in again.",
            )
    finally:
        await db.close()

    # Return basic user info from token (DB lookup happens in route handlers)
    user = {
        "id": int(user_id),
        "username": payload.get("username", ""),
        "role": payload.get("role", "viewer"),
    }
    request.state.user_id = user["id"]
    request.state.username = user["username"]
    return user


def require_role(*roles: str):
    """Dependency that checks if the current user has one of the required roles."""
    async def role_checker(user=Depends(get_current_user)):
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker

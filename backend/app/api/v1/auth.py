"""Authentication API endpoints."""
from fastapi import APIRouter, HTTPException, Depends, Request, Response

from app.database import get_db
from app.models import (
    UserLogin, TokenResponse, User, PasswordChange,
)
from app.utils.security import (
    verify_password, hash_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.middleware import get_current_user
from app.config import settings

router = APIRouter()


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Attach the refresh token as an httpOnly cookie."""
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh_token cookie."""
    response.delete_cookie(
        key="refresh_token",
        path="/",
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, request: Request):
    """Authenticate user and return JWT tokens."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1",
            (credentials.username,)
        )
        user_row = await cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_dict = dict(user_row)
        if not verify_password(credentials.password, user_dict["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Create tokens
        token_data = {
            "sub": str(user_dict["id"]),
            "username": user_dict["username"],
            "role": user_dict["role"],
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Store refresh token hash in DB (for revocation / rotation)
        from hashlib import sha256
        from datetime import datetime, timedelta, timezone

        token_hash = sha256(refresh_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await db.execute(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (user_dict["id"], token_hash, expires_at)
        )

        # Update last login
        await db.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user_dict["id"],)
        )
        await db.commit()

        # Build response so we can set the cookie
        from fastapi.responses import JSONResponse
        resp = JSONResponse(content={
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": user_dict["id"],
                "username": user_dict["username"],
                "email": user_dict["email"],
                "role": user_dict["role"],
                "is_active": bool(user_dict["is_active"]),
                "created_at": user_dict["created_at"],
                "last_login": user_dict["last_login"],
            },
        })
        _set_refresh_cookie(resp, refresh_token)
        return resp
    finally:
        await db.close()


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
):
    """Refresh an access token using the refresh token from the httpOnly cookie.

    The refresh token is read from the ``refresh_token`` cookie (set by
    ``/login``), NOT from the request body, to keep it inaccessible to JS.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token cookie missing")

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = await get_db()
    try:
        # Verify refresh token exists in DB
        from hashlib import sha256
        token_hash = sha256(refresh_token.encode()).hexdigest()
        cursor = await db.execute(
            "SELECT * FROM refresh_tokens WHERE token_hash = ? AND expires_at > CURRENT_TIMESTAMP",
            (token_hash,)
        )
        stored = await cursor.fetchone()
        if not stored:
            raise HTTPException(status_code=401, detail="Refresh token revoked or expired")

        # Get user
        cursor = await db.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (int(user_id),))
        user_row = await cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=401, detail="User not found")

        user_dict = dict(user_row)

        # Rotate tokens: delete old, create new
        await db.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,))

        token_data = {
            "sub": str(user_dict["id"]),
            "username": user_dict["username"],
            "role": user_dict["role"],
        }
        new_access = create_access_token(token_data)
        new_refresh = create_refresh_token(token_data)

        new_hash = sha256(new_refresh.encode()).hexdigest()
        from datetime import datetime, timedelta, timezone
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await db.execute(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (user_dict["id"], new_hash, expires_at)
        )
        await db.commit()

        # Set the new refresh token as a cookie on the response
        _set_refresh_cookie(response, new_refresh)

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,   # also in body for backwards compat
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=User(
                id=user_dict["id"],
                username=user_dict["username"],
                email=user_dict["email"],
                role=user_dict["role"],
                is_active=bool(user_dict["is_active"]),
                created_at=user_dict["created_at"],
                last_login=user_dict["last_login"],
            ),
        )
    finally:
        await db.close()


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    user=Depends(get_current_user),
):
    """Logout: revoke refresh token and clear cookie."""
    db = await get_db()
    try:
        from hashlib import sha256

        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            token_hash = sha256(refresh_token.encode()).hexdigest()
            await db.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,))
        await db.commit()
    finally:
        await db.close()

    _clear_refresh_cookie(response)
    return {"ok": True, "message": "Logged out"}


@router.get("/me", response_model=User)
async def get_me(user=Depends(get_current_user)):
    """Get current user info."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user["id"],))
        user_row = await cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")
        u = dict(user_row)
        return User(
            id=u["id"], username=u["username"], email=u["email"],
            role=u["role"], is_active=bool(u["is_active"]),
            created_at=u["created_at"], last_login=u["last_login"],
        )
    finally:
        await db.close()


@router.put("/password")
async def change_password(
    data: PasswordChange,
    user=Depends(get_current_user),
):
    """Change current user's password."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if len(data.new_password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    db = await get_db()
    try:
        cursor = await db.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        if not verify_password(data.old_password, row[0]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        new_hash = hash_password(data.new_password)
        await db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
        await db.commit()
    finally:
        await db.close()

    return {"ok": True, "message": "Password changed successfully"}

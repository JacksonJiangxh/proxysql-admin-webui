"""Authentication API endpoints."""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.database import get_db
from app.models import (
    UserLogin, TokenResponse, User, PasswordChange,
)
from app.utils.security import (
    verify_password, hash_password, constant_time_compare,
    create_access_token, create_refresh_token, decode_token,
)
from app.middleware import security, get_current_user
from app.middleware.rate_limit import login_rate_limiter

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    _rate=Depends(login_rate_limiter),
):
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

        # Store refresh token
        from hashlib import sha256
        from datetime import datetime, timedelta, timezone
        from app.config import settings

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

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
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


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Refresh an access token using a refresh token."""
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = await get_db()
    try:
        # Verify refresh token exists in DB
        from hashlib import sha256
        token_hash = sha256(credentials.credentials.encode()).hexdigest()
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
        from app.config import settings
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await db.execute(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (user_dict["id"], new_hash, expires_at)
        )
        await db.commit()

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
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
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user=Depends(get_current_user),
):
    """Logout: revoke refresh token and blacklist access token."""
    if user is None:
        return {"ok": True, "message": "Logged out"}

    db = await get_db()
    try:
        from hashlib import sha256
        from datetime import datetime, timedelta, timezone

        # Revoke the refresh token (if this is a refresh token)
        token_hash = sha256(credentials.credentials.encode()).hexdigest()
        await db.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,))

        # Blacklist the current access token
        # Extract access token from Authorization header
        from app.utils.security import decode_token
        auth_header = credentials.credentials
        payload = decode_token(auth_header)
        if payload and payload.get("type") == "access":
            access_hash = sha256(auth_header.encode()).hexdigest()
            # Blacklist until token's natural expiry
            exp = payload.get("exp")
            if exp:
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).replace(tzinfo=None)
            else:
                expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
            await db.execute(
                "INSERT OR IGNORE INTO token_blacklist (token_hash, expires_at) VALUES (?, ?)",
                (access_hash, expires_at)
            )

        await db.commit()
    finally:
        await db.close()

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

    # Validate new password against policy
    from app.utils.password_policy import validate_password, PasswordValidationError
    try:
        validate_password(data.new_password)
    except PasswordValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

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

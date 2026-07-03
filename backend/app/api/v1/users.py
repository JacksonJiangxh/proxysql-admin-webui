"""User management API endpoints."""
from fastapi import APIRouter, HTTPException, Depends

from app.database import get_db
from app.models import UserCreate, UserUpdate, User, UserRole
from app.utils.security import hash_password
from app.middleware import get_current_user

router = APIRouter()


@router.get("", response_model=list[User])
async def list_users(user=Depends(get_current_user)):
    """List all users."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users ORDER BY id")
        rows = await cursor.fetchall()
        return [
            User(
                id=r["id"], username=r["username"], email=r["email"],
                role=r["role"], is_active=bool(r["is_active"]),
                created_at=r["created_at"], last_login=r["last_login"],
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.post("", response_model=User)
async def create_user(data: UserCreate, user=Depends(get_current_user)):
    """Create a new user."""
    if len(data.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    db = await get_db()
    try:
        # Check username uniqueness
        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (data.username,))
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail="Username already exists")

        hashed = hash_password(data.password)
        cursor = await db.execute(
            "INSERT INTO users (username, password_hash, email, role) VALUES (?, ?, ?, ?)",
            (data.username, hashed, data.email, data.role.value)
        )
        await db.commit()
        new_id = cursor.lastrowid

        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (new_id,))
        row = await cursor.fetchone()
        r = dict(row)
        return User(
            id=r["id"], username=r["username"], email=r["email"],
            role=r["role"], is_active=bool(r["is_active"]),
            created_at=r["created_at"], last_login=r["last_login"],
        )
    finally:
        await db.close()


@router.get("/{user_id}", response_model=User)
async def get_user(user_id: int, user=Depends(get_current_user)):
    """Get user details."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        r = dict(row)
        return User(
            id=r["id"], username=r["username"], email=r["email"],
            role=r["role"], is_active=bool(r["is_active"]),
            created_at=r["created_at"], last_login=r["last_login"],
        )
    finally:
        await db.close()


@router.put("/{user_id}", response_model=User)
async def update_user(user_id: int, data: UserUpdate, user=Depends(get_current_user)):
    """Update user."""
    db = await get_db()
    try:
        updates = {}
        if data.email is not None:
            updates["email"] = data.email
        if data.role is not None:
            updates["role"] = data.role.value
        if data.is_active is not None:
            updates["is_active"] = 1 if data.is_active else 0

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [user_id]
            await db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
            await db.commit()

        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        r = dict(row)
        return User(
            id=r["id"], username=r["username"], email=r["email"],
            role=r["role"], is_active=bool(r["is_active"]),
            created_at=r["created_at"], last_login=r["last_login"],
        )
    finally:
        await db.close()


@router.delete("/{user_id}")
async def delete_user(user_id: int, user=Depends(get_current_user)):
    """Delete a user."""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
    finally:
        await db.close()
    return {"ok": True, "message": "User deleted"}

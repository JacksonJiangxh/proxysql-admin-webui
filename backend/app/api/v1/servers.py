"""Server (ProxySQL instance) management API endpoints."""
import asyncio
import uuid
from fastapi import APIRouter, HTTPException, Depends

from app.database import get_db
from app.models import ServerConfigCreate, ServerConfigUpdate, ServerConfig
from app.utils.security import encrypt_credential, decrypt_credential
from app.middleware import get_current_user
from app.services.proxysql import CONNECT_TIMEOUT

router = APIRouter()


@router.get("", response_model=list[ServerConfig])
async def list_servers(user=Depends(get_current_user)):
    """List all configured ProxySQL servers."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM server_configs ORDER BY is_default DESC, name")
        rows = await cursor.fetchall()
        return [
            ServerConfig(
                id=r["id"], name=r["name"], host=r["host"], port=r["port"],
                admin_user=r["admin_user"], is_default=bool(r["is_default"]),
                hide_tables=r["hide_tables"],
                created_at=r["created_at"], updated_at=r["updated_at"],
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.post("", response_model=ServerConfig)
async def create_server(data: ServerConfigCreate, user=Depends(get_current_user)):
    """Add a new ProxySQL server instance."""
    db = await get_db()
    try:
        # Check name uniqueness
        cursor = await db.execute("SELECT id FROM server_configs WHERE name = ?", (data.name,))
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail="Server name already exists")

        server_id = str(uuid.uuid4())[:8]
        encrypted_pw = encrypt_credential(data.admin_password)

        await db.execute(
            """INSERT INTO server_configs (id, name, host, port, admin_user, admin_password_encrypted, is_default, hide_tables)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (server_id, data.name, data.host, data.port, data.admin_user, encrypted_pw,
             1 if data.is_default else 0, data.hide_tables)
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM server_configs WHERE id = ?", (server_id,))
        row = await cursor.fetchone()
        r = dict(row)
        return ServerConfig(
            id=r["id"], name=r["name"], host=r["host"], port=r["port"],
            admin_user=r["admin_user"], is_default=bool(r["is_default"]),
            hide_tables=r["hide_tables"],
            created_at=r["created_at"], updated_at=r["updated_at"],
        )
    finally:
        await db.close()


@router.get("/{server_id}", response_model=ServerConfig)
async def get_server(server_id: str, user=Depends(get_current_user)):
    """Get server details."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM server_configs WHERE id = ?", (server_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Server not found")
        r = dict(row)
        return ServerConfig(
            id=r["id"], name=r["name"], host=r["host"], port=r["port"],
            admin_user=r["admin_user"], is_default=bool(r["is_default"]),
            hide_tables=r["hide_tables"],
            created_at=r["created_at"], updated_at=r["updated_at"],
        )
    finally:
        await db.close()


@router.put("/{server_id}", response_model=ServerConfig)
async def update_server(server_id: str, data: ServerConfigUpdate, user=Depends(get_current_user)):
    """Update server configuration."""
    db = await get_db()
    try:
        updates = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.host is not None:
            updates["host"] = data.host
        if data.port is not None:
            updates["port"] = data.port
        if data.admin_user is not None:
            updates["admin_user"] = data.admin_user
        if data.admin_password is not None:
            updates["admin_password_encrypted"] = encrypt_credential(data.admin_password)
        if data.is_default is not None:
            updates["is_default"] = 1 if data.is_default else 0
        if data.hide_tables is not None:
            updates["hide_tables"] = data.hide_tables

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [server_id]
            await db.execute(
                f"UPDATE server_configs SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values
            )
            await db.commit()

        cursor = await db.execute("SELECT * FROM server_configs WHERE id = ?", (server_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Server not found")
        r = dict(row)
        return ServerConfig(
            id=r["id"], name=r["name"], host=r["host"], port=r["port"],
            admin_user=r["admin_user"], is_default=bool(r["is_default"]),
            hide_tables=r["hide_tables"],
            created_at=r["created_at"], updated_at=r["updated_at"],
        )
    finally:
        await db.close()


@router.delete("/{server_id}")
async def delete_server(server_id: str, user=Depends(get_current_user)):
    """Delete a server."""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM server_configs WHERE id = ?", (server_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Server not found")
    finally:
        await db.close()
    return {"ok": True, "message": "Server deleted"}


@router.post("/{server_id}/test")
async def test_connection(server_id: str, user=Depends(get_current_user)):
    """Test connection to a ProxySQL server."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM server_configs WHERE id = ?", (server_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Server not found")
        config = dict(row)
    finally:
        await db.close()

    # Connection test is outside the DB try/finally so that HTTPException
    # (e.g. 404) is not swallowed by the connection-error handler below.
    from app.services.proxysql import proxysql_service
    try:
        password = decrypt_credential(config["admin_password_encrypted"])
        result = await proxysql_service.execute_query(
            config["host"], config["port"], config["admin_user"], password,
            "SELECT 1 as test"
        )
        return {"ok": True, "message": "Connection successful", "data": result}
    except OSError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Connection refused or network error: {str(e)}"
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=502,
            detail=f"Connection timed out after {CONNECT_TIMEOUT}s"
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Connection failed: {type(e).__name__}: {str(e)}"
        )

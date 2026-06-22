"""Shared helpers for API route handlers."""
from fastapi import HTTPException

from app.database import get_db
from app.utils.security import decrypt_credential


async def get_proxysql_credentials(server_id: str) -> tuple[str, int, str, str]:
    """Look up a ProxySQL server config by id and return connection params.

    Returns:
        (host, port, admin_user, decrypted_password)

    Raises:
        HTTPException(404) if the server_id is not found.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM server_configs WHERE id = ?", (server_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Server '{server_id}' not found",
            )
        config = dict(row)
        password = decrypt_credential(config["admin_password_encrypted"])
        return config["host"], config["port"], config["admin_user"], password
    finally:
        await db.close()

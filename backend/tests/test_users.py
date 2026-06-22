"""Tests for user management."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


async def _get_admin_token(client):
    resp = await client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin"
    })
    return resp.json()["access_token"]


async def _get_auth_headers(client):
    """Return headers with Authorization + CSRF token for admin user."""
    token = await _get_admin_token(client)
    # Get CSRF token via a GET request to a non-exempt endpoint
    csrf_resp = await client.get(
        "/api/v1/servers",
        headers={"Authorization": f"Bearer {token}"}
    )
    csrf_token = csrf_resp.cookies.get("csrf_token")
    headers = {"Authorization": f"Bearer {token}"}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return headers


@pytest.mark.asyncio
async def test_list_users(setup_db):
    """Test listing users (admin only)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_admin_token(client)
        resp = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["username"] == "admin"


@pytest.mark.asyncio
async def test_create_user(setup_db):
    """Test creating a new user."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _get_auth_headers(client)
        resp = await client.post(
            "/api/v1/users",
            json={
                "username": "test_user",
                "password": "TestPass123!",
                "role": "viewer",
            },
            headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "test_user"
        assert data["role"] == "viewer"


@pytest.mark.asyncio
async def test_create_duplicate_user(setup_db):
    """Test creating a duplicate user."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _get_auth_headers(client)
        # First creation
        await client.post(
            "/api/v1/users",
            json={"username": "dup_user", "password": "DupPass123!", "role": "viewer"},
            headers=headers
        )
        # Refresh CSRF token after the first POST (CSRF token is rotated)
        headers = await _get_auth_headers(client)
        # Duplicate
        resp = await client.post(
            "/api/v1/users",
            json={"username": "dup_user", "password": "DupPass123!", "role": "viewer"},
            headers=headers
        )
        assert resp.status_code == 409

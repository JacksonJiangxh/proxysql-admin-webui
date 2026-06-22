"""Tests for the authentication system."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_login_success(setup_db):
    """Test successful login."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "admin"


@pytest.mark.asyncio
async def test_login_invalid_password(setup_db):
    """Test login with wrong password."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "wrong_password"
        })
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(setup_db):
    """Test login with non-existent user."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/login", json={
            "username": "nonexistent",
            "password": "password"
        })
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(setup_db):
    """Test getting current user info."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login first
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin"
        })
        token = resp.json()["access_token"]

        # Get current user
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_change_password(setup_db):
    """Test password change."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin"
        })
        token = resp.json()["access_token"]

        # Get CSRF token via a GET request to a non-exempt endpoint
        csrf_resp = await client.get(
            "/api/v1/servers",
            headers={"Authorization": f"Bearer {token}"}
        )
        csrf_token = csrf_resp.cookies.get("csrf_token")

        resp = await client.put(
            "/api/v1/auth/password",
            json={"old_password": "admin", "new_password": "NewPassword123!"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-CSRF-Token": csrf_token or "",
            }
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_check(setup_db):
    """Test health check endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

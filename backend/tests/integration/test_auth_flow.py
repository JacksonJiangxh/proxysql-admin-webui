"""Integration tests for the full authentication flow.

Covers: login → access protected route → token refresh → logout
Also tests: invalid login, expired token handling, and RBAC.
"""
import pytest
import time
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings


# ── CSRF helper ────────────────────────────────────

async def _get_csrf_token(client: AsyncClient, access_token: str) -> str | None:
    """Fetch a CSRF token by making a GET request to a non-exempt endpoint."""
    resp = await client.get("/api/v1/servers", headers={
        "Authorization": f"Bearer {access_token}"
    })
    return resp.cookies.get("csrf_token")


async def _auth_headers_for_token(client: AsyncClient, access_token: str) -> dict:
    """Build auth headers with CSRF token for a given access token."""
    csrf = await _get_csrf_token(client, access_token)
    headers = {"Authorization": f"Bearer {access_token}"}
    if csrf:
        headers["X-CSRF-Token"] = csrf
        client.cookies.set("csrf_token", csrf, domain="test")
    return headers


# ── Full auth flow ─────────────────────────────────

@pytest.mark.asyncio
async def test_full_auth_flow(setup_db):
    """Complete auth lifecycle: login → access protected route → refresh → logout."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # 1. Login
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin"
        })
        assert resp.status_code == 200
        tokens = resp.json()
        access_token = tokens["access_token"]
        # refresh_token is set as httpOnly cookie, not in response body
        refresh_token = resp.cookies.get("refresh_token")
        assert tokens["token_type"] == "bearer"
        assert tokens["user"]["username"] == "admin"
        assert tokens["user"]["role"] == "admin"
        assert tokens["expires_in"] > 0

        # 2. Access protected route
        resp = await client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {access_token}"
        })
        assert resp.status_code == 200
        me = resp.json()
        assert me["username"] == "admin"

        # 3. Refresh token (refresh token is in cookie, set by login response)
        import asyncio
        await asyncio.sleep(1.1)  # ensure different JWT timestamps
        resp = await client.post("/api/v1/auth/refresh", headers={
            "Authorization": f"Bearer {access_token}"
        })
        assert resp.status_code == 200
        new_tokens = resp.json()
        new_access = new_tokens["access_token"]
        new_refresh = new_tokens["refresh_token"]
        assert new_refresh != refresh_token  # refresh token rotation

        # Old access token should still work (not invalidated on refresh)
        resp = await client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {access_token}"
        })
        assert resp.status_code == 200

        # New access token should work too
        resp = await client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {new_access}"
        })
        assert resp.status_code == 200

        # 4. Logout — need CSRF token
        logout_headers = await _auth_headers_for_token(client, new_access)
        resp = await client.post("/api/v1/auth/logout", headers=logout_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # 5. Access token should be revoked after logout
        resp = await client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {new_access}"
        })
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_login(setup_db):
    """Test various invalid login scenarios."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # Wrong password
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "wrong_password"
        })
        assert resp.status_code == 401

        # Non-existent user
        resp = await client.post("/api/v1/auth/login", json={
            "username": "nonexistent_user", "password": "password"
        })
        assert resp.status_code == 401

        # Missing password field
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin"
        })
        assert resp.status_code == 422

        # Empty body
        resp = await client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_expired_token_handling(setup_db, monkeypatch):
    """Test that expired tokens are rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # Login normally
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin"
        })
        assert resp.status_code == 200
        access_token = resp.json()["access_token"]

        # Verify it works
        resp = await client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {access_token}"
        })
        assert resp.status_code == 200

        # Generate an expired token manually
        from datetime import datetime, timedelta, timezone
        from app.utils.security import create_access_token

        expired_token = create_access_token(
            {"sub": "1", "username": "admin", "role": "admin"},
            expires_delta=timedelta(seconds=-1),  # already expired
        )

        resp = await client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {expired_token}"
        })
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rbac_admin_full_access(setup_db, auth_headers, admin_token, test_app):
    """Admin role should have access to all endpoints."""
    # Admin can access users
    resp = await test_app.get("/api/v1/users", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200

    # Admin can access servers
    resp = await test_app.get("/api/v1/servers", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200

    # Admin can access settings
    resp = await test_app.get("/api/v1/settings", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code in (200, 404)  # settings may or may not exist yet


@pytest.mark.asyncio
async def test_rbac_operator_access(setup_db, operator_token, test_app, auth_headers, test_server_id):
    """Operator role should have limited access."""
    # Build headers with CSRF token for the operator
    op_headers = await _auth_headers_for_token(test_app, operator_token)

    # Operator can read servers
    resp = await test_app.get("/api/v1/servers", headers={
        "Authorization": f"Bearer {operator_token}"
    })
    assert resp.status_code == 200

    # Operator can access wizards
    resp = await test_app.get("/api/v1/wizards/definitions", headers={
        "Authorization": f"Bearer {operator_token}"
    })
    assert resp.status_code == 200

    # Operator cannot manage users (admin-only)
    resp = await test_app.get("/api/v1/users", headers={
        "Authorization": f"Bearer {operator_token}"
    })
    assert resp.status_code == 403

    # Operator cannot create servers (admin-only)
    resp = await test_app.post("/api/v1/servers", json={
        "name": "operator-test-server",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "admin",
        "admin_password": "admin",
    }, headers=op_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rbac_viewer_readonly(setup_db, viewer_token, test_app, test_server_id):
    """Viewer role should have read-only access."""
    # Build headers with CSRF token for the viewer
    vw_headers = await _auth_headers_for_token(test_app, viewer_token)

    # Viewer can read servers
    resp = await test_app.get("/api/v1/servers", headers={
        "Authorization": f"Bearer {viewer_token}"
    })
    assert resp.status_code == 200

    # Viewer can read wizard definitions
    resp = await test_app.get("/api/v1/wizards/definitions", headers={
        "Authorization": f"Bearer {viewer_token}"
    })
    assert resp.status_code == 200

    # Viewer cannot create servers
    resp = await test_app.post("/api/v1/servers", json={
        "name": "viewer-test-server",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "admin",
        "admin_password": "admin",
    }, headers=vw_headers)
    assert resp.status_code == 403

    # Viewer cannot access users
    resp = await test_app.get("/api/v1/users", headers={
        "Authorization": f"Bearer {viewer_token}"
    })
    assert resp.status_code == 403

    # Viewer cannot delete servers
    resp = await test_app.delete(f"/api/v1/servers/{test_server_id}", headers=vw_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthorized_access_no_token(setup_db):
    """Test that protected endpoints reject requests without any token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        endpoints = [
            ("GET", "/api/v1/servers"),
            ("GET", "/api/v1/users"),
            ("GET", "/api/v1/wizards/definitions"),
            ("GET", "/api/v1/auth/me"),
        ]

        for method, path in endpoints:
            if method == "GET":
                resp = await client.get(path)
            else:
                resp = await client.post(path, json={})
            assert resp.status_code in (401, 403), f"{method} {path} should require auth"


@pytest.mark.asyncio
async def test_password_change_flow(setup_db):
    """Test the complete password change flow."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # Login
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin"
        })
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        # Get CSRF token
        csrf = await _get_csrf_token(client, token)

        # Change password
        resp = await client.put("/api/v1/auth/password", json={
            "old_password": "admin",
            "new_password": "NewSecurePass1!",
        }, headers={
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": csrf or "",
        })
        assert resp.status_code == 200, f"Password change failed: {resp.text}"

        # Old password should fail
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin"
        })
        assert resp.status_code == 401

        # New password should work
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "NewSecurePass1!"
        })
        assert resp.status_code == 200

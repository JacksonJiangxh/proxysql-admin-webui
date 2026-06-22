"""Integration tests for API endpoints (table, query, dashboard, servers)."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app


async def _get_csrf_token(client):
    """Fetch a CSRF token by making a GET request to a non-exempt path.
    The CSRF middleware sets the csrf_token cookie on GET responses
    for paths that are not in the exempt list."""
    # Login first to get a token (login is CSRF-exempt)
    resp = await client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin"
    })
    token = resp.json()["access_token"]
    # Now make a GET request to a non-exempt path to get CSRF cookie
    resp = await client.get("/api/v1/servers", headers={
        "Authorization": f"Bearer {token}"
    })
    return token, resp.cookies.get("csrf_token")


async def _get_admin_token(client):
    """Login and return admin access token."""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin"
    })
    return resp.json()["access_token"]


async def _auth_headers(client):
    """Return headers with both Authorization and CSRF token."""
    token, csrf = await _get_csrf_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    if csrf:
        headers["X-CSRF-Token"] = csrf
        client.cookies.set("csrf_token", csrf)
    return headers


# ── Table Browser API ──────────────────────────────

@pytest.mark.asyncio
async def test_tables_list_requires_auth(setup_db):
    """Test that table list endpoint requires authentication."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/default/tables")
        assert resp.status_code in (401, 403, 404)


@pytest.mark.asyncio
async def test_tables_schema_endpoint(setup_db):
    """Test the schema endpoint (needs server config)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_admin_token(client)
        # Without a valid server, this should return 404
        resp = await client.get(
            "/api/v1/nonexistent/tables/test_table/schema",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 404


# ── Query Console API ─────────────────────────────

@pytest.mark.asyncio
async def test_query_execute_requires_server(setup_db):
    """Test that query execution fails without valid server."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _auth_headers(client)
        resp = await client.post(
            "/api/v1/query/nonexistent/execute",
            json={"sql": "SELECT 1", "target": "admin"},
            headers=headers
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_query_schema_requires_server(setup_db):
    """Test query schema endpoint requires valid server."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_admin_token(client)
        resp = await client.get(
            "/api/v1/query/nonexistent/schema",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_query_history_empty(setup_db):
    """Test query history returns empty for a new user."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_admin_token(client)
        resp = await client.get(
            "/api/v1/query/default/history",
            headers={"Authorization": f"Bearer {token}"}
        )
        # May return 404 (no server) or 200 with empty history
        assert resp.status_code in (200, 404)


# ── Dashboard API ────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_snapshot_requires_server(setup_db):
    """Test dashboard snapshot requires valid server."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_admin_token(client)
        resp = await client.get(
            "/api/v1/dashboard/nonexistent/snapshot",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 404


# ── Servers Management API ───────────────────────

@pytest.mark.asyncio
async def test_list_servers_empty(setup_db):
    """Test listing servers returns empty list initially."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_admin_token(client)
        resp = await client.get(
            "/api/v1/servers",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_create_server(setup_db):
    """Test creating a new server configuration."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _auth_headers(client)
        resp = await client.post(
            "/api/v1/servers",
            json={
                "name": "test-proxysql",
                "host": "127.0.0.1",
                "port": 6032,
                "admin_user": "admin",
                "admin_password": "admin",
            },
            headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-proxysql"
        assert "id" in data


@pytest.mark.asyncio
async def test_create_duplicate_server(setup_db):
    """Test creating a server with duplicate name."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _auth_headers(client)
        # Create first
        await client.post(
            "/api/v1/servers",
            json={
                "name": "dup-server",
                "host": "127.0.0.1",
                "port": 6032,
                "admin_user": "admin",
                "admin_password": "admin",
            },
            headers=headers
        )
        # Create duplicate — refresh CSRF token after the first POST
        headers = await _auth_headers(client)
        resp = await client.post(
            "/api/v1/servers",
            json={
                "name": "dup-server",
                "host": "127.0.0.1",
                "port": 6032,
                "admin_user": "admin",
                "admin_password": "admin",
            },
            headers=headers
        )
        assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_nonexistent_server(setup_db):
    """Test deleting a non-existent server."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _auth_headers(client)
        resp = await client.delete(
            "/api/v1/servers/nonexistent",
            headers=headers
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_server_not_found(setup_db):
    """Test getting a non-existent server."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_admin_token(client)
        resp = await client.get(
            "/api/v1/servers/nonexistent",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_test_connection_nonexistent_server(setup_db):
    """Test connection test with non-existent server."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _auth_headers(client)
        resp = await client.post(
            "/api/v1/servers/nonexistent/test",
            headers=headers
        )
        # Should be 404 (server not found in DB)
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ── Wizards API ──────────────────────────────────

@pytest.mark.asyncio
async def test_wizards_definitions_endpoint(setup_db):
    """Test getting wizard definitions via API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_admin_token(client)
        resp = await client.get(
            "/api/v1/wizards/definitions",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "wizards" in data
        # The technical documentation catalog defines 63 wizards.
        assert len(data["wizards"]) == 63
        # Each definition must carry a status field so the frontend can tell
        # implemented wizards apart from planned stubs.
        statuses = {w["status"] for w in data["wizards"]}
        assert "implemented" in statuses


@pytest.mark.asyncio
async def test_wizards_get_single_definition(setup_db):
    """Test getting a single wizard definition."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_admin_token(client)
        resp = await client.get(
            "/api/v1/wizards/definitions/W01",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "W01"
        assert "fields" in data


@pytest.mark.asyncio
async def test_wizards_get_nonexistent_definition(setup_db):
    """Test getting a non-existent wizard definition."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_admin_token(client)
        resp = await client.get(
            "/api/v1/wizards/definitions/W99",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_wizards_preview_endpoint(setup_db):
    """Test wizard SQL preview via API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _auth_headers(client)
        resp = await client.post(
            "/api/v1/wizards/preview",
            json={
                "wizard_id": "W01",
                "server_id": "dummy",
                "fields": {
                    "hostgroup_id": 0,
                    "hostname": "10.0.0.1",
                    "port": 3306,
                },
            },
            headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert len(data["sql_preview"]) == 1
        assert "INSERT INTO mysql_servers" in data["sql_preview"][0]


@pytest.mark.asyncio
async def test_wizards_history_requires_server(setup_db):
    """Test wizard history returns empty or 404 for nonexistent server."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_admin_token(client)
        resp = await client.get(
            "/api/v1/wizards/history/nonexistent",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code in (200, 404)


# ── Auth API Additional Tests ────────────────────

@pytest.mark.asyncio
async def test_login_validation(setup_db):
    """Test login request validation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing password
        resp = await client.post("/api/v1/auth/login", json={"username": "admin"})
        assert resp.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_unauthorized_access(setup_db):
    """Test accessing protected endpoints without auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/users")
        assert resp.status_code in (401, 403)

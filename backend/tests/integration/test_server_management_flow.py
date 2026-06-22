"""Integration tests for the server management flow.

Tests: server CRUD, connection testing, duplicate detection, deletion.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


# ── Server CRUD ────────────────────────────────────

@pytest.mark.asyncio
async def test_create_server(setup_db, test_app, auth_headers):
    """Test creating a new server configuration."""
    resp = await test_app.post("/api/v1/servers", json={
        "name": "crud-test-server",
        "host": "192.168.1.100",
        "port": 6032,
        "admin_user": "admin",
        "admin_password": "secure_pass",
        "is_default": False,
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "crud-test-server"
    assert data["host"] == "192.168.1.100"
    assert data["port"] == 6032
    assert data["admin_user"] == "admin"
    assert data["is_default"] is False
    assert "id" in data
    assert "created_at" in data
    # Password should NOT be in response
    assert "admin_password" not in data


@pytest.mark.asyncio
async def test_list_servers(setup_db, test_app, auth_headers):
    """Test listing servers after creating one."""
    # Create a server
    await test_app.post("/api/v1/servers", json={
        "name": "list-test-server",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "admin",
        "admin_password": "admin",
    }, headers=auth_headers)

    resp = await test_app.get("/api/v1/servers", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(s["name"] == "list-test-server" for s in data)


@pytest.mark.asyncio
async def test_get_server(setup_db, test_app, auth_headers):
    """Test getting a specific server."""
    # Create
    resp = await test_app.post("/api/v1/servers", json={
        "name": "get-test-server",
        "host": "10.0.0.1",
        "port": 6032,
        "admin_user": "admin",
        "admin_password": "admin",
    }, headers=auth_headers)
    server_id = resp.json()["id"]

    # Get
    resp = await test_app.get(f"/api/v1/servers/{server_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == server_id
    assert data["name"] == "get-test-server"
    assert data["host"] == "10.0.0.1"


@pytest.mark.asyncio
async def test_update_server(setup_db, test_app, auth_headers, admin_token, refresh_csrf):
    """Test updating a server configuration."""
    # Create
    resp = await test_app.post("/api/v1/servers", json={
        "name": "update-test-server",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "admin",
        "admin_password": "admin",
    }, headers=auth_headers)
    server_id = resp.json()["id"]

    # Refresh CSRF token (rotated after the POST above)
    auth_headers = await refresh_csrf(test_app, admin_token)

    # Update
    resp = await test_app.put(f"/api/v1/servers/{server_id}", json={
        "name": "updated-server-name",
        "port": 6033,
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "updated-server-name"
    assert data["port"] == 6033


@pytest.mark.asyncio
async def test_delete_server(setup_db, test_app, auth_headers, admin_token, refresh_csrf):
    """Test deleting a server."""
    # Create
    resp = await test_app.post("/api/v1/servers", json={
        "name": "delete-test-server",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "admin",
        "admin_password": "admin",
    }, headers=auth_headers)
    server_id = resp.json()["id"]

    # Refresh CSRF token (rotated after the POST above)
    auth_headers = await refresh_csrf(test_app, admin_token)

    # Delete
    resp = await test_app.delete(f"/api/v1/servers/{server_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify gone
    resp = await test_app.get(f"/api/v1/servers/{server_id}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_duplicate_server(setup_db, test_app, auth_headers, admin_token, refresh_csrf):
    """Test creating a server with duplicate name returns 409."""
    resp = await test_app.post("/api/v1/servers", json={
        "name": "dup-server-name",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "admin",
        "admin_password": "admin",
    }, headers=auth_headers)
    assert resp.status_code == 200

    # Refresh CSRF token (rotated after the POST above)
    auth_headers = await refresh_csrf(test_app, admin_token)

    # Duplicate
    resp = await test_app.post("/api/v1/servers", json={
        "name": "dup-server-name",
        "host": "127.0.0.1",
        "port": 6033,
        "admin_user": "admin",
        "admin_password": "admin",
    }, headers=auth_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_nonexistent_server(setup_db, test_app, auth_headers):
    """Test getting a non-existent server returns 404."""
    resp = await test_app.get("/api/v1/servers/nonexistent", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_server(setup_db, test_app, auth_headers):
    """Test deleting a non-existent server returns 404."""
    resp = await test_app.delete("/api/v1/servers/nonexistent", headers=auth_headers)
    assert resp.status_code == 404


# ── Connection testing ─────────────────────────────

@pytest.mark.asyncio
async def test_test_connection_with_mock(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test connection testing with mocked ProxySQL."""
    from unittest.mock import AsyncMock
    from app.services import proxysql as proxysql_module

    mock_result = [{"test": 1}]
    mock_query = AsyncMock(return_value=mock_result)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)

    resp = await test_app.post(
        f"/api/v1/servers/{test_server_id}/test",
        headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "Connection successful" in data["message"]
    assert mock_query.called


@pytest.mark.asyncio
async def test_test_connection_failure(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test connection testing handles ProxySQL connection failure."""
    from app.services import proxysql as proxysql_module

    async def mock_query_error(*args, **kwargs):
        raise Exception("Connection refused")

    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query_error)

    resp = await test_app.post(
        f"/api/v1/servers/{test_server_id}/test",
        headers=auth_headers
    )
    assert resp.status_code == 502
    assert "Connection failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_test_connection_nonexistent_server(setup_db, test_app, auth_headers):
    """Test connection test with non-existent server returns 404."""
    resp = await test_app.post("/api/v1/servers/nonexistent/test", headers=auth_headers)
    assert resp.status_code == 404


# ── Server RBAC ────────────────────────────────────

@pytest.mark.asyncio
async def test_server_create_requires_admin(setup_db, test_app, operator_token):
    """Test that operator cannot create servers."""
    resp = await test_app.post("/api/v1/servers", json={
        "name": "op-server",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "admin",
        "admin_password": "admin",
    }, headers={"Authorization": f"Bearer {operator_token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_server_delete_requires_admin(setup_db, test_app, operator_token, test_server_id):
    """Test that operator cannot delete servers."""
    resp = await test_app.delete(f"/api/v1/servers/{test_server_id}", headers={
        "Authorization": f"Bearer {operator_token}"
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_server_test_connection_requires_admin(setup_db, test_app, operator_token, test_server_id):
    """Test that operator cannot test connections."""
    resp = await test_app.post(f"/api/v1/servers/{test_server_id}/test", headers={
        "Authorization": f"Bearer {operator_token}"
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_server_viewer_readonly(setup_db, test_app, viewer_token):
    """Test that viewer can list/read servers but not modify."""
    # List - works
    resp = await test_app.get("/api/v1/servers", headers={
        "Authorization": f"Bearer {viewer_token}"
    })
    assert resp.status_code == 200

    # Create - fails
    resp = await test_app.post("/api/v1/servers", json={
        "name": "viewer-server",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "admin",
        "admin_password": "admin",
    }, headers={"Authorization": f"Bearer {viewer_token}"})
    assert resp.status_code == 403


# ── Default server handling ────────────────────────

@pytest.mark.asyncio
async def test_set_default_server(setup_db, test_app, auth_headers):
    """Test creating and marking a server as default."""
    resp = await test_app.post("/api/v1/servers", json={
        "name": "default-server",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "admin",
        "admin_password": "admin",
        "is_default": True,
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_default"] is True

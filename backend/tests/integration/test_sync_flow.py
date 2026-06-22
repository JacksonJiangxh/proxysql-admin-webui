"""Integration tests for the configuration sync flow.

Tests: sync status, apply/save/discard/load operations — all with mocked ProxySQL.
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app


# ── Sync status ────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_status_with_mock(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test sync status retrieval with mocked ProxySQL tables."""
    from app.services import proxysql as proxysql_module

    # Mock SHOW TABLES
    mock_tables = [
        {"name": "mysql_servers"},
        {"name": "runtime_mysql_servers"},
        {"name": "mysql_users"},
        {"name": "runtime_mysql_users"},
    ]

    # Mock table data (identical = no unapplied changes)
    mock_data = [
        {"hostgroup_id": 0, "hostname": "10.0.0.1", "port": 3306},
    ]

    call_count = [0]

    async def mock_query(*args, **kwargs):
        call_count[0] += 1
        sql = args[4] if len(args) > 4 else ""
        if "SHOW TABLES" in sql:
            return mock_tables
        else:
            return mock_data

    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)

    resp = await test_app.get(f"/api/v1/sync/{test_server_id}/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["server_id"] == test_server_id
    assert "tables" in data
    assert "total_unapplied" in data
    assert "total_unsaved" in data


@pytest.mark.asyncio
async def test_sync_status_requires_auth(setup_db):
    """Test that sync status endpoint requires authentication."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/sync/nonexistent/status")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_sync_status_server_not_found(setup_db, test_app, auth_headers):
    """Test sync status with non-existent server returns 404."""
    resp = await test_app.get("/api/v1/sync/nonexistent/status", headers=auth_headers)
    assert resp.status_code == 404


# ── Apply ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_apply_with_mock(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test sync apply with mocked ProxySQL."""
    from app.services import proxysql as proxysql_module

    mock_tables = [
        {"name": "mysql_servers"},
        {"name": "runtime_mysql_servers"},
        {"name": "mysql_users"},
        {"name": "runtime_mysql_users"},
    ]
    mock_query = AsyncMock(return_value=mock_tables)
    mock_admin = AsyncMock(return_value=[{"result": "OK"}])

    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_admin_command", mock_admin)

    resp = await test_app.post(
        f"/api/v1/sync/{test_server_id}/apply",
        params={"tables": ["mysql_servers"]},
        headers=auth_headers
    )
    assert resp.status_code == 200, f"Apply failed: {resp.text}"
    data = resp.json()
    assert data["action"] == "apply"
    assert "results" in data
    assert mock_admin.called


@pytest.mark.asyncio
async def test_sync_apply_all_tables(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test sync apply with no tables specified (should apply all)."""
    from app.services import proxysql as proxysql_module

    mock_tables = [
        {"name": "mysql_servers"},
        {"name": "runtime_mysql_servers"},
        {"name": "mysql_users"},
        {"name": "runtime_mysql_users"},
    ]
    mock_query = AsyncMock(return_value=mock_tables)
    mock_admin = AsyncMock(return_value=[{"result": "OK"}])

    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_admin_command", mock_admin)

    resp = await test_app.post(
        f"/api/v1/sync/{test_server_id}/apply",
        headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "apply"
    assert data["total"] >= 1


# ── Save ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_save_with_mock(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test sync save with mocked ProxySQL."""
    from app.services import proxysql as proxysql_module

    mock_tables = [
        {"name": "mysql_servers"},
        {"name": "runtime_mysql_servers"},
    ]
    mock_query = AsyncMock(return_value=mock_tables)
    mock_admin = AsyncMock(return_value=[{"result": "OK"}])

    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_admin_command", mock_admin)

    resp = await test_app.post(
        f"/api/v1/sync/{test_server_id}/save",
        headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "save"
    assert "results" in data
    assert mock_admin.called


# ── Discard ────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_discard_with_mock(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test sync discard with mocked ProxySQL."""
    from app.services import proxysql as proxysql_module

    mock_tables = [
        {"name": "mysql_servers"},
        {"name": "runtime_mysql_servers"},
    ]
    mock_query = AsyncMock(return_value=mock_tables)
    mock_admin = AsyncMock(return_value=[{"result": "OK"}])

    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_admin_command", mock_admin)

    resp = await test_app.post(
        f"/api/v1/sync/{test_server_id}/discard",
        headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "discard"
    assert "results" in data


# ── Load ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_load_with_mock(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test sync load from disk with mocked ProxySQL."""
    from app.services import proxysql as proxysql_module

    mock_tables = [
        {"name": "mysql_servers"},
        {"name": "runtime_mysql_servers"},
    ]
    mock_query = AsyncMock(return_value=mock_tables)
    mock_admin = AsyncMock(return_value=[{"result": "OK"}])

    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_admin_command", mock_admin)

    resp = await test_app.post(
        f"/api/v1/sync/{test_server_id}/load",
        headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "load"
    assert "results" in data
    assert mock_admin.called


# ── Sync RBAC ──────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_requires_operator_role(setup_db, test_app, viewer_token, test_server_id):
    """Test that viewer cannot execute sync operations."""
    sync_actions = ["apply", "save", "discard", "load"]

    for action in sync_actions:
        resp = await test_app.post(
            f"/api/v1/sync/{test_server_id}/{action}",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        assert resp.status_code == 403, f"{action} should require operator role"


@pytest.mark.asyncio
async def test_sync_operator_can_execute(setup_db, test_app, operator_token, test_server_id, monkeypatch):
    """Test that operator can execute sync operations."""
    from app.services import proxysql as proxysql_module

    mock_tables = [{"name": "mysql_servers"}, {"name": "runtime_mysql_servers"}]
    mock_query = AsyncMock(return_value=mock_tables)
    mock_admin = AsyncMock(return_value=[{"result": "OK"}])

    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_admin_command", mock_admin)

    resp = await test_app.post(
        f"/api/v1/sync/{test_server_id}/apply",
        params={"tables": ["mysql_servers"]},
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert resp.status_code == 200, f"Operator apply failed: {resp.text}"


# ── Error handling ─────────────────────────────────

@pytest.mark.asyncio
async def test_sync_proxysql_connection_error(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test sync handles ProxySQL connection errors gracefully."""
    from app.services import proxysql as proxysql_module

    # Mock execute_admin_command to raise an error (sync_action wraps this in try/except)
    async def mock_admin_error(*args, **kwargs):
        raise ConnectionError("Connection refused")

    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_admin_command", mock_admin_error)

    # Also mock execute_query to return tables so it gets to the sync_action loop
    async def mock_query(*args, **kwargs):
        return [{"name": "mysql_servers"}, {"name": "runtime_mysql_servers"}]

    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)

    resp = await test_app.post(
        f"/api/v1/sync/{test_server_id}/apply",
        headers=auth_headers
    )
    # sync_action catches errors per-table and returns results with success=False
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["succeeded"] == 0
    assert data["failed"] == 1

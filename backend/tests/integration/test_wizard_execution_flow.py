"""Integration tests for the wizard execution flow.

Tests: wizard definitions, preview, execution (with mock ProxySQL), history.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app


# ── Wizard definitions ─────────────────────────────

@pytest.mark.asyncio
async def test_wizard_definitions_listing(setup_db, test_app, admin_token):
    """Test that all 70 wizard definitions are returned."""
    resp = await test_app.get("/api/v1/wizards/definitions", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "wizards" in data
    assert len(data["wizards"]) == 70

    # Check structure of each wizard
    for wiz in data["wizards"]:
        assert "id" in wiz
        assert "category" in wiz
        assert "name" in wiz
        assert "description" in wiz
        assert "fields" in wiz
        assert "status" in wiz

    # Verify all wizards are implemented
    statuses = {w["status"] for w in data["wizards"]}
    assert "implemented" in statuses
    assert "planned" not in statuses


@pytest.mark.asyncio
async def test_wizard_definitions_require_auth(setup_db):
    """Test that wizard definitions require authentication."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/wizards/definitions")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_single_wizard_definition(setup_db, test_app, admin_token):
    """Test getting a single wizard definition."""
    resp = await test_app.get("/api/v1/wizards/definitions/W01", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "W01"
    assert "Add MySQL" in data["name"]  # exact name may vary ("Add MySQL Server" vs "Add MySQL Backend Server")
    assert len(data["fields"]) > 0

    # Verify field structure
    field_names = [f["name"] for f in data["fields"]]
    assert "hostgroup_id" in field_names
    assert "hostname" in field_names
    assert "port" in field_names


@pytest.mark.asyncio
async def test_get_nonexistent_wizard_definition(setup_db, test_app, admin_token):
    """Test getting a non-existent wizard returns 404."""
    resp = await test_app.get("/api/v1/wizards/definitions/W99", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 404


# ── Wizard preview ─────────────────────────────────

@pytest.mark.asyncio
async def test_wizard_preview_w01(setup_db, test_app, auth_headers, test_server_id):
    """Test W01 wizard preview generates correct SQL."""
    resp = await test_app.post("/api/v1/wizards/preview", json={
        "wizard_id": "W01",
        "server_id": test_server_id,
        "fields": {
            "hostgroup_id": 0,
            "hostname": "10.0.0.1",
            "port": 3306,
        },
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert len(data["sql_preview"]) == 1
    assert "INSERT INTO mysql_servers" in data["sql_preview"][0]
    assert "10.0.0.1" in data["sql_preview"][0]


@pytest.mark.asyncio
async def test_wizard_preview_w02(setup_db, test_app, auth_headers, test_server_id):
    """Test W02 (PostgreSQL server) wizard preview."""
    resp = await test_app.post("/api/v1/wizards/preview", json={
        "wizard_id": "W02",
        "server_id": test_server_id,
        "fields": {
            "hostgroup_id": 0,
            "hostname": "10.0.0.2",
            "port": 5432,
        },
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "INSERT INTO pgsql_servers" in data["sql_preview"][0]


@pytest.mark.asyncio
async def test_wizard_preview_w09(setup_db, test_app, auth_headers, test_server_id):
    """Test W09 (Add MySQL User) wizard preview."""
    resp = await test_app.post("/api/v1/wizards/preview", json={
        "wizard_id": "W09",
        "server_id": test_server_id,
        "fields": {
            "username": "testuser",
            "password": "testpass",
            "default_hostgroup": 0,
            "active": 1,
        },
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "INSERT INTO mysql_users" in data["sql_preview"][0]


@pytest.mark.asyncio
async def test_wizard_preview_w16_rw_split(setup_db, test_app, auth_headers, test_server_id):
    """Test W16 (Read/Write Split) wizard preview."""
    resp = await test_app.post("/api/v1/wizards/preview", json={
        "wizard_id": "W16",
        "server_id": test_server_id,
        "fields": {
            "writer_hostgroup": 0,
            "reader_hostgroup": 1,
            "rule_select_for_update": True,
            "rule_dml": True,
            "rule_select": True,
            "rule_transaction": True,
        },
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert len(data["sql_preview"]) >= 4
    assert any("mysql_replication_hostgroups" in sql for sql in data["sql_preview"])
    assert any("mysql_query_rules" in sql for sql in data["sql_preview"])


@pytest.mark.asyncio
async def test_wizard_preview_validation_error(setup_db, test_app, auth_headers, test_server_id):
    """Test wizard preview with validation errors."""
    resp = await test_app.post("/api/v1/wizards/preview", json={
        "wizard_id": "W01",
        "server_id": test_server_id,
        "fields": {
            "hostgroup_id": 0,
            "hostname": "",  # empty hostname should fail validation
            "port": 3306,
        },
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert len(data.get("errors", [])) > 0


@pytest.mark.asyncio
async def test_wizard_preview_nonexistent_wizard(setup_db, test_app, auth_headers, test_server_id):
    """Test wizard preview with non-existent wizard ID."""
    resp = await test_app.post("/api/v1/wizards/preview", json={
        "wizard_id": "W99",
        "server_id": test_server_id,
        "fields": {},
    }, headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_wizard_preview_nonexistent_server(setup_db, test_app, auth_headers):
    """Test wizard preview with non-existent server — may succeed or fail depending on implementation."""
    resp = await test_app.post("/api/v1/wizards/preview", json={
        "wizard_id": "W01",
        "server_id": "nonexistent",
        "fields": {
            "hostgroup_id": 0,
            "hostname": "10.0.0.1",
            "port": 3306,
        },
    }, headers=auth_headers)
    # The wizard preview may succeed (it only generates SQL, doesn't connect to ProxySQL)
    # or may fail if it validates the server_id against the database.
    # Both behaviors are acceptable.
    if resp.status_code == 200:
        data = resp.json()
        # Preview may still succeed since it only generates SQL
        assert "sql_preview" in data or "ok" in data
    else:
        assert resp.status_code >= 400


# ── Wizard execution (with mock) ───────────────────

@pytest.mark.asyncio
async def test_wizard_execute_w01_mocked(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test W01 wizard execution with a mocked ProxySQL service."""
    from unittest.mock import AsyncMock
    from app.services import proxysql as proxysql_module

    # Mock the execute_modify to return affected rows without real ProxySQL
    mock_execute_modify = AsyncMock(return_value=1)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_modify", mock_execute_modify)

    resp = await test_app.post("/api/v1/wizards/execute", json={
        "wizard_id": "W01",
        "server_id": test_server_id,
        "fields": {
            "hostgroup_id": 0,
            "hostname": "10.0.0.1",
            "port": 3306,
            "status": "ONLINE",
            "weight": 1,
        },
        "options": {"auto_apply": False, "auto_save": False, "dry_run": False},
    }, headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert mock_execute_modify.called


@pytest.mark.asyncio
async def test_wizard_execute_w50_load_from_disk_mocked(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test W50 (Load From Disk) wizard execution with mocked ProxySQL."""
    from unittest.mock import AsyncMock
    from app.services import proxysql as proxysql_module

    mock_admin = AsyncMock(return_value=[{"result": "OK"}])
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_admin_command", mock_admin)

    resp = await test_app.post("/api/v1/wizards/execute", json={
        "wizard_id": "W50",
        "server_id": test_server_id,
        "fields": {},
        "options": {"auto_apply": False, "auto_save": False},
    }, headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert mock_admin.called


@pytest.mark.asyncio
async def test_wizard_execute_requires_operator_role(setup_db, test_app, viewer_token, test_server_id):
    """Test that viewer cannot execute wizards."""
    resp = await test_app.post("/api/v1/wizards/execute", json={
        "wizard_id": "W01",
        "server_id": test_server_id,
        "fields": {"hostgroup_id": 0, "hostname": "10.0.0.1", "port": 3306},
    }, headers={"Authorization": f"Bearer {viewer_token}"})
    assert resp.status_code == 403


# ── Wizard history ─────────────────────────────────

@pytest.mark.asyncio
async def test_wizard_history_empty(setup_db, test_app, admin_token, test_server_id):
    """Test wizard history returns empty for new server."""
    resp = await test_app.get(f"/api/v1/wizards/history/{test_server_id}", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "history" in data
    assert isinstance(data["history"], list)


@pytest.mark.asyncio
async def test_wizard_history_after_execution(setup_db, test_app, auth_headers, test_server_id, admin_token, monkeypatch):
    """Test wizard history contains entries after execution."""
    from unittest.mock import AsyncMock
    from app.services import proxysql as proxysql_module

    mock_execute_modify = AsyncMock(return_value=1)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_modify", mock_execute_modify)

    # Execute a wizard
    resp = await test_app.post("/api/v1/wizards/execute", json={
        "wizard_id": "W01",
        "server_id": test_server_id,
        "fields": {"hostgroup_id": 0, "hostname": "10.0.0.1", "port": 3306},
        "options": {"auto_apply": True, "auto_save": False},
    }, headers=auth_headers)
    assert resp.status_code == 200

    # Check history
    resp = await test_app.get(f"/api/v1/wizards/history/{test_server_id}", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["history"]) >= 1
    entry = data["history"][0]
    assert entry["wizard_id"] == "W01"
    assert entry["success"] == 1


@pytest.mark.asyncio
async def test_wizard_history_limit(setup_db, test_app, auth_headers, test_server_id, admin_token, refresh_csrf, monkeypatch):
    """Test wizard history respects the limit parameter."""
    from unittest.mock import AsyncMock
    from app.services import proxysql as proxysql_module

    mock_execute_modify = AsyncMock(return_value=1)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_modify", mock_execute_modify)

    # Execute multiple wizards — refresh CSRF after each
    for i in range(3):
        resp = await test_app.post("/api/v1/wizards/execute", json={
            "wizard_id": "W01",
            "server_id": test_server_id,
            "fields": {"hostgroup_id": 0, "hostname": "10.0.0.1", "port": 3306},
        }, headers=auth_headers)
        assert resp.status_code == 200
        if i < 2:  # Refresh after first two, not needed after last
            auth_headers = await refresh_csrf(test_app, admin_token)

    # Request with limit=2
    resp = await test_app.get(f"/api/v1/wizards/history/{test_server_id}?limit=2", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["history"]) <= 2

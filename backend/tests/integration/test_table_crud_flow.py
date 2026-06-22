"""Integration tests for table CRUD flow.

Tests: table listing, data retrieval with pagination, schema retrieval,
and inline row operations — all with mocked ProxySQL connections.
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app


# ── Table listing ──────────────────────────────────

@pytest.mark.asyncio
async def test_tables_list_requires_auth(setup_db):
    """Test that table list endpoint requires authentication."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/nonexistent/tables")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tables_list_with_mock(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test table listing with mocked ProxySQL response."""
    from app.services import proxysql as proxysql_module

    mock_tables = [
        {"name": "mysql_servers"},
        {"name": "mysql_users"},
        {"name": "mysql_query_rules"},
    ]
    mock_query = AsyncMock(return_value=mock_tables)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)

    resp = await test_app.get(f"/api/v1/{test_server_id}/tables", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["server_id"] == test_server_id
    assert "tables" in data
    assert len(data["tables"]) == 3
    assert "mysql_servers" in data["tables"]


@pytest.mark.asyncio
async def test_tables_list_server_not_found(setup_db, test_app, auth_headers):
    """Test table listing with non-existent server returns 404."""
    resp = await test_app.get("/api/v1/nonexistent/tables", headers=auth_headers)
    assert resp.status_code == 404


# ── Table data retrieval ───────────────────────────

@pytest.mark.asyncio
async def test_table_data_retrieval_with_pagination(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test table data retrieval with pagination using mocked ProxySQL."""
    from app.services import proxysql as proxysql_module

    # Mock schema columns
    mock_columns = [
        {"name": "hostgroup_id", "type": "INT"},
        {"name": "hostname", "type": "VARCHAR"},
        {"name": "port", "type": "INT"},
    ]

    # Mock data rows
    mock_rows = [
        {"hostgroup_id": 0, "hostname": "10.0.0.1", "port": 3306},
        {"hostgroup_id": 0, "hostname": "10.0.0.2", "port": 3306},
    ]

    # Mock count
    mock_count = [{"cnt": 2}]

    # Track calls to return different values
    call_count = [0]

    async def mock_query(*args, **kwargs):
        call_count[0] += 1
        sql = args[4] if len(args) > 4 else ""
        if "PRAGMA table_info" in sql:
            return mock_columns
        elif "COUNT(*)" in sql:
            return mock_count
        else:
            return mock_rows

    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)

    resp = await test_app.get(
        f"/api/v1/{test_server_id}/tables/mysql_servers?page=1&page_size=50",
        headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["table"] == "mysql_servers"
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 50
    assert len(data["rows"]) == 2
    assert "column_names" in data


@pytest.mark.asyncio
async def test_table_data_with_search(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test table data retrieval with search parameter."""
    from app.services import proxysql as proxysql_module

    mock_columns = [{"name": "hostname", "type": "VARCHAR"}]
    mock_count = [{"cnt": 1}]
    mock_rows = [{"hostname": "10.0.0.1"}]

    call_count = [0]

    async def mock_query(*args, **kwargs):
        call_count[0] += 1
        sql = args[4] if len(args) > 4 else ""
        if "PRAGMA table_info" in sql:
            return mock_columns
        elif "COUNT(*)" in sql:
            return mock_count
        else:
            return mock_rows

    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)

    resp = await test_app.get(
        f"/api/v1/{test_server_id}/tables/mysql_servers?search=10.0.0.1",
        headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_table_data_with_ordering(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test table data retrieval with order_by and order_dir."""
    from app.services import proxysql as proxysql_module

    mock_columns = [{"name": "port", "type": "INT"}]
    mock_count = [{"cnt": 2}]
    mock_rows = [{"port": 3306}, {"port": 3307}]

    call_count = [0]

    async def mock_query(*args, **kwargs):
        call_count[0] += 1
        sql = args[4] if len(args) > 4 else ""
        if "PRAGMA table_info" in sql:
            return mock_columns
        elif "COUNT(*)" in sql:
            return mock_count
        else:
            # Verify ORDER BY and DESC are in the SQL
            assert "ORDER BY" in sql
            assert "DESC" in sql
            return mock_rows

    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)

    resp = await test_app.get(
        f"/api/v1/{test_server_id}/tables/mysql_servers?order_by=port&order_dir=desc",
        headers=auth_headers
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_table_data_invalid_table_name(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test that invalid table names are rejected."""
    from app.services import proxysql as proxysql_module

    # Mock that returns no columns (bad table)
    mock_query = AsyncMock(return_value=[])
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)

    resp = await test_app.get(
        f"/api/v1/{test_server_id}/tables/;DROP TABLE users;--",
        headers=auth_headers
    )
    assert resp.status_code == 400


# ── Table schema ───────────────────────────────────

@pytest.mark.asyncio
async def test_table_schema_retrieval(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test table schema retrieval with mocked ProxySQL."""
    from app.services import proxysql as proxysql_module

    # The schema service calls execute_query with "SHOW CREATE TABLE main.mysql_servers"
    # and expects a result like [{"Create Table": "CREATE TABLE ..."}]
    create_sql = (
        "CREATE TABLE mysql_servers (\n"
        "  hostgroup_id INT NOT NULL DEFAULT 0,\n"
        "  hostname VARCHAR NOT NULL,\n"
        "  port INT NOT NULL DEFAULT 3306,\n"
        "  PRIMARY KEY (hostgroup_id, hostname, port)\n"
        ")"
    )
    mock_query = AsyncMock(return_value=[{"Create Table": create_sql}])
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_query", mock_query)

    resp = await test_app.get(
        f"/api/v1/{test_server_id}/tables/mysql_servers/schema",
        headers=auth_headers
    )
    assert resp.status_code == 200, f"Schema failed: {resp.text}"
    data = resp.json()
    assert "columns" in data
    assert len(data["columns"]) == 3
    assert data["columns"][0]["name"] == "hostgroup_id"


# ── Inline row operations ──────────────────────────

@pytest.mark.asyncio
async def test_inline_row_insert(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test inline row insert with mocked ProxySQL."""
    from app.services import proxysql as proxysql_module

    mock_modify = AsyncMock(return_value=1)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_modify", mock_modify)

    resp = await test_app.post(
        f"/api/v1/{test_server_id}/tables/mysql_servers/row",
        json={
            "hostgroup_id": 0,
            "hostname": "10.0.0.10",
            "port": 3306,
        },
        headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["affected_rows"] == 1
    assert mock_modify.called

    # Verify the SQL contains INSERT INTO
    call_args = mock_modify.call_args[0]
    sql = call_args[4]
    assert "INSERT INTO" in sql
    assert "mysql_servers" in sql


@pytest.mark.asyncio
async def test_inline_row_update(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test inline row update with mocked ProxySQL."""
    from app.services import proxysql as proxysql_module

    mock_modify = AsyncMock(return_value=1)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_modify", mock_modify)

    resp = await test_app.put(
        f"/api/v1/{test_server_id}/tables/mysql_servers/row",
        json={
            "pk_values": {"hostgroup_id": 0, "hostname": "10.0.0.1", "port": 3306},
            "data": {"status": "OFFLINE_SOFT", "weight": 0},
        },
        headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert mock_modify.called

    call_args = mock_modify.call_args[0]
    sql = call_args[4]
    assert "UPDATE" in sql
    assert "SET" in sql
    assert "WHERE" in sql


@pytest.mark.asyncio
async def test_inline_row_delete(setup_db, test_app, auth_headers, test_server_id, monkeypatch):
    """Test inline row delete with mocked ProxySQL."""
    from app.services import proxysql as proxysql_module

    mock_modify = AsyncMock(return_value=1)
    monkeypatch.setattr(proxysql_module.proxysql_service, "execute_modify", mock_modify)

    resp = await test_app.delete(
        f"/api/v1/{test_server_id}/tables/mysql_servers/row",
        params={"pk_values": '{"hostgroup_id": 0, "hostname": "10.0.0.1", "port": 3306}'},
        headers=auth_headers
    )
    assert resp.status_code in (200, 422)  # 422 if pk_values isn't parsed as JSON body

    # Try with JSON body instead
    resp = await test_app.request(
        "DELETE",
        f"/api/v1/{test_server_id}/tables/mysql_servers/row",
        json={
            "pk_values": {"hostgroup_id": 0, "hostname": "10.0.0.1", "port": 3306},
        },
        headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert mock_modify.called


@pytest.mark.asyncio
async def test_inline_row_insert_requires_operator(setup_db, test_app, viewer_token, test_server_id):
    """Test that viewer cannot insert rows."""
    resp = await test_app.post(
        f"/api/v1/{test_server_id}/tables/mysql_servers/row",
        json={"hostgroup_id": 0, "hostname": "10.0.0.1", "port": 3306},
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_table_operations_server_not_found(setup_db, test_app, auth_headers):
    """Test that table operations with non-existent server return 404."""
    # Table listing
    resp = await test_app.get("/api/v1/nonexistent/tables/mysql_servers", headers=auth_headers)
    assert resp.status_code == 404

    # Schema
    resp = await test_app.get("/api/v1/nonexistent/tables/mysql_servers/schema", headers=auth_headers)
    assert resp.status_code == 404

    # Row insert
    resp = await test_app.post(
        "/api/v1/nonexistent/tables/mysql_servers/row",
        json={"hostgroup_id": 0, "hostname": "10.0.0.1", "port": 3306},
        headers=auth_headers
    )
    assert resp.status_code == 404

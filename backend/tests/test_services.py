"""Tests for service layer components (unit tests without ProxySQL)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.query_engine import QueryEngine, QueryTarget
from app.services.dashboard_service import DashboardService
from app.services.sync_service import SyncService, SyncAction


class TestQueryEngine:
    """Tests for the multi-target SQL query engine."""

    def test_query_target_values(self):
        """Test QueryTarget enum values."""
        assert QueryTarget.ADMIN == "admin"
        assert QueryTarget.MYSQL_PROXY == "mysql"
        assert QueryTarget.PGSQL_PROXY == "pgsql"

    def test_allowed_admin_commands_pattern(self):
        """Test the admin command validation regex."""
        engine = QueryEngine()
        assert engine.ALLOWED_ADMIN_COMMANDS.match("LOAD MYSQL SERVERS TO RUNTIME")
        assert engine.ALLOWED_ADMIN_COMMANDS.match("SAVE MYSQL USERS TO DISK")
        assert engine.ALLOWED_ADMIN_COMMANDS.match("SELECT CONFIG")
        assert engine.ALLOWED_ADMIN_COMMANDS.match("  LOAD MYSQL SERVERS TO RUNTIME")
        assert not engine.ALLOWED_ADMIN_COMMANDS.match("DROP TABLE test")
        assert not engine.ALLOWED_ADMIN_COMMANDS.match("INSERT INTO test VALUES (1)")

    @pytest.mark.asyncio
    async def test_execute_admin_select(self):
        """Test admin SELECT query execution."""
        engine = QueryEngine()
        mock_rows = [{"id": 1, "name": "test"}]
        with patch.object(engine, '_execute_admin') as mock_exec:
            mock_exec.return_value = {
                "type": "select",
                "rows": mock_rows,
                "row_count": 1,
                "elapsed_ms": 5.0,
            }
            result = await engine.execute(
                "host", 6032, "user", "pass",
                "SELECT * FROM test",
                target=QueryTarget.ADMIN,
            )
            assert result["type"] == "select"
            assert result["row_count"] == 1

    @pytest.mark.asyncio
    async def test_execute_unsupported_target(self):
        """Test that unsupported targets raise error."""
        engine = QueryEngine()
        with pytest.raises(ValueError, match="Unsupported query target"):
            await engine.execute(
                "host", 6032, "user", "pass",
                "SELECT 1",
                target="unknown",
            )


class TestDashboardService:
    """Tests for the dashboard monitoring service."""

    def test_metrics_queries_defined(self):
        """Test that all expected metrics queries are defined."""
        service = DashboardService()
        expected = {"connections", "qps", "traffic", "memory", "hostgroups"}
        assert set(service.METRICS_QUERIES.keys()) == expected

    def test_metrics_queries_syntax(self):
        """Test that metric queries contain basic SQL keywords."""
        service = DashboardService()
        for name, query in service.METRICS_QUERIES.items():
            assert "SELECT" in query.upper(), f"{name} query missing SELECT"
            assert "FROM" in query.upper(), f"{name} query missing FROM"

    @pytest.mark.asyncio
    async def test_get_snapshot_error_handling(self):
        """Test that snapshot gracefully handles connection errors."""
        service = DashboardService()
        # Create a fresh service with a single test metric
        service.METRICS_QUERIES = {"test_metric": "SELECT 1"}
        with patch('app.services.proxysql.proxysql_service.execute_query',
                   side_effect=Exception("Connection refused")):
            snapshot = await service.get_snapshot(
                "host", 6032, "user", "pass"
            )
            assert "test_metric" in snapshot
            assert "timestamp" in snapshot
            assert "error" in snapshot["test_metric"]


class TestSyncService:
    """Tests for the three-layer config sync service."""

    def test_sync_action_enum(self):
        """Test sync action enum values."""
        assert SyncAction.APPLY.value == "apply"
        assert SyncAction.SAVE.value == "save"
        assert SyncAction.DISCARD.value == "discard"
        assert SyncAction.LOAD.value == "load"

    def test_config_modules_mapping(self):
        """Test config module name mapping."""
        service = SyncService()
        assert service.CONFIG_MODULES["mysql_servers"] == "MYSQL SERVERS"
        assert service.CONFIG_MODULES["mysql_users"] == "MYSQL USERS"
        assert service.CONFIG_MODULES["mysql_query_rules"] == "MYSQL QUERY RULES"
        assert service.CONFIG_MODULES["pgsql_servers"] == "PGSQL SERVERS"
        assert service.CONFIG_MODULES["proxysql_servers"] == "PROXYSQL SERVERS"
        assert service.CONFIG_MODULES["scheduler"] == "SCHEDULER"

    def test_sync_table_prefixes(self):
        """Test sync table prefix filtering."""
        service = SyncService()
        assert "mysql_" in service.SYNC_TABLE_PREFIXES
        assert "pgsql_" in service.SYNC_TABLE_PREFIXES
        assert "proxysql_" in service.SYNC_TABLE_PREFIXES
        assert "scheduler" in service.SYNC_TABLE_PREFIXES

    def test_sync_action_sql_templates(self):
        """Test sync action SQL templates are correct."""
        sql_templates = {
            SyncAction.APPLY: "LOAD {module} TO RUNTIME",
            SyncAction.SAVE: "SAVE {module} TO DISK",
            SyncAction.DISCARD: "LOAD {module} FROM RUNTIME",
            SyncAction.LOAD: "LOAD {module} FROM DISK",
        }
        assert "TO RUNTIME" in sql_templates[SyncAction.APPLY]
        assert "TO DISK" in sql_templates[SyncAction.SAVE]
        assert "FROM RUNTIME" in sql_templates[SyncAction.DISCARD]
        assert "FROM DISK" in sql_templates[SyncAction.LOAD]


class TestSchemaService:
    """Tests for the schema introspection service."""

    def test_parse_columns_empty_sql(self):
        """Test parsing columns from empty/malformed SQL."""
        from app.services.schema_service import SchemaService
        service = SchemaService()
        assert service._parse_columns("") == []
        assert service._parse_columns("CREATE TABLE") == []
        assert service._parse_columns("CREATE TABLE test ()") == []

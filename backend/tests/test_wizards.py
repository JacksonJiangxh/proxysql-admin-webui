"""Tests for wizard engine."""
import pytest
from app.services.wizard_engine import (
    WIZARD_REGISTRY,
    AddMysqlServerWizard,
    AddPgsqlServerWizard,
    AddMysqlUserWizard,
    EditMysqlServerWizard,
    ToggleMysqlServerStatusWizard,
    ChangeMysqlUserPasswordWizard,
    ToggleMysqlUserActiveWizard,
    ReadWriteSplitWizard,
    AddQueryRuleWizard,
    ReplicationHostgroupsWizard,
    ConfigSyncWizard,
    GlobalVariableUpdateWizard,
    LoadFromDiskWizard,
    ResetStatsWizard,
    WizardDefinition,
    WizardField,
)


# Total wizard count (W01-W70): 63 original + 7 delete wizards (W64-W70).
EXPECTED_TOTAL_WIZARDS = 70
# All 70 wizards (W01-W70) are now fully implemented.
IMPLEMENTED_WIZARDS = {f"W{i:02d}" for i in range(1, 71)}
# Wizards that legitimately need no user input (read-only or no-param wizards).
NO_FIELD_WIZARDS = {
    "W50", "W51", "W52",           # ops: load-from-disk, reset-stats, flush-cache
    "W55", "W57", "W58", "W59",    # monitoring: rule-hits, pool, processlist, user-conn
    "W60", "W61", "W62", "W63",    # monitoring: topology, global-status, gtid, cluster
}


def test_w01_add_mysql_server_validation():
    """Test W01 validation."""
    wizard = WIZARD_REGISTRY["W01"]

    # Valid fields
    errors = wizard.validate({
        "hostgroup_id": 0,
        "hostname": "10.0.0.1",
        "port": 3306,
        "status": "ONLINE",
        "weight": 1,
    })
    assert len(errors) == 0

    # Missing hostname
    errors = wizard.validate({
        "hostgroup_id": 0,
        "port": 3306,
    })
    assert len(errors) > 0

    # Invalid port
    errors = wizard.validate({
        "hostgroup_id": 0,
        "hostname": "10.0.0.1",
        "port": 99999,
    })
    assert len(errors) > 0


def test_w01_add_mysql_server_sql_generation():
    """Test W01 SQL generation."""
    wizard = WIZARD_REGISTRY["W01"]
    fields = {
        "hostgroup_id": 0,
        "hostname": "10.0.0.1",
        "port": 3306,
        "status": "ONLINE",
        "weight": 1,
        "max_connections": 1000,
        "max_replication_lag": 0,
        "use_ssl": 0,
        "max_latency_ms": 0,
        "comment": "Test server",
    }
    sqls = wizard.generate_sql(fields)
    assert len(sqls) == 1
    sql = sqls[0]
    assert "INSERT INTO mysql_servers" in sql
    assert "10.0.0.1" in sql


def test_w02_add_pgsql_server_sql_generation():
    """Test W02 (PostgreSQL server) SQL generation."""
    wizard = WIZARD_REGISTRY["W02"]
    fields = {
        "hostgroup_id": 0,
        "hostname": "10.0.0.2",
        "port": 5432,
        "status": "ONLINE",
        "weight": 1,
        "max_connections": 500,
        "use_ssl": 0,
        "comment": "pg server",
    }
    sqls = wizard.generate_sql(fields)
    assert len(sqls) == 1
    assert "INSERT INTO pgsql_servers" in sqls[0]
    assert "10.0.0.2" in sqls[0]


def test_w04_edit_mysql_server_sql_generation():
    """Test W04 SQL generation produces an UPDATE."""
    wizard = WIZARD_REGISTRY["W04"]
    sqls = wizard.generate_sql({
        "hostgroup_id": 0,
        "hostname": "10.0.0.1",
        "port": 3306,
        "weight": 5,
        "max_connections": 2000,
    })
    assert len(sqls) == 1
    assert sqls[0].startswith("UPDATE mysql_servers SET")
    assert "weight = 5" in sqls[0]
    assert "WHERE hostgroup_id = 0" in sqls[0]


def test_w04_edit_mysql_server_no_updates():
    """Test W04 produces no SQL when nothing is editable."""
    wizard = WIZARD_REGISTRY["W04"]
    sqls = wizard.generate_sql({
        "hostgroup_id": 0,
        "hostname": "10.0.0.1",
        "port": 3306,
    })
    assert sqls == []


def test_w05_toggle_server_status_sql_generation():
    """Test W05 SQL generation."""
    wizard = WIZARD_REGISTRY["W05"]
    sqls = wizard.generate_sql({
        "hostgroup_id": 0,
        "hostname": "10.0.0.1",
        "port": 3306,
        "status": "OFFLINE_SOFT",
    })
    assert len(sqls) == 1
    assert "UPDATE mysql_servers SET status = 'OFFLINE_SOFT'" in sqls[0]


def test_w05_rejects_invalid_status():
    """Test W05 validation rejects an unknown status."""
    wizard = WIZARD_REGISTRY["W05"]
    errors = wizard.validate({
        "hostgroup_id": 0,
        "hostname": "10.0.0.1",
        "status": "HACKED",
    })
    assert any("status must be" in e for e in errors)


def test_w09_add_mysql_user_sql_generation():
    """Test W09 SQL generation."""
    wizard = WIZARD_REGISTRY["W09"]
    fields = {
        "username": "testuser",
        "password": "testpass",
        "default_hostgroup": 0,
        "active": 1,
        "default_schema": "testdb",
        "max_connections": 100,
    }
    sqls = wizard.generate_sql(fields)
    assert len(sqls) == 1
    sql = sqls[0]
    assert "INSERT INTO mysql_users" in sql
    assert "testuser" in sql


def test_w11_edit_user_sql_generation():
    """Test W11 SQL generation produces an UPDATE."""
    wizard = WIZARD_REGISTRY["W11"]
    sqls = wizard.generate_sql({
        "username": "app_user",
        "max_connections": 5000,
        "active": 0,
    })
    assert len(sqls) == 1
    assert sqls[0].startswith("UPDATE mysql_users SET")
    assert "WHERE username = 'app_user'" in sqls[0]


def test_w12_change_password_sql_generation():
    """Test W12 SQL generation."""
    wizard = WIZARD_REGISTRY["W12"]
    sqls = wizard.generate_sql({
        "username": "app_user",
        "new_password": "s3cret",
    })
    assert len(sqls) == 1
    assert "UPDATE mysql_users SET password = 's3cret'" in sqls[0]
    assert "WHERE username = 'app_user'" in sqls[0]


def test_w13_toggle_user_active_sql_generation():
    """Test W13 SQL generation."""
    wizard = WIZARD_REGISTRY["W13"]
    sqls = wizard.generate_sql({"username": "app_user", "active": 0})
    assert len(sqls) == 1
    assert "UPDATE mysql_users SET active = 0" in sqls[0]


def test_w16_read_write_split_sql_generation():
    """Test W16 SQL generation."""
    wizard = WIZARD_REGISTRY["W16"]
    fields = {
        "writer_hostgroup": 0,
        "reader_hostgroup": 1,
        "cluster_name": "test_cluster",
        "rule_select_for_update": True,
        "rule_dml": True,
        "rule_select": True,
        "rule_transaction": True,
    }
    sqls = wizard.generate_sql(fields)
    assert len(sqls) >= 4  # replication hostgroups + at least 4 rules
    assert "mysql_replication_hostgroups" in sqls[0]
    assert "INSERT INTO mysql_query_rules" in sqls[1]


def test_w16_validation_same_hostgroups():
    """Test W16 validation with same writer/reader hostgroups."""
    wizard = WIZARD_REGISTRY["W16"]
    errors = wizard.validate({
        "writer_hostgroup": 0,
        "reader_hostgroup": 0,
    })
    assert len(errors) > 0


def test_w16_includes_check_type():
    """Test W16 includes the check_type column (per technical doc W24/W16)."""
    wizard = WIZARD_REGISTRY["W16"]
    sqls = wizard.generate_sql({
        "writer_hostgroup": 0,
        "reader_hostgroup": 1,
        "check_type": "super_read_only",
    })
    assert "check_type" in sqls[0]
    assert "'super_read_only'" in sqls[0]


def test_w17_add_query_rule_sql_generation():
    """Test W17 SQL generation."""
    wizard = WIZARD_REGISTRY["W17"]
    sqls = wizard.generate_sql({
        "rule_id": 100,
        "match_digest": "^SELECT.*FROM cache",
        "destination_hostgroup": 5,
        "apply": 1,
        "active": 1,
        "comment": "cache rule",
    })
    assert len(sqls) == 1
    assert "INSERT INTO mysql_query_rules" in sqls[0]
    assert "rule_id, active, destination_hostgroup, apply, match_digest" in sqls[0]


def test_w24_replication_hostgroups_sql_generation():
    """Test W24 SQL generation."""
    wizard = WIZARD_REGISTRY["W24"]
    sqls = wizard.generate_sql({
        "writer_hostgroup": 0,
        "reader_hostgroup": 1,
        "check_type": "read_only",
        "comment": "primary-replica",
    })
    assert len(sqls) == 1
    assert "INSERT INTO mysql_replication_hostgroups" in sqls[0]
    assert "check_type" in sqls[0]


def test_w24_rejects_invalid_check_type():
    """Test W24 rejects unknown check_type values."""
    wizard = WIZARD_REGISTRY["W24"]
    errors = wizard.validate({
        "writer_hostgroup": 0,
        "reader_hostgroup": 1,
        "check_type": "bogus",
    })
    assert any("check_type must be" in e for e in errors)


def test_w29_global_variable_update_sql_generation():
    """Test W29 (and W30/W31) SQL generation via the generic helper."""
    wizard = WIZARD_REGISTRY["W29"]
    sqls = wizard.generate_sql({
        "variables": {"mysql-max_connections": "2048", "mysql-connect_timeout_server": "10000"}
    })
    assert len(sqls) == 2
    for sql in sqls:
        assert sql.startswith("UPDATE global_variables SET variable_value = ")
        assert "WHERE variable_name = " in sql


def test_w46_config_sync_sql_generation():
    """Test W46 SQL generation."""
    wizard = WIZARD_REGISTRY["W46"]
    sqls = wizard.generate_sql({"action": "apply"})
    assert len(sqls) > 0
    assert "LOAD" in sqls[0]
    assert "TO RUNTIME" in sqls[0]


def test_w47_save_all_sql_generation():
    """Test W47 (Save All) SQL generation."""
    wizard = WIZARD_REGISTRY["W47"]
    sqls = wizard.generate_sql({"action": "save"})
    assert len(sqls) > 0
    assert "SAVE" in sqls[0]
    assert "TO DISK" in sqls[0]


def test_w50_load_from_disk_sql_generation():
    """Test W50 (Load From Disk) SQL generation."""
    wizard = WIZARD_REGISTRY["W50"]
    sqls = wizard.generate_sql({})
    assert len(sqls) > 0
    assert all("FROM DISK" in sql for sql in sqls)


def test_w51_reset_stats_sql_generation():
    """Test W51 (Reset Stats) SQL generation."""
    wizard = WIZARD_REGISTRY["W51"]
    sqls = wizard.generate_sql({})
    assert len(sqls) == 1
    assert "STATS_RESET" in sqls[0]


def test_wizard_preview():
    """Test wizard SQL preview."""
    wizard = WIZARD_REGISTRY["W01"]
    result = wizard.preview_sql({
        "hostgroup_id": 0,
        "hostname": "10.0.0.1",
        "port": 3306,
    })
    assert result["ok"] is True
    assert len(result["sql_preview"]) == 1
    assert "INSERT INTO mysql_servers" in result["sql_preview"][0]
    assert result["auto_apply_sql"] is not None


def test_all_wizards_registered():
    """All 70 wizards (W01-W70) must be registered in the registry."""
    assert len(WIZARD_REGISTRY) == EXPECTED_TOTAL_WIZARDS
    for i in range(1, EXPECTED_TOTAL_WIZARDS + 1):
        wiz_id = f"W{i:02d}"
        assert wiz_id in WIZARD_REGISTRY, f"Wizard {wiz_id} not registered"


def test_implemented_wizards_have_full_definitions():
    """All implemented wizards must have non-empty fields and a name/category."""
    for wiz_id, wizard in WIZARD_REGISTRY.items():
        assert wizard.definition.name, f"Wizard {wiz_id} has no name"
        assert wizard.definition.category, f"Wizard {wiz_id} has no category"
        if wizard.definition.status == "implemented":
            assert wiz_id in NO_FIELD_WIZARDS or len(wizard.definition.fields) > 0, (
                f"Implemented wizard {wiz_id} has no fields"
            )


def test_implemented_status_matches_registry():
    """The IMPLEMENTED_WIZARDS constant must match the registry's status field."""
    actual_implemented = {
        wid for wid, w in WIZARD_REGISTRY.items() if w.definition.status == "implemented"
    }
    assert actual_implemented == IMPLEMENTED_WIZARDS


def test_no_planned_wizards_remain():
    """All 70 wizards should now be implemented (no planned stubs left)."""
    planned = [wid for wid, w in WIZARD_REGISTRY.items() if w.definition.status == "planned"]
    assert planned == [], f"Unexpected planned wizards: {planned}"


# ── Tests for newly implemented wizards ──────────────────────────


def test_w03_batch_import_servers_sql_generation():
    """Test W03 (batch import) generates one INSERT per line."""
    wizard = WIZARD_REGISTRY["W03"]
    sqls = wizard.generate_sql({
        "target_table": "mysql_servers",
        "csv_data": "0,10.0.0.1,3306,ONLINE,1,1000,primary\n1,10.0.0.2,3306,ONLINE,1,1000,reader",
    })
    assert len(sqls) == 2
    assert "INSERT INTO mysql_servers" in sqls[0]
    assert "10.0.0.1" in sqls[0]
    assert "10.0.0.2" in sqls[1]


def test_w03_batch_import_validation():
    """Test W03 validation rejects empty input and bad port."""
    wizard = WIZARD_REGISTRY["W03"]
    errors = wizard.validate({"csv_data": ""})
    assert len(errors) > 0

    errors = wizard.validate({"csv_data": "0,host,not_a_port"})
    assert len(errors) > 0


def test_w03_batch_import_skips_comments():
    """Test W03 ignores comment lines starting with #."""
    wizard = WIZARD_REGISTRY["W03"]
    sqls = wizard.generate_sql({
        "target_table": "mysql_servers",
        "csv_data": "# comment line\n0,10.0.0.1,3306,ONLINE",
    })
    assert len(sqls) == 1


def test_w35_admin_user_management_sql_generation():
    """Test W35 (admin user management) generates correct SQL."""
    wizard = WIZARD_REGISTRY["W35"]
    # List action
    sqls = wizard.generate_sql({"action": "list"})
    assert "SELECT variable_value" in sqls[0]
    assert "admin-admin_credentials" in sqls[0]

    # Set action
    sqls = wizard.generate_sql({"action": "set", "target": "admin_credentials",
                                 "credentials": "admin:pass"})
    assert "UPDATE global_variables" in sqls[0]
    assert "admin-admin_credentials" in sqls[0]


def test_w53_slow_query_analysis_queries():
    """Test W53 (slow query analysis) generates read-only queries."""
    wizard = WIZARD_REGISTRY["W53"]
    queries = wizard.generate_queries({"sort_by": "sum_time", "limit": 10})
    assert "top_queries" in queries
    assert "stats_mysql_query_digest" in queries["top_queries"]
    assert "ORDER BY sum_time DESC" in queries["top_queries"]
    assert "LIMIT 10" in queries["top_queries"]


def test_w53_validation_rejects_bad_sort():
    """Test W53 validation rejects invalid sort_by."""
    wizard = WIZARD_REGISTRY["W53"]
    errors = wizard.validate({"sort_by": "invalid_column"})
    assert len(errors) > 0


def test_w57_connection_pool_monitor_queries():
    """Test W57 (connection pool monitoring) generates read-only queries."""
    wizard = WIZARD_REGISTRY["W57"]
    queries = wizard.generate_queries({})
    assert "connection_pool" in queries
    assert "stats_mysql_connection_pool" in queries["connection_pool"]
    assert "summary" in queries


def test_w58_realtime_process_list_queries():
    """Test W58 (realtime process list) generates read-only queries."""
    wizard = WIZARD_REGISTRY["W58"]
    queries = wizard.generate_queries({})
    assert "processlist" in queries
    assert "stats_mysql_processlist" in queries["processlist"]


def test_w61_global_status_queries():
    """Test W61 (global status panel) queries both stats tables."""
    wizard = WIZARD_REGISTRY["W61"]
    queries = wizard.generate_queries({})
    assert "global_status" in queries
    assert "memory_metrics" in queries
    assert "stats_mysql_global" in queries["global_status"]
    assert "stats_memory_metrics" in queries["memory_metrics"]


def test_w52_flush_query_cache_sql():
    """Test W52 (flush query cache) generates the flush command."""
    wizard = WIZARD_REGISTRY["W52"]
    sqls = wizard.generate_sql({})
    assert len(sqls) == 1
    assert "FLUSH_QUERY_CACHE" in sqls[0]


def test_w39_scheduler_task_add_sql():
    """Test W39 (scheduler task management) generates INSERT for add."""
    wizard = WIZARD_REGISTRY["W39"]
    sqls = wizard.generate_sql({
        "action": "add",
        "active": 1,
        "interval_ms": 5000,
        "filename": "/path/to/script.sh",
        "comment": "test task",
    })
    assert len(sqls) == 1
    assert "INSERT INTO scheduler" in sqls[0]
    assert "/path/to/script.sh" in sqls[0]


def test_w39_scheduler_task_list_sql():
    """Test W39 list action generates SELECT."""
    wizard = WIZARD_REGISTRY["W39"]
    sqls = wizard.generate_sql({"action": "list"})
    assert "SELECT" in sqls[0]
    assert "FROM scheduler" in sqls[0]

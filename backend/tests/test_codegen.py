"""Tests for the code generator parser."""
import pytest
import tempfile
import os
from pathlib import Path

from codegen.parser import (
    read_header, extract_defines, resolve_defines,
    is_current_table, parse_create_table, TableDef, Column,
    _unquote, _split_column_defs,
)


# Sample C header content for testing
SAMPLE_HEADER = """
#define ADMIN_SQLITE_TABLE_MYSQL_SERVERS_V1_0 "CREATE TABLE mysql_servers (hostgroup_id INT NOT NULL DEFAULT 0, hostname VARCHAR NOT NULL, port INT NOT NULL DEFAULT 3306, status VARCHAR CHECK (UPPER(status) IN ('ONLINE','SHUNNED','OFFLINE_SOFT','OFFLINE_HARD')) NOT NULL DEFAULT 'ONLINE', PRIMARY KEY (hostgroup_id, hostname, port))"
#define ADMIN_SQLITE_TABLE_MYSQL_SERVERS ADMIN_SQLITE_TABLE_MYSQL_SERVERS_V1_0

#define STATS_SQLITE_TABLE_MYSQL_CONNECTION_POOL "CREATE TABLE stats_mysql_connection_pool (hostgroup INT, srv_host VARCHAR, srv_port INT, status VARCHAR, ConnUsed INT, ConnFree INT)"
"""


def test_unquote():
    """Test string unquoting."""
    assert _unquote('"hello"') == "hello"
    assert _unquote('"hello" " world"') == "hello world"
    assert _unquote('  "test"  ') == "test"


def test_extract_defines():
    """Test extracting defines from C header."""
    defines = extract_defines(SAMPLE_HEADER)
    assert "ADMIN_SQLITE_TABLE_MYSQL_SERVERS_V1_0" in defines
    assert "ADMIN_SQLITE_TABLE_MYSQL_SERVERS" in defines
    assert defines["ADMIN_SQLITE_TABLE_MYSQL_SERVERS"] == "ADMIN_SQLITE_TABLE_MYSQL_SERVERS_V1_0"


def test_resolve_defines():
    """Test resolving alias chains."""
    defines = extract_defines(SAMPLE_HEADER)
    resolved = resolve_defines(defines)
    assert "ADMIN_SQLITE_TABLE_MYSQL_SERVERS" in resolved
    # Should resolve to the actual SQL
    sql = resolved["ADMIN_SQLITE_TABLE_MYSQL_SERVERS"]
    assert "CREATE TABLE" in sql


def test_is_current_table():
    """Test filtering versioned vs current table definitions."""
    assert is_current_table("ADMIN_SQLITE_TABLE_MYSQL_SERVERS") is True
    assert is_current_table("ADMIN_SQLITE_TABLE_MYSQL_SERVERS_V1_0") is False
    assert is_current_table("ADMIN_SQLITE_TABLE_MYSQL_SERVERS_V2_0_11") is False
    assert is_current_table("STATS_SQLITE_TABLE_MYSQL_CONNECTION_POOL") is True
    assert is_current_table("RANDOM_DEFINE") is False


def test_split_column_defs():
    """Test splitting column definitions."""
    parts = _split_column_defs("a INT, b VARCHAR, c CHECK (x IN (1,2))")
    assert len(parts) == 3

    parts = _split_column_defs("a INT NOT NULL DEFAULT 0, b VARCHAR, PRIMARY KEY (a, b)")
    assert len(parts) == 3


def test_parse_create_table_simple():
    """Test parsing a simple CREATE TABLE."""
    sql = "CREATE TABLE test_table (id INT NOT NULL, name VARCHAR(64), active INT DEFAULT 1, PRIMARY KEY (id))"
    table = parse_create_table(sql, "TEST_MACRO")

    assert table.table_name == "test_table"
    assert table.macro_name == "TEST_MACRO"
    assert len(table.columns) == 3
    assert table.table_pks == ["id"]
    assert table.is_readonly is False
    assert table.is_view is False

    # Check columns
    col_names = [c.name for c in table.columns]
    assert "id" in col_names
    assert "name" in col_names
    assert "active" in col_names

    # Check types
    id_col = next(c for c in table.columns if c.name == "id")
    assert id_col.python_type == "int"
    assert id_col.nullable is False

    name_col = next(c for c in table.columns if c.name == "name")
    assert name_col.python_type == "str"
    assert name_col.nullable is True

    active_col = next(c for c in table.columns if c.name == "active")
    assert active_col.default == 1


def test_parse_create_table_with_check():
    """Test parsing a table with CHECK constraints."""
    sql = """CREATE TABLE mysql_servers (
        hostgroup_id INT NOT NULL DEFAULT 0,
        hostname VARCHAR NOT NULL,
        port INT NOT NULL DEFAULT 3306,
        status VARCHAR CHECK (UPPER(status) IN ('ONLINE','SHUNNED')) NOT NULL DEFAULT 'ONLINE',
        weight INT CHECK (weight >= 0 AND weight <= 10000000) NOT NULL DEFAULT 1,
        PRIMARY KEY (hostgroup_id, hostname, port)
    )"""
    table = parse_create_table(sql, "TEST")

    assert table.table_name == "mysql_servers"
    assert len(table.columns) == 5
    assert len(table.table_pks) == 3

    # Check CHECK constraint parsing
    status_col = next(c for c in table.columns if c.name == "status")
    assert status_col.check_expression is not None
    assert "ONLINE" in status_col.check_values
    assert "SHUNNED" in status_col.check_values

    weight_col = next(c for c in table.columns if c.name == "weight")
    assert weight_col.check_expression is not None


def test_parse_view():
    """Test parsing a CREATE VIEW."""
    sql = "CREATE VIEW test_view AS SELECT id, name FROM test_table"
    table = parse_create_table(sql, "TEST_VIEW")
    assert table.is_view is True


def test_model_class_name():
    """Test PascalCase conversion."""
    table = TableDef(macro_name="TEST", table_name="mysql_query_rules")
    assert table.model_class_name == "MysqlQueryRules"


def test_is_readonly():
    """Test readonly detection."""
    config_table = TableDef(macro_name="T", table_name="mysql_servers")
    assert config_table.is_readonly is False

    stats_table = TableDef(macro_name="T", table_name="stats_mysql_global")
    assert stats_table.is_readonly is True

    runtime_table = TableDef(macro_name="T", table_name="runtime_mysql_servers")
    assert runtime_table.is_readonly is True

    view_table = TableDef(macro_name="T", table_name="test_view", is_view=True)
    assert view_table.is_readonly is True


def test_all_pk_columns():
    """Test primary key column collection."""
    col1 = Column(name="id", raw_type="INT", is_primary_key=True)
    col2 = Column(name="name", raw_type="VARCHAR")
    table = TableDef(
        macro_name="TEST",
        table_name="test",
        columns=[col1, col2],
        table_pks=["hostgroup_id"],
    )
    pks = table.all_pk_columns
    assert "id" in pks
    assert "hostgroup_id" in pks
    assert len(pks) == 2


def test_header_with_continuation():
    """Test reading header with backslash continuation."""
    content = '#define MULTI_LINE "CREATE TABLE test (" \\\n  "id INT" \\\n  ")"\n'
    with tempfile.NamedTemporaryFile(mode='w', suffix='.h', delete=False) as f:
        f.write(content)
        tmp_path = f.name

    try:
        text = read_header(tmp_path)
        assert 'CREATE TABLE' in text
        assert '\\' not in text.split('\n')[0]  # Continuation resolved
    finally:
        os.unlink(tmp_path)


def test_generator_integration():
    """Test full code generation pipeline with sample header."""
    # Write a test header
    test_header = """
#define ADMIN_SQLITE_TABLE_MYSQL_SERVERS_V1_0 "CREATE TABLE mysql_servers (hostgroup_id INT NOT NULL DEFAULT 0, hostname VARCHAR NOT NULL, port INT NOT NULL DEFAULT 3306, PRIMARY KEY (hostgroup_id, hostname, port))"
#define ADMIN_SQLITE_TABLE_MYSQL_SERVERS ADMIN_SQLITE_TABLE_MYSQL_SERVERS_V1_0

#define STATS_SQLITE_TABLE_MYSQL_CONNECTION_POOL "CREATE TABLE stats_mysql_connection_pool (hostgroup INT, srv_host VARCHAR, srv_port INT, status VARCHAR, ConnUsed INT, ConnFree INT)"

#define ADMIN_SQLITE_TABLE_OLD_VERSION_V1_0 "CREATE TABLE old_version (col1 INT)"
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.h', delete=False) as f:
        f.write(test_header)
        header_path = f.name

    outdir = tempfile.mkdtemp()

    try:
        # Run pipeline manually
        from codegen.parser import read_header, extract_defines, resolve_defines, is_current_table, parse_create_table
        from codegen.emitter import emit_models, emit_crud_router, emit_metadata

        text = read_header(header_path)
        defines = extract_defines(text)
        resolved = resolve_defines(defines)
        current = {n: s for n, s in resolved.items() if is_current_table(n)}

        tables = []
        for macro_name, sql in sorted(current.items(), key=lambda x: len(x[0])):
            table_def = parse_create_table(sql, macro_name)
            tables.append(table_def)

        # Should have 2 tables (mysql_servers and stats_mysql_connection_pool),
        # but not the versioned one
        table_names = [t.table_name for t in tables]
        assert "mysql_servers" in table_names
        assert "stats_mysql_connection_pool" in table_names
        assert "old_version" not in table_names  # Versioned macro filtered out

        # Emit models
        models_path = Path(outdir) / "models.py"
        with open(models_path, "w") as f:
            emit_models(tables, f)
        assert models_path.exists()

        # Emit routes
        routes_path = Path(outdir) / "routes.py"
        with open(routes_path, "w") as f:
            emit_crud_router(tables, f)
        assert routes_path.exists()

        # Emit metadata
        metadata_path = Path(outdir) / "metadata.py"
        with open(metadata_path, "w") as f:
            emit_metadata(tables, f)
        assert metadata_path.exists()

    finally:
        os.unlink(header_path)
        import shutil
        shutil.rmtree(outdir, ignore_errors=True)

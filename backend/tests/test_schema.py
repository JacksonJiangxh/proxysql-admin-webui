"""Tests for schema service."""
import pytest
from app.services.schema_service import SchemaService


def test_parse_columns_simple():
    """Test parsing columns from simple CREATE TABLE."""
    sql = "CREATE TABLE test (id INT NOT NULL, name VARCHAR(64), active INT DEFAULT 1)"
    service = SchemaService()
    columns = service._parse_columns(sql)
    assert len(columns) == 3

    col_names = [c["name"] for c in columns]
    assert "id" in col_names
    assert "name" in col_names
    assert "active" in col_names

    # Check types
    id_col = next(c for c in columns if c["name"] == "id")
    assert "INT" in id_col["type"]
    assert id_col["nullable"] is False  # NOT NULL

    name_col = next(c for c in columns if c["name"] == "name")
    assert name_col["nullable"] is True


def test_parse_primary_keys():
    """Test parsing primary keys."""
    sql = "CREATE TABLE test (id INT, name VARCHAR(64), PRIMARY KEY (id, name))"
    service = SchemaService()
    pks = service._parse_primary_keys(sql)
    assert "id" in pks
    assert "name" in pks


def test_parse_inline_primary_key():
    """Test parsing inline primary key."""
    sql = "CREATE TABLE test (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, name VARCHAR(64))"
    service = SchemaService()
    pks = service._parse_primary_keys(sql)
    assert "id" in pks


def test_parse_check_constraints():
    """Test parsing CHECK constraints."""
    sql = """CREATE TABLE test (
        id INT,
        status VARCHAR CHECK (UPPER(status) IN ('ONLINE','OFFLINE','SHUNNED'))
    )"""
    service = SchemaService()
    constraints = service._parse_check_constraints(sql)
    assert "status" in constraints
    assert "ONLINE" in constraints["status"]


def test_parse_columns_with_check():
    """Test parsing columns with CHECK constraints."""
    sql = """CREATE TABLE mysql_servers (
        hostgroup_id INT NOT NULL DEFAULT 0,
        hostname VARCHAR NOT NULL,
        port INT CHECK (port >= 0 AND port <= 65535) NOT NULL DEFAULT 3306,
        status VARCHAR CHECK (UPPER(status) IN ('ONLINE','SHUNNED','OFFLINE_SOFT','OFFLINE_HARD')) NOT NULL DEFAULT 'ONLINE',
        weight INT CHECK (weight >= 0 AND weight <= 10000000) NOT NULL DEFAULT 1,
        PRIMARY KEY (hostgroup_id, hostname, port)
    )"""
    service = SchemaService()
    columns = service._parse_columns(sql)
    pks = service._parse_primary_keys(sql)
    constraints = service._parse_check_constraints(sql)

    assert len(columns) >= 4
    assert len(pks) == 3
    assert "port" in constraints or "status" in constraints


def test_split_commas():
    """Test the split_commas helper."""
    from app.utils.helpers import split_commas
    # Simple case
    parts = split_commas("a, b, c")
    assert parts == ["a", "b", "c"]

    # With nested parentheses
    parts = split_commas("a INT, b CHECK (x IN (1,2)), c VARCHAR")
    assert len(parts) == 3
    assert "b CHECK (x IN (1,2))" in parts[1]

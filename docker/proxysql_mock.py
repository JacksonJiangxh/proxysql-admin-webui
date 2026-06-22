#!/usr/bin/env python3
"""ProxySQL Mock Server for Integration Testing.

Listens on port 6032 and responds to a subset of MySQL-compatible
admin commands that the ProxySQL Admin WebUI uses. This allows
integration tests to run without a real ProxySQL instance.

Supported commands:
- SHOW TABLES FROM main
- PRAGMA table_info(...)
- SELECT ... FROM main....
- SELECT COUNT(*) ...
- INSERT INTO ...
- UPDATE ... SET ...
- DELETE FROM ...
- LOAD ... TO RUNTIME
- SAVE ... TO DISK
- LOAD ... FROM RUNTIME
- LOAD ... FROM DISK
- SELECT variable_value FROM runtime_global_variables
- SELECT * FROM stats_mysql_global
- SELECT * FROM stats_proxysql_servers_checksums
- SELECT * FROM runtime_proxysql_servers
- SELECT * FROM proxysql_servers
"""
import socket
import threading
import struct
import hashlib
import os
import json

# In-memory mock database
_mock_data = {
    "main": {
        "mysql_servers": [
            {"hostgroup_id": 0, "hostname": "10.0.0.1", "port": 3306, "status": "ONLINE", "weight": 1, "compression": 0, "max_connections": 1000, "max_replication_lag": 0, "use_ssl": 0, "max_latency_ms": 0, "comment": ""},
            {"hostgroup_id": 1, "hostname": "10.0.0.2", "port": 3306, "status": "ONLINE", "weight": 1, "compression": 0, "max_connections": 1000, "max_replication_lag": 0, "use_ssl": 0, "max_latency_ms": 0, "comment": ""},
        ],
        "mysql_users": [
            {"username": "app_user", "password": "hashed", "default_hostgroup": 0, "active": 1, "default_schema": "", "max_connections": 100},
        ],
        "mysql_query_rules": [
            {"rule_id": 1, "active": 1, "match_digest": "^SELECT", "destination_hostgroup": 1, "apply": 1},
        ],
        "mysql_variables": [
            {"variable_name": "mysql-max_connections", "variable_value": "2048"},
        ],
        "admin_variables": [
            {"variable_name": "admin-version", "variable_value": "2.7.2"},
        ],
        "global_variables": [
            {"variable_name": "mysql-server_version", "variable_value": "8.0.35"},
            {"variable_name": "admin-version", "variable_value": "2.7.2"},
        ],
        "proxysql_servers": [
            {"hostname": "127.0.0.1", "port": 6032, "weight": 1, "comment": "node1"},
        ],
        "scheduler": [],
    },
    "runtime_global_variables": [
        {"variable_name": "mysql-server_version", "variable_value": "8.0.35"},
        {"variable_name": "admin-version", "variable_value": "2.7.2"},
    ],
    "stats_mysql_global": [
        {"variable_name": "Uptime", "variable_value": "3600"},
        {"variable_name": "Questions", "variable_value": "12345"},
    ],
    "stats_proxysql_servers_checksums": [
        {"name": "mysql_servers", "version": 1, "epoch": 1, "checksum": "abc123"},
        {"name": "mysql_users", "version": 1, "epoch": 1, "checksum": "def456"},
    ],
    "runtime_proxysql_servers": [
        {"hostname": "127.0.0.1", "port": 6032, "weight": 1, "comment": "node1"},
    ],
    "stats_mysql_connection_pool": [
        {"hostgroup": "0", "srv_host": "10.0.0.1", "srv_port": "3306", "status": "ONLINE", "ConnUsed": "0", "ConnFree": "10", "ConnOK": "10", "ConnERR": "0", "Queries": "100"},
    ],
    "stats_mysql_processlist": [
        {"ThreadID": "1", "SessionID": "1", "user": "app_user", "db": "testdb", "command": "Query", "time_ms": "100", "info": "SELECT 1"},
    ],
    "stats_mysql_query_digest": [
        {"hostgroup": "0", "schemaname": "testdb", "username": "app_user", "digest_text": "SELECT * FROM test", "count_star": "100", "sum_time": "5.0"},
    ],
    "stats_memory_metrics": [
        {"variable_name": "SQLite3_memory_bytes", "variable_value": "1048576"},
    ],
}


def build_mysql_packet(sequence_id, payload):
    """Build a MySQL protocol packet."""
    length = struct.pack("<I", len(payload))[:3]
    seq = struct.pack("B", sequence_id)
    return length + seq + payload


def parse_mysql_packet(data):
    """Parse a MySQL protocol packet header. Returns (length, sequence_id, payload)."""
    if len(data) < 4:
        return 0, 0, data
    length = data[0] | (data[1] << 8) | (data[2] << 16)
    sequence_id = data[3]
    payload = data[4:4 + length]
    return length, sequence_id, payload


def build_column_def(name, col_type="VAR_STRING", flags=0):
    """Build MySQL column definition packets."""
    packets = []

    # Catalog
    packets.append(build_mysql_packet(0, b"def"))
    # Schema
    packets.append(build_mysql_packet(0, b"main"))
    # Table
    packets.append(build_mysql_packet(0, b""))
    # Org table
    packets.append(build_mysql_packet(0, b""))
    # Name
    packets.append(build_mysql_packet(0, name.encode()))
    # Org name
    packets.append(build_mysql_packet(0, name.encode()))
    # Filler + charset + length + type + flags + decimals + filler
    payload = struct.pack("<IH", 0x0c, 33)  # charset
    payload += struct.pack("<I", 255)  # max length
    payload += struct.pack("B", 253)  # VAR_STRING type
    payload += struct.pack("<H", flags)
    payload += struct.pack("B", 0)  # decimals
    payload += b"\x00\x00"  # filler
    packets.append(build_mysql_packet(0, payload))

    return packets


def build_result_set(columns, rows):
    """Build a complete MySQL result set response."""
    packets = []

    # Column count
    packets.append(build_mysql_packet(0, struct.pack("B", len(columns))))

    # Column definitions
    for col in columns:
        packets.extend(build_column_def(col))

    # EOF after columns
    packets.append(build_mysql_packet(0, b"\xfe"))

    # Row data
    for row in rows:
        row_data = b""
        for col in columns:
            val = row.get(col, "")
            if val is None:
                row_data += b"\xfb"  # NULL
            else:
                val_str = str(val).encode()
                row_data += struct.pack("B", len(val_str)) + val_str
        packets.append(build_mysql_packet(0, row_data))

    # EOF after rows
    packets.append(build_mysql_packet(0, b"\xfe"))

    return packets


def build_ok_packet(affected_rows=0, info=""):
    """Build a MySQL OK packet."""
    payload = b"\x00"  # OK header
    payload += struct.pack("B", affected_rows)  # affected rows
    payload += struct.pack("B", 0)  # last insert id
    payload += struct.pack("<H", 0x0002)  # status flags
    payload += struct.pack("<H", 0)  # warnings
    if info:
        payload += info.encode()
    return [build_mysql_packet(0, payload)]


def build_error_packet(err_code, message):
    """Build a MySQL error packet."""
    payload = b"\xff"  # ERR header
    payload += struct.pack("<H", err_code)
    payload += b"#" + b"HY000"  # SQL state marker + state
    payload += message.encode()
    return [build_mysql_packet(0, payload)]


def handle_query(sql):
    """Handle a SQL query and return MySQL protocol response packets."""
    sql_upper = sql.upper().strip()

    # SHOW TABLES FROM main
    if "SHOW TABLES" in sql_upper:
        tables = sorted(_mock_data["main"].keys())
        rows = [{"name": t} for t in tables]
        return build_result_set(["name"], rows)

    # PRAGMA table_info(table)
    if "PRAGMA TABLE_INFO" in sql_upper or "PRAGMA table_info" in sql:
        # Extract table name
        import re
        match = re.search(r"table_info\((\w+)\)", sql, re.IGNORECASE)
        if match:
            table_name = match.group(1)
            if table_name in _mock_data["main"]:
                rows = _mock_data["main"][table_name]
                if rows:
                    columns = []
                    pk_set = set()
                    # Guess primary keys
                    if table_name == "mysql_servers":
                        pk_set = {"hostgroup_id", "hostname", "port"}
                    elif table_name == "mysql_users":
                        pk_set = {"username"}
                    elif table_name == "mysql_query_rules":
                        pk_set = {"rule_id"}

                    for i, col in enumerate(rows[0].keys()):
                        val = rows[0][col]
                        col_type = "INT" if isinstance(val, int) else "VARCHAR"
                        columns.append({
                            "cid": i, "name": col, "type": col_type,
                            "notnull": 1, "dflt_value": None,
                            "pk": 1 if col in pk_set else 0,
                        })
                    return build_result_set(
                        ["cid", "name", "type", "notnull", "dflt_value", "pk"],
                        columns,
                    )
        return build_result_set(["cid", "name", "type", "notnull", "dflt_value", "pk"], [])

    # SELECT COUNT(*) ...
    if "COUNT(*)" in sql_upper:
        import re
        # Extract table name from "FROM main.X" or "FROM X"
        match = re.search(r"FROM\s+(?:main\.)?(\w+)", sql, re.IGNORECASE)
        if match:
            table_name = match.group(1)
            if table_name in _mock_data["main"]:
                count = len(_mock_data["main"][table_name])
                return build_result_set(["cnt"], [{"cnt": count}])
        return build_result_set(["cnt"], [{"cnt": 0}])

    # SELECT ... FROM main.table
    if "SELECT" in sql_upper and "FROM" in sql_upper:
        import re
        match = re.search(r"FROM\s+(?:main\.)?(\w+)", sql, re.IGNORECASE)
        if match:
            table_name = match.group(1)
            # Handle runtime_* tables
            if table_name.startswith("runtime_"):
                base = table_name[len("runtime_"):]
                if base in _mock_data["main"]:
                    rows = _mock_data["main"][base]
                    return build_result_set(list(rows[0].keys()) if rows else [], rows)
                # Fall through to other tables

            if table_name in _mock_data["main"]:
                rows = _mock_data["main"][table_name]
                columns = list(rows[0].keys()) if rows else []
                return build_result_set(columns, rows)

            # Handle special tables
            if table_name in _mock_data:
                rows = _mock_data[table_name]
                columns = list(rows[0].keys()) if rows else []
                return build_result_set(columns, rows)

        return build_result_set(["result"], [{"result": "ok"}])

    # INSERT INTO ...
    if "INSERT" in sql_upper:
        return build_ok_packet(affected_rows=1, info="1 row inserted")

    # UPDATE ... SET ...
    if "UPDATE" in sql_upper:
        return build_ok_packet(affected_rows=1, info="1 row updated")

    # DELETE FROM ...
    if "DELETE" in sql_upper:
        return build_ok_packet(affected_rows=1, info="1 row deleted")

    # LOAD / SAVE admin commands
    if any(cmd in sql_upper for cmd in ["LOAD", "SAVE"]):
        return build_ok_packet(affected_rows=0, info="OK")

    # FLUSH_QUERY_CACHE
    if "FLUSH_QUERY_CACHE" in sql_upper:
        return build_ok_packet(affected_rows=0, info="Query cache flushed")

    # STATS_RESET
    if "STATS_RESET" in sql_upper:
        return build_ok_packet(affected_rows=0, info="Stats reset")

    # Default: OK
    return build_ok_packet(affected_rows=0, info="Command executed")


def handle_greeting():
    """Build MySQL handshake greeting packet."""
    protocol_version = 10
    server_version = b"5.7.0-proxysql-mock\x00"
    connection_id = struct.pack("<I", 1)
    auth_plugin_data_part1 = os.urandom(8)
    filler = b"\x00"
    capability_flags_lower = struct.pack("<H", 0x0fff)
    character_set = struct.pack("B", 33)  # utf8
    status_flags = struct.pack("<H", 0x0002)
    capability_flags_upper = struct.pack("<H", 0x0000)
    auth_plugin_data_len = struct.pack("B", 21)
    reserved = b"\x00" * 10
    auth_plugin_data_part2 = os.urandom(12) + b"\x00"
    auth_plugin_name = b"mysql_native_password\x00"

    payload = struct.pack("B", protocol_version)
    payload += server_version
    payload += connection_id
    payload += auth_plugin_data_part1
    payload += filler
    payload += capability_flags_lower
    payload += character_set
    payload += status_flags
    payload += capability_flags_upper
    payload += auth_plugin_data_len
    payload += reserved
    payload += auth_plugin_data_part2
    payload += auth_plugin_name

    return [build_mysql_packet(0, payload)]


def handle_auth_response(data, sequence_id):
    """Handle MySQL authentication response."""
    # Accept any auth - this is a mock
    return build_mysql_packet(sequence_id + 1, b"\x00\x00\x00\x02\x00\x00\x00")


def handle_client(conn, addr):
    """Handle a single client connection."""
    print(f"[mock] Connection from {addr}")
    try:
        # Send greeting
        for packet in handle_greeting():
            conn.sendall(packet)

        # Read auth response
        data = conn.recv(4096)
        if data:
            conn.sendall(handle_auth_response(data, 1))

        # Process commands
        while True:
            data = conn.recv(65536)
            if not data:
                break

            length, seq_id, payload = parse_mysql_packet(data)
            if len(payload) < 1:
                continue

            command = payload[0]
            if command == 0x03:  # COM_QUERY
                sql = payload[1:].decode("utf-8", errors="replace")
                print(f"[mock] Query: {sql[:100]}")
                try:
                    packets = handle_query(sql)
                    for pkt in packets:
                        conn.sendall(pkt)
                except Exception as e:
                    print(f"[mock] Error handling query: {e}")
                    for pkt in build_error_packet(1064, f"Mock error: {str(e)}"):
                        conn.sendall(pkt)
            elif command == 0x01:  # COM_QUIT
                break
            else:
                # Unknown command, send OK
                conn.sendall(build_mysql_packet(0, b"\x00\x00\x00\x02\x00\x00\x00"))

    except Exception as e:
        print(f"[mock] Client error: {e}")
    finally:
        conn.close()
        print(f"[mock] Connection from {addr} closed")


def main():
    host = "0.0.0.0"
    port = 6032

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(10)

    print(f"[mock] ProxySQL Mock Server listening on {host}:{port}")

    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("[mock] Shutting down...")
    finally:
        server.close()


if __name__ == "__main__":
    main()

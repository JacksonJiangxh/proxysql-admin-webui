"""W03, W06-W08: Backend server management wizards."""
from app.services.wizard_engine import BaseWizard, WizardDefinition, WizardField, _quote_val
from app.services.proxysql import proxysql_service


class BatchImportServersWizard(BaseWizard):
    """W03: Batch import backend servers from CSV/text paste.

    Accepts a multi-line text block where each line is:
        hostgroup_id,hostname,port,status,weight,max_connections,comment

    Generates one INSERT per line into mysql_servers (or pgsql_servers).
    """

    def validate(self, fields: dict) -> list[str]:
        errors = []
        raw = fields.get("csv_data", "")
        if not raw or not raw.strip():
            errors.append("csv_data is required (one server per line)")
            return errors
        target = fields.get("target_table", "mysql_servers")
        if target not in ("mysql_servers", "pgsql_servers"):
            errors.append("target_table must be mysql_servers or pgsql_servers")
        # Validate each line can be parsed
        for i, line in enumerate(raw.strip().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                errors.append(f"Line {i}: need at least hostgroup_id,hostname,port")
                continue
            try:
                int(parts[0])
                int(parts[2])
            except ValueError:
                errors.append(f"Line {i}: hostgroup_id and port must be integers")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        target = fields.get("target_table", "mysql_servers")
        raw = fields.get("csv_data", "")
        default_port = 3306 if target == "mysql_servers" else 5432
        sqls = []

        for line in raw.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            hostgroup_id = int(parts[0])
            hostname = parts[1]
            port = int(parts[2]) if len(parts) > 2 and parts[2] else default_port
            status = parts[3] if len(parts) > 3 and parts[3] else "ONLINE"
            weight = int(parts[4]) if len(parts) > 4 and parts[4] else 1
            max_conn = int(parts[5]) if len(parts) > 5 and parts[5] else 1000
            comment = parts[6] if len(parts) > 6 and parts[6] else hostname

            cols = ["hostgroup_id", "hostname", "port", "status", "weight",
                    "max_connections", "comment"]
            vals = [hostgroup_id, hostname, port, status, weight, max_conn, comment]
            cols_str = ", ".join(cols)
            vals_str = ", ".join(_quote_val(v) for v in vals)
            sqls.append(f"INSERT INTO {target} ({cols_str}) VALUES ({vals_str})")
        return sqls


class ServerSslParamsWizard(BaseWizard):
    """W06: Configure SSL parameters for a backend server (mysql_servers_ssl_params)."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if fields.get("hostgroup_id") is None or not fields.get("hostname"):
            errors.append("hostgroup_id and hostname are required to identify the server")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        cols = ["hostgroup_id", "hostname", "port"]
        vals = [
            int(fields["hostgroup_id"]),
            fields["hostname"],
            int(fields.get("port", 3306)),
        ]
        for key in ("ssl_ca", "ssl_cert", "ssl_key", "ssl_cipher", "tls_version"):
            if fields.get(key) is not None:
                cols.append(key)
                vals.append(fields[key])
        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO mysql_servers_ssl_params ({cols_str}) VALUES ({vals_str})"]


class HostgroupAttributesWizard(BaseWizard):
    """W07: Configure hostgroup attributes (mysql_hostgroup_attributes)."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if fields.get("hostgroup_id") is None:
            errors.append("hostgroup_id is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        updates = {}
        for key in ("max_num_online_servers", "autocommit", "free_connections_pct",
                     "multiplex", "connection_warming", "init_connect",
                     "throttle_connections_per_sec", "servers_defaults",
                     "hostgroup_settings", "comment"):
            if fields.get(key) is not None:
                updates[key] = fields[key]

        if not updates:
            return []

        # Use INSERT OR REPLACE (upsert) so we don't need a separate
        # UPDATE + INSERT which would conflict if the row already exists.
        # mysql_hostgroup_attributes uses hostgroup_id as primary key.
        hg = int(fields["hostgroup_id"])
        col_names = ["hostgroup_id"] + list(updates.keys())
        col_vals = [hg] + list(updates.values())
        cols_str = ", ".join(col_names)
        vals_str = ", ".join(_quote_val(v) for v in col_vals)
        # Update clause for existing rows (all columns except the PK)
        update_clause = ", ".join(f"{k}=excluded.{k}" for k in updates.keys())
        return [
            f"INSERT INTO mysql_hostgroup_attributes ({cols_str}) VALUES ({vals_str}) "
            f"ON CONFLICT(hostgroup_id) DO UPDATE SET {update_clause}"
        ]


class BackendConnectionTestWizard(BaseWizard):
    """W08: Test backend connectivity and show current connection pool status.

    This is a read-only wizard that queries the connection pool for the
    specified backend server.
    """

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if fields.get("hostname"):
            if fields.get("port") is not None:
                try:
                    p = int(fields["port"])
                    if not (1 <= p <= 65535):
                        errors.append("port must be between 1 and 65535")
                except ValueError:
                    errors.append("port must be an integer")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        where_parts = []
        if fields.get("hostgroup") is not None:
            where_parts.append(f"hostgroup = {int(fields['hostgroup'])}")
        if fields.get("hostname"):
            where_parts.append(f"srv_host = {_quote_val(fields['hostname'])}")
            if fields.get("port") is not None:
                where_parts.append(f"srv_port = {int(fields['port'])}")
        where = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
        return [
            f"SELECT hostgroup, srv_host, srv_port, status, ConnUsed, ConnFree, "
            f"ConnOK, ConnERR, Queries, Latency_us "
            f"FROM stats_mysql_connection_pool{where}"
        ]

    async def execute(
        self, host: str, port: int, user: str, password: str,
        fields: dict, auto_apply: bool = False, auto_save: bool = False,
    ) -> dict:
        fields = self._normalize_fields(fields)
        errors = self.validate(fields)
        if errors:
            return {"ok": False, "errors": errors}

        sqls = self.generate_sql(fields)
        results = []
        executed_sql = []
        for sql in sqls:
            try:
                rows = await proxysql_service.execute_query(host, port, user, password, sql)
                results.append({"sql": sql, "ok": True, "rows": rows, "row_count": len(rows)})
                executed_sql.append(sql)
            except Exception as e:
                results.append({"sql": sql, "ok": False, "error": str(e)})
                executed_sql.append(sql)
        return {
            "ok": True,
            "wizard_id": self.definition.id,
            "wizard_name": self.definition.name,
            "executed_sql": executed_sql,
            "results": results,
            "all_succeeded": all(r["ok"] for r in results),
        }


# ── Wizard Definitions ──────────────────────────────────────────

DEFINITIONS = {
    "W03": (WizardDefinition(
        id="W03", category="backend_servers", name="Batch Import Backend Servers",
        description="Bulk import backend servers from CSV/text paste (one per line)",
        icon="upload", target_table="mysql_servers", auto_apply_module="MYSQL SERVERS",
        fields=[
            WizardField("target_table", "Target Table", "select", default="mysql_servers",
                        options=[{"value": "mysql_servers", "label": "mysql_servers"},
                                 {"value": "pgsql_servers", "label": "pgsql_servers"}]),
            WizardField("csv_data", "Server List (CSV: hg,host,port,status,weight,maxconn,comment)",
                        "textarea", required=True,
                        placeholder="0,10.0.0.1,3306,ONLINE,1,1000,primary\n0,10.0.0.2,3306,ONLINE,1,1000,replica\n1,10.0.0.3,3306,ONLINE,1,1000,reader"),
        ], status="implemented",
    ), BatchImportServersWizard),

    "W06": (WizardDefinition(
        id="W06", category="backend_servers", name="Backend Server SSL Parameters",
        description="Configure SSL parameters (ssl_ca, ssl_cert, ssl_key, ...) for a backend server",
        icon="lock", target_table="mysql_servers_ssl_params", auto_apply_module="MYSQL SERVERS",
        fields=[
            WizardField("_lookup", "Select Existing Server (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_servers",
                            "label_template": "hg={hostgroup_id} | {hostname}:{port} | {status}",
                            "linked_fields": {
                                "hostgroup_id": "hostgroup_id",
                                "hostname": "hostname",
                                "port": "port",
                            },
                        }),
            WizardField("hostgroup_id", "Hostgroup", "number", required=True),
            WizardField("hostname", "Hostname", "text", required=True),
            WizardField("port", "Port", "number", required=True, default=3306),
            WizardField("ssl_ca", "SSL CA", "text"),
            WizardField("ssl_cert", "SSL Cert", "text"),
            WizardField("ssl_key", "SSL Key", "text"),
            WizardField("ssl_cipher", "SSL Cipher", "text"),
            WizardField("tls_version", "TLS Version", "text"),
        ], status="implemented",
    ), ServerSslParamsWizard),

    "W07": (WizardDefinition(
        id="W07", category="backend_servers", name="Hostgroup Attributes",
        description="Configure hostgroup attributes (max_num_online_servers, multiplex, ...)",
        icon="settings", target_table="mysql_hostgroup_attributes", auto_apply_module="MYSQL SERVERS",
        fields=[
            WizardField("_lookup", "Select Existing Hostgroup (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_servers",
                            "label_template": "hg={hostgroup_id} | servers: {hostname}:{port}",
                            "linked_fields": {"hostgroup_id": "hostgroup_id"},
                        }),
            WizardField("hostgroup_id", "Hostgroup", "number", required=True),
            WizardField("max_num_online_servers", "Max Online Servers", "number"),
            WizardField("autocommit", "Autocommit", "toggle"),
            WizardField("free_connections_pct", "Free Connections %", "number"),
            WizardField("multiplex", "Multiplex", "number"),
            WizardField("connection_warming", "Connection Warming", "toggle"),
            WizardField("init_connect", "Init Connect SQL", "text"),
            WizardField("throttle_connections_per_sec", "Throttle (conn/sec)", "number"),
            WizardField("servers_defaults", "Servers Defaults", "text"),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), HostgroupAttributesWizard),

    "W08": (WizardDefinition(
        id="W08", category="backend_servers", name="Backend Connection Test",
        description="Test connectivity to a backend server and show pool status",
        icon="activity", target_table="stats_mysql_connection_pool", auto_apply_module=None,
        fields=[
            WizardField("_lookup", "Select Server (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_servers",
                            "label_template": "hg={hostgroup_id} | {hostname}:{port} | {status}",
                            "linked_fields": {
                                "hostgroup": "hostgroup_id",
                                "hostname": "hostname",
                                "port": "port",
                            },
                        }),
            WizardField("hostgroup", "Hostgroup (optional)", "number"),
            WizardField("hostname", "Hostname (optional, empty=all)", "text"),
            WizardField("port", "Port (optional)", "number"),
        ], status="implemented",
    ), BackendConnectionTestWizard),
}

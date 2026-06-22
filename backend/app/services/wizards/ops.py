"""W48, W49, W52: Operations wizards (backup / restore / cache flush)."""
from app.services.wizard_engine import BaseWizard, WizardDefinition, WizardField, _quote_val
from app.services.proxysql import proxysql_service
from app.utils.helpers import quote_ident


# Whitelist of tables allowed in backup/restore operations.
_BACKUP_TABLE_WHITELIST = {
    "mysql_servers", "mysql_users", "mysql_query_rules",
    "mysql_replication_hostgroups", "mysql_group_replication_hostgroups",
    "mysql_galera_hostgroups", "mysql_aws_aurora_hostgroups",
    "global_variables", "scheduler", "proxysql_servers", "restapi_routes",
    "pgsql_servers", "pgsql_users", "pgsql_query_rules",
    "pgsql_replication_hostgroups",
    "mysql_query_rules_fast_routing", "mysql_hostgroup_attributes",
    "mysql_servers_ssl_params", "mysql_ldap_mapping",
    "mysql_firewall_whitelist_users", "mysql_firewall_whitelist_rules",
    "mysql_collations",
}


class ConfigBackupWizard(BaseWizard):
    """W48: Export current ProxySQL configuration to a backup (SELECT dump)."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        modules = fields.get("modules", [])
        if modules:
            if not isinstance(modules, list):
                errors.append("modules must be a list of table names")
            else:
                for t in modules:
                    if t not in _BACKUP_TABLE_WHITELIST:
                        errors.append(f"Table '{t}' is not allowed for backup")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        modules = fields.get("modules", [])
        default_tables = list(_BACKUP_TABLE_WHITELIST)
        tables = modules if modules else default_tables
        sqls = []
        for table in tables:
            safe_table = quote_ident(table)
            sqls.append(f"SELECT * FROM {safe_table}")
        return sqls

    async def execute(
        self, host: str, port: int, user: str, password: str,
        fields: dict, auto_apply: bool = False, auto_save: bool = False,
    ) -> dict:
        errors = self.validate(fields)
        if errors:
            return {"ok": False, "errors": errors}

        sqls = self.generate_sql(fields)
        results = {}
        executed_sql = []
        all_ok = True

        for sql, table in zip(sqls, fields.get("modules", []) or list(_BACKUP_TABLE_WHITELIST)):
            try:
                rows = await proxysql_service.execute_query(host, port, user, password, sql)
                results[table] = rows
                executed_sql.append(sql)
            except Exception as e:
                results[table] = {"error": str(e)}
                executed_sql.append(sql)
                all_ok = False

        return {
            "ok": True,
            "wizard_id": self.definition.id,
            "wizard_name": self.definition.name,
            "executed_sql": executed_sql,
            "backup_data": results,
            "all_succeeded": all_ok,
        }


class ConfigRestoreWizard(BaseWizard):
    """W49: Restore ProxySQL configuration from a JSON backup.

    Accepts a JSON object mapping table names to arrays of row dicts,
    and generates DELETE + INSERT statements to restore each table.
    """

    def validate(self, fields: dict) -> list[str]:
        errors = []
        backup_data = fields.get("backup_data")
        if not backup_data or not isinstance(backup_data, dict):
            errors.append("backup_data (JSON object of table -> rows) is required")
            return errors
        if not fields.get("confirm_restore"):
            errors.append("confirm_restore must be true to proceed with restore")
        # Validate all table names are in the whitelist
        for table in backup_data.keys():
            if table not in _BACKUP_TABLE_WHITELIST:
                errors.append(f"Table '{table}' is not allowed for restore")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        backup_data = fields["backup_data"]
        sqls = []
        for table, rows in backup_data.items():
            safe_table = quote_ident(table)
            # Clear existing rows
            sqls.append(f"DELETE FROM {safe_table}")
            # Insert backed-up rows
            for row in rows:
                cols = list(row.keys())
                # Validate column names
                safe_cols = [quote_ident(c) for c in cols]
                vals = [row[c] for c in cols]
                cols_str = ", ".join(safe_cols)
                vals_str = ", ".join(_quote_val(v) for v in vals)
                sqls.append(f"INSERT INTO {safe_table} ({cols_str}) VALUES ({vals_str})")
        return sqls


class FlushQueryCacheWizard(BaseWizard):
    """W52: Flush the ProxySQL query cache."""

    def validate(self, fields: dict) -> list[str]:
        return []

    def generate_sql(self, fields: dict) -> list[str]:
        return ["SELECT FLUSH_QUERY_CACHE()"]


# ── Wizard Definitions ──────────────────────────────────────────

DEFINITIONS = {
    "W48": (WizardDefinition(
        id="W48", category="operations",
        name="Config Backup",
        description="Export current ProxySQL configuration (dump config tables)",
        icon="download", target_table="", auto_apply_module=None,
        fields=[
            WizardField("modules", "Modules to backup (JSON array, empty=all)", "textarea",
                        default='', placeholder='["mysql_servers", "mysql_users"]'),
        ], status="implemented",
    ), ConfigBackupWizard),

    "W49": (WizardDefinition(
        id="W49", category="operations",
        name="Config Restore",
        description="Restore ProxySQL configuration from a JSON backup",
        icon="upload", target_table="", auto_apply_module=None,
        fields=[
            WizardField("backup_data", "Backup Data (JSON: {table: [rows]})", "textarea",
                        required=True,
                        placeholder='{"mysql_servers": [{"hostgroup_id": 0, ...}]}'),
            WizardField("confirm_restore", "Confirm Restore (destructive)", "checkbox",
                        required=True, default=False),
        ], status="implemented",
    ), ConfigRestoreWizard),

    "W52": (WizardDefinition(
        id="W52", category="operations",
        name="Flush Query Cache",
        description="Flush the ProxySQL query cache",
        icon="trash-2", target_table="stats_mysql_global", auto_apply_module=None,
        fields=[], status="implemented",
    ), FlushQueryCacheWizard),
}

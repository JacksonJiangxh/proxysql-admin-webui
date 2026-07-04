"""Wizard engine - base classes and SQL generation for guided operations.

Each wizard encapsulates a specific ProxySQL operation, providing:
- Field validation
- SQL generation from form fields
- Execution with optional auto-apply/save

The full technical catalog defines 63 wizards (W01-W63). This module
implements the MVP subset documented in the technical specification's
"优先级矩阵" P0 list plus several frequently-used P1 wizards. Wizards not
yet implemented are exposed as ``status="planned"`` stubs so the UI can
advertise the roadmap without breaking the registry contract.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from app.services.proxysql import proxysql_service
from app.services.sync_service import sync_service, SyncAction


def _safe_get(fields: dict, key: str, default: Any = ""):
    """Get a field value with a default, handling None the same as missing.

    Python's ``dict.get(key, default)`` only returns the default when the
    key is completely absent from the dict; if the key is present with a
    ``None`` value (e.g. JSON ``null`` from a frontend form), it returns
    ``None``.  This helper treats ``None`` and missing keys the same way,
    which prevents accidental SQL ``NULL`` for NOT NULL columns like
    ``comment``.
    """
    val = fields.get(key)
    return val if val is not None else default


def _quote_val(v):
    """Safely quote/format a value for SQL embedding.

    IMPORTANT: This is a minimal-effort escape suitable for the MVP. A more
    robust long-term solution is to refactor generate_sql to return
    (sql, params) pairs and use aiomysql parameter binding everywhere.
    """
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    # Reject control characters that could enable multi-statement or escape attacks.
    if any(c in s for c in "\x00\x08\x0b\x0c\x1a"):
        raise ValueError("Invalid character in SQL value")
    # Escape backslashes and double single quotes to be safe with MySQL escape rules.
    escaped = s.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


@dataclass
class WizardField:
    """Definition of a single wizard form field."""
    name: str
    label: str
    type: str  # text, number, select, radio, checkbox, password, textarea, toggle, lookup
    required: bool = False
    default: Any = None
    options: list = field(default_factory=list)
    help_text: str = ""
    placeholder: str = ""
    validation: Optional[str] = None
    min: Optional[int] = None
    max: Optional[int] = None
    # ── Dynamic lookup (type="lookup") ───────────────────────
    # When type == "lookup", this field renders as a searchable dropdown that
    # dynamically fetches options from the connected ProxySQL instance.  When
    # the user selects an option the linked_fields are auto-filled.
    # Structure:
    #   lookup = {
    #       "table": "mysql_servers",                   # ProxySQL table to query
    #       "label_template": "{hostname}:{port}",       # Python format string for display
    #       "linked_fields": {                           # column -> form-field-name
    #           "hostgroup_id": "hostgroup_id",
    #           "hostname": "hostname",
    #           "port": "port",
    #       },
    #       "allow_manual": True,                        # also permit manual text input
    #   }
    lookup: Optional[dict] = None

    def get_lookup_sql(self) -> str:
        """Build the SELECT query for this lookup field's options.

        Columns are collected from two sources:
        1) ``linked_fields`` keys — needed to populate auto-fill form fields.
        2) ``label_template`` placeholders — needed to render human-readable
           dropdown labels (e.g. ``{hostname}:{port}``).
        """
        if not self.lookup:
            return ""
        import re
        table = self.lookup["table"]
        linked = self.lookup.get("linked_fields", {})
        select_cols = list(linked.keys())
        # Also extract columns referenced in the label template
        label_tpl = self.lookup.get("label_template", "")
        label_cols = re.findall(r'\{(\w+)\}', label_tpl)
        for col in label_cols:
            if col not in select_cols:
                select_cols.append(col)
        if not select_cols:
            select_cols = ["*"]
        cols_str = ", ".join(select_cols)
        return f"SELECT {cols_str} FROM {table} ORDER BY 1"


@dataclass
class WizardDefinition:
    """Definition of a complete wizard."""
    id: str
    category: str
    name: str
    description: str
    icon: str
    fields: list
    target_table: str
    auto_apply_module: Optional[str] = None
    related_tables: list = field(default_factory=list)
    # Implementation status: "implemented" (executable) or "planned" (stub only).
    status: str = "implemented"
    # Beginner-friendly guide text explaining what this wizard does and how to use it.
    # Displayed as a highlighted info box inside the wizard form dialog.
    guide: str = ""


class BaseWizard(ABC):
    """Abstract base class for all wizards."""

    def __init__(self, definition: WizardDefinition):
        self.definition = definition

    @abstractmethod
    def validate(self, fields: dict) -> list[str]:
        """Validate form fields. Returns list of error messages."""
        ...

    @abstractmethod
    def generate_sql(self, fields: dict) -> list[str]:
        """Generate SQL statements from form fields."""
        ...

    @staticmethod
    def _normalize_fields(fields: dict) -> dict:
        """Strip ``None`` values from the fields dict.

        When the frontend sends ``"comment": null`` (JSON), Python
        deserializes it as ``None``.  ``dict.get("key", default)`` then
        returns ``None`` instead of the default because the key *exists*
        (its value is just ``None``).  Stripping ``None``-valued keys
        fixes this for every ``dict.get()`` call site at once, preventing
        accidental SQL ``NULL`` for NOT NULL columns.
        """
        return {k: v for k, v in fields.items() if v is not None}

    async def execute(
        self,
        host: str, port: int, user: str, password: str,
        fields: dict,
        auto_apply: bool = False,
        auto_save: bool = False,
    ) -> dict:
        """Execute the wizard operation."""
        fields = self._normalize_fields(fields)
        errors = self.validate(fields)
        if errors:
            return {"ok": False, "errors": errors}

        sqls = self.generate_sql(fields)
        results = []

        for sql in sqls:
            try:
                if sql.strip().upper().startswith(("LOAD ", "SAVE ")):
                    output = await proxysql_service.execute_admin_command(
                        host, port, user, password, sql
                    )
                    results.append({"sql": sql, "ok": True, "output": output})
                else:
                    affected = await proxysql_service.execute_modify(
                        host, port, user, password, sql
                    )
                    results.append({"sql": sql, "ok": True, "affected_rows": affected})
            except Exception as e:
                results.append({"sql": sql, "ok": False, "error": str(e)})
                return {
                    "ok": False,
                    "wizard_id": self.definition.id,
                    "wizard_name": self.definition.name,
                    "executed_sql": [r["sql"] for r in results],
                    "results": results,
                    "all_succeeded": False,
                }

        # Auto Apply
        auto_apply_error = None
        if auto_apply and self.definition.auto_apply_module:
            try:
                await sync_service.sync_action(
                    host, port, user, password,
                    SyncAction.APPLY,
                    tables=[self.definition.target_table],
                )
            except Exception as e:
                auto_apply_error = str(e)

        # Auto Save
        auto_save_error = None
        if auto_save and self.definition.auto_apply_module:
            try:
                await sync_service.sync_action(
                    host, port, user, password,
                    SyncAction.SAVE,
                    tables=[self.definition.target_table],
                )
            except Exception as e:
                auto_save_error = str(e)

        response: dict = {
            "ok": True,
            "wizard_id": self.definition.id,
            "wizard_name": self.definition.name,
            "executed_sql": [r["sql"] for r in results],
            "results": results,
            "all_succeeded": all(r["ok"] for r in results),
        }
        if auto_apply_error:
            response["auto_apply_error"] = auto_apply_error
        if auto_save_error:
            response["auto_save_error"] = auto_save_error
        return response

    def preview_sql(self, fields: dict) -> dict:
        """Preview the SQL that would be executed."""
        fields = self._normalize_fields(fields)
        errors = self.validate(fields)
        if errors:
            return {"ok": False, "errors": errors}

        sqls = self.generate_sql(fields)
        auto_apply_sql = None
        if self.definition.auto_apply_module:
            auto_apply_sql = f"LOAD {self.definition.auto_apply_module.upper()} TO RUNTIME"

        return {
            "ok": True,
            "wizard_id": self.definition.id,
            "wizard_name": self.definition.name,
            "sql_preview": sqls,
            "auto_apply_sql": auto_apply_sql,
            "affected_modules": [self.definition.target_table],
            "warnings": [],
        }


class PlannedWizard(BaseWizard):
    """Placeholder for wizards that are documented but not yet implemented.

    Exposes the definition so the UI can advertise the roadmap, but any
    attempt to validate/generate SQL returns a clear "not implemented"
    message instead of silently no-op'ing.
    """

    def validate(self, fields: dict) -> list[str]:
        return [f"Wizard {self.definition.id} is planned but not yet implemented."]

    def generate_sql(self, fields: dict) -> list[str]:
        return []


# Import the extended wizard implementations from the wizards package.
# This import is deferred until after the base classes above are defined
# to avoid a circular import (the wizards package imports BaseWizard
# and WizardDefinition from this module).
from app.services.wizards import (  # noqa: E402
    SlowQueryAnalysisWizard, QueryCommandStatsWizard, QueryRuleHitsWizard,
    QueryErrorAnalysisWizard, ConnectionPoolMonitorWizard,
    RealtimeProcessListWizard, UserConnectionStatsWizard,
    BackendTopologyWizard, GlobalStatusWizard, GtidSyncStatusWizard,
    ClusterStatusWizard, MonitorCheckModeWizard,
    ConfigBackupWizard, ConfigRestoreWizard, FlushQueryCacheWizard,
    MultiplexingVariablesWizard, LoggingEventsWizard, MonitorVariablesWizard,
    AdminUserManagementWizard, NetworkInterfaceWizard, ClusterNodeWizard,
    ClusterSyncVariablesWizard, SchedulerTaskWizard, RestApiRouteWizard,
    SslBackendWizard, CharsetVersionWizard,
    FirewallUserWhitelistWizard, FirewallRuleWhitelistWizard,
    SqlInjectionProtectionWizard,
    QueryCacheRuleWizard, QueryRewriteRuleWizard, QueryTimeoutRuleWizard,
    QueryMirrorRuleWizard, FastRoutingWizard, QueryLoggingRuleWizard,
    GroupReplicationWizard, GaleraClusterWizard, AwsAuroraWizard,
    PgsqlReplicationWizard,
    BatchImportServersWizard, ServerSslParamsWizard,
    HostgroupAttributesWizard, BackendConnectionTestWizard,
    AddPgsqlUserWizard, LdapUserMappingWizard, FrontendBackendUserWizard,
)
from app.services.wizards import (  # noqa: E402
    monitor as _monitor_mod,
    ops as _ops_mod,
    system as _system_mod,
    firewall as _firewall_mod,
    routing as _routing_mod,
    topology as _topology_mod,
    server as _server_mod,
    user as _user_mod,
)


# ── Concrete Wizard Implementations ──────────────────────────


class AddMysqlServerWizard(BaseWizard):
    """W01: Add MySQL backend server."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if not fields.get("hostname"):
            errors.append("Host address is required")
        port = fields.get("port", 0)
        if not (1 <= int(port) <= 65535):
            errors.append("Port must be between 1-65535")
        if fields.get("hostgroup_id") is None:
            errors.append("Hostgroup is required")
        weight = int(fields.get("weight", 1))
        if not (0 <= weight <= 10000000):
            errors.append("Weight must be between 0-10000000")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        columns = [
            "hostgroup_id", "hostname", "port", "status", "weight",
            "max_connections", "max_replication_lag", "use_ssl",
            "max_latency_ms", "comment",
        ]
        comment = fields.get("comment")
        if not comment:
            comment = fields["hostname"]  # comment is NOT NULL; use hostname as default
        values = [
            int(fields.get("hostgroup_id", 0)),
            fields["hostname"],
            int(fields.get("port", 3306)),
            fields.get("status", "ONLINE"),
            int(fields.get("weight", 1)),
            int(fields.get("max_connections", 1000)),
            int(fields.get("max_replication_lag", 0)),
            int(fields.get("use_ssl", 0)),
            int(fields.get("max_latency_ms", 0)),
            comment,
        ]
        vals_str = ", ".join(_quote_val(v) for v in values)
        cols_str = ", ".join(columns)
        return [f"INSERT INTO mysql_servers ({cols_str}) VALUES ({vals_str})"]


class AddPgsqlServerWizard(BaseWizard):
    """W02: Add PostgreSQL backend server."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if not fields.get("hostname"):
            errors.append("Host address is required")
        if not (1 <= int(fields.get("port", 5432)) <= 65535):
            errors.append("Port must be between 1-65535")
        if fields.get("hostgroup_id") is None:
            errors.append("Hostgroup is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        columns = ["hostgroup_id", "hostname", "port", "status", "weight",
                   "max_connections", "use_ssl", "comment"]
        comment = fields.get("comment")
        if not comment:
            comment = fields["hostname"]  # comment is NOT NULL; use hostname as default
        values = [
            int(fields.get("hostgroup_id", 0)),
            fields["hostname"],
            int(fields.get("port", 5432)),
            fields.get("status", "ONLINE"),
            int(fields.get("weight", 1)),
            int(fields.get("max_connections", 1000)),
            int(fields.get("use_ssl", 0)),
            comment,
        ]
        vals_str = ", ".join(_quote_val(v) for v in values)
        cols_str = ", ".join(columns)
        return [f"INSERT INTO pgsql_servers ({cols_str}) VALUES ({vals_str})"]


class EditMysqlServerWizard(BaseWizard):
    """W04: Edit MySQL backend server attributes."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if fields.get("hostgroup_id") is None or not fields.get("hostname"):
            errors.append("hostgroup_id and hostname are required to identify the server")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        updates = {}
        for key in ("weight", "max_connections", "max_replication_lag",
                    "max_latency_ms", "compression", "comment"):
            if fields.get(key) is not None:
                updates[key] = fields[key]

        if not updates:
            return []

        set_clause = ", ".join(f"{k} = {_quote_val(v)}" for k, v in updates.items())
        where = (f"hostgroup_id = {int(fields['hostgroup_id'])} "
                 f"AND hostname = {_quote_val(fields['hostname'])} "
                 f"AND port = {int(fields.get('port', 3306))}")
        return [f"UPDATE mysql_servers SET {set_clause} WHERE {where}"]


class ToggleMysqlServerStatusWizard(BaseWizard):
    """W05: Bring a backend server online/offline."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if fields.get("hostgroup_id") is None or not fields.get("hostname"):
            errors.append("hostgroup_id and hostname are required")
        status = fields.get("status")
        if status not in ("ONLINE", "OFFLINE_SOFT", "OFFLINE_HARD"):
            errors.append("status must be ONLINE, OFFLINE_SOFT, or OFFLINE_HARD")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        where = (f"hostgroup_id = {int(fields['hostgroup_id'])} "
                 f"AND hostname = {_quote_val(fields['hostname'])} "
                 f"AND port = {int(fields.get('port', 3306))}")
        return [f"UPDATE mysql_servers SET status = {_quote_val(fields['status'])} WHERE {where}"]


class AddMysqlUserWizard(BaseWizard):
    """W09: Create MySQL backend user."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if not fields.get("username"):
            errors.append("Username is required")
        if not fields.get("password"):
            errors.append("Password is required")
        if fields.get("default_hostgroup") is None:
            errors.append("Default hostgroup is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        columns = [
            "username", "password", "active", "use_ssl",
            "default_hostgroup", "default_schema",
            "schema_locked", "transaction_persistent",
            "fast_forward", "backend", "frontend",
            "max_connections", "comment",
        ]
        values = [
            fields["username"],
            fields.get("password", ""),
            int(fields.get("active", 1)),
            int(fields.get("use_ssl", 0)),
            int(fields.get("default_hostgroup", 0)),
            fields.get("default_schema", ""),
            int(fields.get("schema_locked", 0)),
            int(fields.get("transaction_persistent", 1)),
            int(fields.get("fast_forward", 0)),
            int(fields.get("backend", 1)),
            int(fields.get("frontend", 1)),
            int(fields.get("max_connections", 10000)),
            fields.get("comment", ""),
        ]
        vals_str = ", ".join(_quote_val(v) for v in values)
        cols_str = ", ".join(columns)
        return [f"INSERT INTO mysql_users ({cols_str}) VALUES ({vals_str})"]


class EditMysqlUserWizard(BaseWizard):
    """W11: Edit MySQL backend user attributes."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if not fields.get("username"):
            errors.append("username is required to identify the user")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        updates = {}
        for key in ("default_hostgroup", "max_connections", "transaction_persistent",
                    "schema_locked", "active", "default_schema", "comment"):
            if fields.get(key) is not None:
                updates[key] = fields[key]
        if not updates:
            return []
        set_clause = ", ".join(f"{k} = {_quote_val(v)}" for k, v in updates.items())
        return [f"UPDATE mysql_users SET {set_clause} WHERE username = {_quote_val(fields['username'])}"]


class ChangeMysqlUserPasswordWizard(BaseWizard):
    """W12: Change a MySQL backend user's password."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if not fields.get("username"):
            errors.append("username is required")
        if not fields.get("new_password"):
            errors.append("new_password is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        return [
            f"UPDATE mysql_users SET password = {_quote_val(fields['new_password'])} "
            f"WHERE username = {_quote_val(fields['username'])}"
        ]


class ToggleMysqlUserActiveWizard(BaseWizard):
    """W13: Enable/disable a MySQL backend user."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if not fields.get("username"):
            errors.append("username is required")
        if fields.get("active") not in (0, 1, "0", "1"):
            errors.append("active must be 0 or 1")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        return [
            f"UPDATE mysql_users SET active = {int(fields['active'])} "
            f"WHERE username = {_quote_val(fields['username'])}"
        ]


class ReadWriteSplitWizard(BaseWizard):
    """W16: Quick read-write split configuration."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        writer = int(fields.get("writer_hostgroup", 0))
        reader = int(fields.get("reader_hostgroup", 1))
        if writer == reader:
            errors.append("Writer and reader hostgroups must be different")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        writer_hg = int(fields.get("writer_hostgroup", 0))
        reader_hg = int(fields.get("reader_hostgroup", 1))
        cluster_name = _quote_val(fields.get("cluster_name", "cluster1"))
        check_type = _quote_val(fields.get("check_type", "read_only"))

        sqls = []

        # 1. Create replication hostgroups
        sqls.append(
            f"INSERT INTO mysql_replication_hostgroups "
            f"(writer_hostgroup, reader_hostgroup, check_type, comment) "
            f"VALUES ({writer_hg}, {reader_hg}, {check_type}, {cluster_name})"
        )

        rule_id = int(fields.get("base_rule_id", 10))

        # 2. SELECT ... FOR UPDATE -> Writer
        if fields.get("rule_select_for_update", True):
            sqls.append(
                f"INSERT INTO mysql_query_rules "
                f"(rule_id, active, match_digest, destination_hostgroup, apply, comment) "
                f"VALUES ({rule_id}, 1, '^SELECT.*FOR UPDATE', {writer_hg}, 1, 'RW-Split: SELECT FOR UPDATE')"
            )
            rule_id += 10

        # 3. INSERT/UPDATE/DELETE/DDL/LOCK/UNLOCK/FLUSH -> Writer
        if fields.get("rule_dml", True):
            sqls.append(
                f"INSERT INTO mysql_query_rules "
                f"(rule_id, active, match_digest, destination_hostgroup, apply, comment) "
                f"VALUES ({rule_id}, 1, "
                f"'^(INSERT|UPDATE|DELETE|REPLACE|CREATE|ALTER|DROP|TRUNCATE|LOCK|UNLOCK|FLUSH)', "
                f"{writer_hg}, 1, 'RW-Split: DML+DDL')"
            )
            rule_id += 10

        # 4. SELECT -> Reader
        if fields.get("rule_select", True):
            sqls.append(
                f"INSERT INTO mysql_query_rules "
                f"(rule_id, active, match_digest, destination_hostgroup, apply, comment) "
                f"VALUES ({rule_id}, 1, '^SELECT', {reader_hg}, 1, 'RW-Split: SELECT')"
            )
            rule_id += 10

        # 5. Transaction control -> Writer
        if fields.get("rule_transaction", True):
            sqls.append(
                f"INSERT INTO mysql_query_rules "
                f"(rule_id, active, match_digest, destination_hostgroup, apply, comment) "
                f"VALUES ({rule_id}, 1, "
                f"'^(SET autocommit|BEGIN|COMMIT|ROLLBACK|START TRANSACTION)', "
                f"{writer_hg}, 1, 'RW-Split: Transaction')"
            )

        return sqls


class AddQueryRuleWizard(BaseWizard):
    """W17: Add a single query routing rule via a simplified form."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if fields.get("rule_id") is None:
            errors.append("rule_id is required")
        if not fields.get("match_digest") and not fields.get("match_pattern"):
            errors.append("Either match_digest or match_pattern is required")
        if fields.get("destination_hostgroup") is None:
            errors.append("destination_hostgroup is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        cols = ["rule_id", "active", "destination_hostgroup", "apply"]
        vals = [
            int(fields["rule_id"]),
            int(fields.get("active", 1)),
            int(fields["destination_hostgroup"]),
            int(fields.get("apply", 1)),
        ]
        if fields.get("match_digest"):
            cols.append("match_digest")
            vals.append(fields["match_digest"])
        if fields.get("match_pattern"):
            cols.append("match_pattern")
            vals.append(fields["match_pattern"])
        if fields.get("username"):
            cols.append("username")
            vals.append(fields["username"])
        if fields.get("schemaname"):
            cols.append("schemaname")
            vals.append(fields["schemaname"])
        if fields.get("comment"):
            cols.append("comment")
            vals.append(fields["comment"])

        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO mysql_query_rules ({cols_str}) VALUES ({vals_str})"]


class ReplicationHostgroupsWizard(BaseWizard):
    """W24: Configure traditional primary/replica replication hostgroups."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        writer = int(fields.get("writer_hostgroup", -1))
        reader = int(fields.get("reader_hostgroup", -1))
        if writer < 0 or reader < 0:
            errors.append("writer_hostgroup and reader_hostgroup are required")
        elif writer == reader:
            errors.append("Writer and reader hostgroups must be different")
        check_type = fields.get("check_type", "read_only")
        valid = {"read_only", "innodb_read_only", "super_read_only",
                 "read_only|innodb_read_only", "read_only&innodb_read_only"}
        if check_type not in valid:
            errors.append(f"check_type must be one of: {', '.join(sorted(valid))}")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        return [
            f"INSERT INTO mysql_replication_hostgroups "
            f"(writer_hostgroup, reader_hostgroup, check_type, comment) "
            f"VALUES ({int(fields['writer_hostgroup'])}, {int(fields['reader_hostgroup'])}, "
            f"{_quote_val(fields.get('check_type', 'read_only'))}, "
            f"{_quote_val(fields.get('comment', ''))})"
        ]


class ConfigSyncWizard(BaseWizard):
    """W46/W47: One-click Apply All or Save All."""

    def validate(self, fields: dict) -> list[str]:
        action = fields.get("action", "apply")
        if action not in ("apply", "save"):
            return [f"Unknown action: {action}"]
        return []

    def generate_sql(self, fields: dict) -> list[str]:
        action = fields.get("action", "apply")
        if action == "save":
            return ["SAVE MYSQL SERVERS TO DISK",
                    "SAVE MYSQL USERS TO DISK",
                    "SAVE MYSQL QUERY RULES TO DISK",
                    "SAVE MYSQL VARIABLES TO DISK",
                    "SAVE ADMIN VARIABLES TO DISK"]
        else:
            return ["LOAD MYSQL SERVERS TO RUNTIME",
                    "LOAD MYSQL USERS TO RUNTIME",
                    "LOAD MYSQL QUERY RULES TO RUNTIME",
                    "LOAD MYSQL VARIABLES TO RUNTIME",
                    "LOAD ADMIN VARIABLES TO RUNTIME"]


class GlobalVariableUpdateWizard(BaseWizard):
    """W29-W34, W41-W42: Update one or more ProxySQL global variables.

    Generic helper wizard that updates ``global_variables`` rows for a list
    of (variable_name, value) pairs supplied by the form.
    """

    def validate(self, fields: dict) -> list[str]:
        errors = []
        variables = fields.get("variables")
        if not variables or not isinstance(variables, dict):
            errors.append("variables mapping is required")
            return errors
        for name in variables:
            if not name:
                errors.append("variable name cannot be empty")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        variables = fields["variables"]
        sqls = []
        for name, value in variables.items():
            sqls.append(
                f"UPDATE global_variables SET variable_value = {_quote_val(value)} "
                f"WHERE variable_name = {_quote_val(name)}"
            )
        return sqls


class LoadFromDiskWizard(BaseWizard):
    """W50: Load all configuration modules from disk into memory."""

    def validate(self, fields: dict) -> list[str]:
        return []

    def generate_sql(self, fields: dict) -> list[str]:
        return [
            "LOAD MYSQL SERVERS FROM DISK",
            "LOAD MYSQL USERS FROM DISK",
            "LOAD MYSQL QUERY RULES FROM DISK",
            "LOAD MYSQL VARIABLES FROM DISK",
            "LOAD ADMIN VARIABLES FROM DISK",
        ]


class ResetStatsWizard(BaseWizard):
    """W51: Reset ProxySQL statistics counters."""

    def validate(self, fields: dict) -> list[str]:
        return []

    def generate_sql(self, fields: dict) -> list[str]:
        return ["SELECT STATS_RESET()"]


# ── Wizard Registry ──────────────────────────────────────────


def _planned(wizard_id: str, category: str, name: str, description: str,
             icon: str, target_table: str = "", guide: str = "") -> PlannedWizard:
    """Helper to create a planned (not-yet-implemented) wizard stub."""
    return PlannedWizard(WizardDefinition(
        id=wizard_id,
        category=category,
        name=name,
        description=description,
        icon=icon,
        target_table=target_table,
        fields=[],
        status="planned",
        guide=guide,
    ))


WIZARD_REGISTRY: dict[str, BaseWizard] = {
    # ── Backend servers (W01-W08) ──
    "W01": AddMysqlServerWizard(WizardDefinition(
        id="W01",
        category="backend_servers",
        name="Add MySQL Backend Server",
        description="Add a new MySQL backend server to mysql_servers table",
        icon="server",
        target_table="mysql_servers",
        auto_apply_module="MYSQL SERVERS",
        fields=[
            WizardField("hostgroup_id", "Hostgroup", "number", required=True, default=0),
            WizardField("hostname", "Host Address", "text", required=True, placeholder="e.g. 10.0.0.1"),
            WizardField("port", "Port", "number", required=True, default=3306, min=1, max=65535),
            WizardField("status", "Status", "radio", required=True, default="ONLINE",
                        options=["ONLINE", "OFFLINE_SOFT", "OFFLINE_HARD"]),
            WizardField("weight", "Weight", "number", default=1, min=0, max=10000000),
            WizardField("max_connections", "Max Connections", "number", default=1000),
            WizardField("max_replication_lag", "Max Replication Lag (s)", "number", default=0),
            WizardField("use_ssl", "Use SSL", "toggle", default=0),
            WizardField("max_latency_ms", "Max Latency (ms)", "number", default=0),
            WizardField("comment", "Comment", "text"),
        ],
    )),
    "W02": AddPgsqlServerWizard(WizardDefinition(
        id="W02",
        category="backend_servers",
        name="Add PostgreSQL Backend Server",
        description="Add a new PostgreSQL backend server to pgsql_servers table",
        icon="server",
        target_table="pgsql_servers",
        auto_apply_module="PGSQL SERVERS",
        fields=[
            WizardField("hostgroup_id", "Hostgroup", "number", required=True, default=0),
            WizardField("hostname", "Host Address", "text", required=True, placeholder="e.g. 10.0.0.1"),
            WizardField("port", "Port", "number", required=True, default=5432, min=1, max=65535),
            WizardField("status", "Status", "radio", required=True, default="ONLINE",
                        options=["ONLINE", "OFFLINE_SOFT", "OFFLINE_HARD"]),
            WizardField("weight", "Weight", "number", default=1, min=0, max=10000000),
            WizardField("max_connections", "Max Connections", "number", default=1000),
            WizardField("use_ssl", "Use SSL", "toggle", default=0),
            WizardField("comment", "Comment", "text"),
        ],
    )),
    "W03": _planned("W03", "backend_servers", "Batch Import Backend Servers",
                    "Bulk import backend servers from CSV/text paste", "upload", "mysql_servers"),
    "W04": EditMysqlServerWizard(WizardDefinition(
        id="W04",
        category="backend_servers",
        name="Edit Backend Server Attributes",
        description="Modify weight, max_connections, max_replication_lag, etc.",
        icon="edit",
        target_table="mysql_servers",
        auto_apply_module="MYSQL SERVERS",
        fields=[
            WizardField("_lookup", "Select Existing Server (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_servers",
                            "label_template": "hg={hostgroup_id} | {hostname}:{port} | {status}",
                            "linked_fields": {
                                "hostgroup_id": "hostgroup_id",
                                "hostname": "hostname",
                                "port": "port",
                                "weight": "weight",
                                "max_connections": "max_connections",
                                "max_replication_lag": "max_replication_lag",
                                "max_latency_ms": "max_latency_ms",
                                "compression": "compression",
                                "comment": "comment",
                            },
                        }),
            WizardField("hostgroup_id", "Hostgroup (identifier)", "number", required=True),
            WizardField("hostname", "Hostname (identifier)", "text", required=True),
            WizardField("port", "Port (identifier)", "number", required=True, default=3306),
            WizardField("weight", "Weight", "number", min=0, max=10000000),
            WizardField("max_connections", "Max Connections", "number"),
            WizardField("max_replication_lag", "Max Replication Lag (s)", "number"),
            WizardField("max_latency_ms", "Max Latency (ms)", "number"),
            WizardField("compression", "Compression", "number", default=0),
            WizardField("comment", "Comment", "text"),
        ],
    )),
    "W05": ToggleMysqlServerStatusWizard(WizardDefinition(
        id="W05",
        category="backend_servers",
        name="Bring Server Online/Offline",
        description="Toggle a backend server status (ONLINE/OFFLINE_SOFT/OFFLINE_HARD)",
        icon="power",
        target_table="mysql_servers",
        auto_apply_module="MYSQL SERVERS",
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
            WizardField("status", "New Status", "radio", required=True, default="ONLINE",
                        options=["ONLINE", "OFFLINE_SOFT", "OFFLINE_HARD"]),
        ],
    )),
    "W06": _planned("W06", "backend_servers", "Backend Server SSL Parameters",
                    "Configure SSL parameters (ssl_ca, ssl_cert, ssl_key, ...) for a backend server",
                    "lock", "mysql_servers_ssl_params"),
    "W07": _planned("W07", "backend_servers", "Hostgroup Attributes",
                    "Configure hostgroup attributes (max_num_online_servers, multiplex, ...)",
                    "settings", "mysql_hostgroup_attributes"),
    "W08": _planned("W08", "backend_servers", "Backend Connection Test",
                    "Test connectivity to a backend server and show pool status",
                    "activity", "mysql_servers"),

    # ── Backend users (W09-W15) ──
    "W09": AddMysqlUserWizard(WizardDefinition(
        id="W09",
        category="backend_users",
        name="Create ProxySQL MySQL User",
        description="Register user credentials in ProxySQL (mysql_users) for frontend app auth and/or backend MySQL auth",
        icon="user",
        target_table="mysql_users",
        auto_apply_module="MYSQL USERS",
        fields=[
            WizardField("username", "Username", "text", required=True, placeholder="e.g. app_user"),
            WizardField("password", "Password", "password", required=True),
            WizardField("default_hostgroup", "Default Hostgroup", "number", required=True, default=0),
            WizardField("default_schema", "Default Schema", "text"),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("max_connections", "Max Connections", "number", default=10000),
            WizardField("transaction_persistent", "Transaction Persistent", "toggle", default=1),
            WizardField("fast_forward", "Fast Forward", "toggle", default=0),
            WizardField("schema_locked", "Schema Locked", "toggle", default=0),
            WizardField("comment", "Comment", "text"),
        ],
    )),
    "W10": _planned("W10", "backend_users", "Create PostgreSQL Backend User",
                    "Create a new PostgreSQL user for backend connections", "user", "pgsql_users"),
    "W11": EditMysqlUserWizard(WizardDefinition(
        id="W11",
        category="backend_users",
        name="Edit ProxySQL User Attributes",
        description="Modify registered user attributes: default_hostgroup, max_connections, active status, etc.",
        icon="edit",
        target_table="mysql_users",
        auto_apply_module="MYSQL USERS",
        fields=[
            WizardField("_lookup", "Select Existing User (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_users",
                            "label_template": "{username} | hg={default_hostgroup} | active={active}",
                            "linked_fields": {
                                "username": "username",
                                "default_hostgroup": "default_hostgroup",
                                "default_schema": "default_schema",
                                "max_connections": "max_connections",
                                "transaction_persistent": "transaction_persistent",
                                "schema_locked": "schema_locked",
                                "active": "active",
                                "comment": "comment",
                            },
                        }),
            WizardField("username", "Username (identifier)", "text", required=True),
            WizardField("default_hostgroup", "Default Hostgroup", "number"),
            WizardField("default_schema", "Default Schema", "text"),
            WizardField("max_connections", "Max Connections", "number"),
            WizardField("transaction_persistent", "Transaction Persistent", "toggle"),
            WizardField("schema_locked", "Schema Locked", "toggle"),
            WizardField("active", "Active", "toggle"),
            WizardField("comment", "Comment", "text"),
        ],
    )),
    "W12": ChangeMysqlUserPasswordWizard(WizardDefinition(
        id="W12",
        category="backend_users",
        name="Change ProxySQL User Password",
        description="Update the authentication password of a registered user in ProxySQL",
        icon="key",
        target_table="mysql_users",
        auto_apply_module="MYSQL USERS",
        fields=[
            WizardField("_lookup", "Select Existing User (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_users",
                            "label_template": "{username} | hg={default_hostgroup} | active={active}",
                            "linked_fields": {"username": "username"},
                        }),
            WizardField("username", "Username", "text", required=True),
            WizardField("new_password", "New Password", "password", required=True),
        ],
    )),
    "W13": ToggleMysqlUserActiveWizard(WizardDefinition(
        id="W13",
        category="backend_users",
        name="Enable/Disable ProxySQL User",
        description="Toggle the active flag of a registered user in ProxySQL",
        icon="power",
        target_table="mysql_users",
        auto_apply_module="MYSQL USERS",
        fields=[
            WizardField("_lookup", "Select Existing User (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_users",
                            "label_template": "{username} | hg={default_hostgroup} | active={active}",
                            "linked_fields": {
                                "username": "username",
                                "active": "active",
                            },
                        }),
            WizardField("username", "Username", "text", required=True),
            WizardField("active", "Active", "toggle", required=True, default=1),
        ],
    )),
    "W14": _planned("W14", "backend_users", "LDAP User Mapping",
                    "Configure LDAP user mapping (mysql_ldap_mapping)", "users", "mysql_ldap_mapping"),
    "W15": _planned("W15", "backend_users", "Frontend/Backend User Separation",
                    "Configure frontend-only or backend-only users", "user", "mysql_users"),

    # ── Query routing (W16-W23) ──
    "W16": ReadWriteSplitWizard(WizardDefinition(
        id="W16",
        category="query_routing",
        name="Read-Write Split Quick Setup",
        description="One-click setup for read-write split routing",
        icon="split",
        target_table="mysql_query_rules",
        auto_apply_module="MYSQL QUERY RULES",
        related_tables=["mysql_replication_hostgroups"],
        fields=[
            WizardField("_lookup", "Pick Existing Hostgroup (auto-fill writer)", "lookup",
                        lookup={
                            "table": "mysql_servers",
                            "label_template": "hg={hostgroup_id} | {hostname}:{port}",
                            "linked_fields": {"writer_hostgroup": "hostgroup_id"},
                        }),
            WizardField("writer_hostgroup", "Writer Hostgroup", "number", required=True, default=0),
            WizardField("reader_hostgroup", "Reader Hostgroup", "number", required=True, default=1),
            WizardField("check_type", "Check Type", "select", default="read_only",
                        options=["read_only", "innodb_read_only", "super_read_only",
                                 "read_only|innodb_read_only", "read_only&innodb_read_only"]),
            WizardField("cluster_name", "Cluster Name", "text", default="cluster1"),
            WizardField("base_rule_id", "Base Rule ID", "number", default=10),
            WizardField("rule_select_for_update", "SELECT FOR UPDATE -> Writer", "checkbox", default=True),
            WizardField("rule_dml", "INSERT/UPDATE/DELETE -> Writer", "checkbox", default=True),
            WizardField("rule_select", "SELECT -> Reader", "checkbox", default=True),
            WizardField("rule_transaction", "Transaction -> Writer", "checkbox", default=True),
        ],
    )),
    "W17": AddQueryRuleWizard(WizardDefinition(
        id="W17",
        category="query_routing",
        name="Add Query Routing Rule",
        description="Simplified form to add a single mysql_query_rules entry",
        icon="filter",
        target_table="mysql_query_rules",
        auto_apply_module="MYSQL QUERY RULES",
        fields=[
            WizardField("rule_id", "Rule ID", "number", required=True),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("match_digest", "Match Digest (regex)", "text", placeholder="^SELECT.*FOR UPDATE"),
            WizardField("match_pattern", "Match Pattern (regex)", "text"),
            WizardField("_lookup_username", "Pick Existing User (auto-fill username)", "lookup",
                        lookup={
                            "table": "mysql_users",
                            "label_template": "{username} | hg={default_hostgroup}",
                            "linked_fields": {"username": "username"},
                        }),
            WizardField("username", "Username (optional)", "text"),
            WizardField("schemaname", "Schema (optional)", "text"),
            WizardField("_lookup_hg", "Pick Hostgroup (auto-fill destination)", "lookup",
                        lookup={
                            "table": "mysql_servers",
                            "label_template": "hg={hostgroup_id} | {hostname}:{port}",
                            "linked_fields": {"destination_hostgroup": "hostgroup_id"},
                        }),
            WizardField("destination_hostgroup", "Destination Hostgroup", "number", required=True),
            WizardField("apply", "Apply (stop matching)", "toggle", default=1),
            WizardField("comment", "Comment", "text"),
        ],
    )),
    "W18": _planned("W18", "query_routing", "Query Cache Rule",
                    "Configure cache_ttl/cache_empty_result/cache_timeout for a query",
                    "database", "mysql_query_rules"),
    "W19": _planned("W19", "query_routing", "Query Rewrite Rule",
                    "Set match_pattern + replace_pattern for SQL rewriting", "edit", "mysql_query_rules"),
    "W20": _planned("W20", "query_routing", "Query Timeout/Rate-Limit Rule",
                    "Configure timeout, delay and retries for a query", "clock", "mysql_query_rules"),
    "W21": _planned("W21", "query_routing", "Query Mirror Rule",
                    "Mirror traffic to a test hostgroup (mirror_hostgroup)", "copy", "mysql_query_rules"),
    "W22": _planned("W22", "query_routing", "Fast Routing Table",
                    "Configure O(1) fast routing (mysql_query_rules_fast_routing)",
                    "zap", "mysql_query_rules_fast_routing"),
    "W23": _planned("W23", "query_routing", "Query Logging Rule",
                    "Enable logging for specific queries (log=1)", "file-text", "mysql_query_rules"),

    # ── Replication & cluster topology (W24-W28) ──
    "W24": ReplicationHostgroupsWizard(WizardDefinition(
        id="W24",
        category="replication_topology",
        name="Configure Primary/Replica Replication",
        description="Register writer/reader hostgroups for traditional async replication",
        icon="git-branch",
        target_table="mysql_replication_hostgroups",
        auto_apply_module="MYSQL SERVERS",
        fields=[
            WizardField("writer_hostgroup", "Writer Hostgroup", "number", required=True),
            WizardField("reader_hostgroup", "Reader Hostgroup", "number", required=True),
            WizardField("check_type", "Check Type", "select", default="read_only",
                        options=["read_only", "innodb_read_only", "super_read_only",
                                 "read_only|innodb_read_only", "read_only&innodb_read_only"]),
            WizardField("comment", "Comment", "text", default="primary-replica"),
        ],
    )),
    "W25": _planned("W25", "replication_topology", "Configure Group Replication",
                    "Configure mysql_group_replication_hostgroups", "git-branch",
                    "mysql_group_replication_hostgroups"),
    "W26": _planned("W26", "replication_topology", "Configure Galera Cluster",
                    "Configure mysql_galera_hostgroups", "git-branch", "mysql_galera_hostgroups"),
    "W27": _planned("W27", "replication_topology", "Configure AWS Aurora Cluster",
                    "Configure mysql_aws_aurora_hostgroups", "cloud", "mysql_aws_aurora_hostgroups"),
    "W28": _planned("W28", "replication_topology", "Configure PostgreSQL Replication",
                    "Configure pgsql_replication_hostgroups", "git-branch", "pgsql_replication_hostgroups"),

    # ── System configuration (W29-W42) ──
    "W29": GlobalVariableUpdateWizard(WizardDefinition(
        id="W29",
        category="system_config",
        name="Connection Pool Variables",
        description="Update mysql-* connection pool variables (max_connections, connect_timeout_*, ...)",
        icon="plug",
        target_table="global_variables",
        auto_apply_module="MYSQL VARIABLES",
        fields=[
            WizardField("variables", "Variables (JSON: {name: value})", "textarea", required=True,
                        default='{"mysql-max_connections": "2048"}',
                        placeholder='{"mysql-max_connections": "2048", "mysql-connect_timeout_server": "10000"}'),
        ],
    )),
    "W30": GlobalVariableUpdateWizard(WizardDefinition(
        id="W30",
        category="system_config",
        name="Query Processing Variables",
        description="Update query processor variables (query_digests, threshold_query_length, ...)",
        icon="cpu",
        target_table="global_variables",
        auto_apply_module="MYSQL VARIABLES",
        fields=[
            WizardField("variables", "Variables (JSON: {name: value})", "textarea", required=True,
                        default='{"mysql-query_digests": "true"}'),
        ],
    )),
    "W31": GlobalVariableUpdateWizard(WizardDefinition(
        id="W31",
        category="system_config",
        name="Query Cache Global Variables",
        description="Update query cache variables (query_cache_size_MB, ...)",
        icon="database",
        target_table="global_variables",
        auto_apply_module="MYSQL VARIABLES",
        fields=[
            WizardField("variables", "Variables (JSON: {name: value})", "textarea", required=True,
                        default='{"mysql-query_cache_size_MB": "256"}'),
        ],
    )),
    "W32": _planned("W32", "system_config", "Multiplexing Variables",
                    "Configure multiplex-related variables", "shuffle", "global_variables"),
    "W33": _planned("W33", "system_config", "Logging & Events Variables",
                    "Configure eventslog/auditlog variables", "file-text", "global_variables"),
    "W34": _planned("W34", "system_config", "Monitor Variables",
                    "Configure mysql-monitor_* variables", "activity", "global_variables"),
    "W35": _planned("W35", "system_config", "ProxySQL Admin User Management",
                    "Manage admin-admin_credentials / stats_credentials", "shield", "global_variables"),
    "W36": _planned("W36", "system_config", "Network Interface Variables",
                    "Configure admin-mysql_ifaces / admin-web_enabled / ...", "network", "global_variables"),
    "W37": _planned("W37", "system_config", "Cluster Node Management",
                    "Add/remove proxysql_servers entries", "server", "proxysql_servers"),
    "W38": _planned("W38", "system_config", "Cluster Sync Variables",
                    "Configure admin-cluster_* variables", "refresh-cw", "global_variables"),
    "W39": _planned("W39", "system_config", "Scheduler Task Management",
                    "Add/edit scheduler entries", "clock", "scheduler"),
    "W40": _planned("W40", "system_config", "REST API Route Management",
                    "Add/edit restapi_routes entries", "code", "restapi_routes"),
    "W41": _planned("W41", "system_config", "SSL/TLS Backend Variables",
                    "Configure mysql-ssl_* variables", "lock", "global_variables"),
    "W42": _planned("W42", "system_config", "Charset & Version Variables",
                    "Configure default_charset / server_version / ...", "type", "global_variables"),

    # ── Firewall & security (W43-W45) ──
    "W43": _planned("W43", "firewall_security", "User Whitelist",
                    "Manage mysql_firewall_whitelist_users", "shield", "mysql_firewall_whitelist_users"),
    "W44": _planned("W44", "firewall_security", "Rule Whitelist",
                    "Manage mysql_firewall_whitelist_rules", "shield", "mysql_firewall_whitelist_rules"),
    "W45": _planned("W45", "firewall_security", "SQL Injection Protection",
                    "Configure firewall rules for SQL injection detection", "shield",
                    "mysql_firewall_whitelist_rules"),

    # ── Operations & config sync (W46-W52) ──
    "W46": ConfigSyncWizard(WizardDefinition(
        id="W46",
        category="operations",
        name="Apply All Config Changes",
        description="Apply all pending config changes to runtime (LOAD ... TO RUNTIME)",
        icon="sync",
        target_table="mysql_servers",
        auto_apply_module="MYSQL SERVERS",
        fields=[
            WizardField("action", "Action", "select", required=True, default="apply",
                        options=[{"value": "apply", "label": "apply"},
                                 {"value": "save", "label": "save"}]),
        ],
    )),
    "W47": ConfigSyncWizard(WizardDefinition(
        id="W47",
        category="operations",
        name="Save All Config to Disk",
        description="Persist all runtime config to disk (SAVE ... TO DISK)",
        icon="save",
        target_table="mysql_servers",
        auto_apply_module="MYSQL SERVERS",
        fields=[
            WizardField("action", "Action", "select", required=True, default="save",
                        options=[{"value": "save", "label": "save"},
                                 {"value": "apply", "label": "apply"}]),
        ],
    )),
    "W48": _planned("W48", "operations", "Config Backup",
                    "Export current ProxySQL configuration to a backup file", "download", ""),
    "W49": _planned("W49", "operations", "Config Restore",
                    "Restore ProxySQL configuration from a backup file", "upload", ""),
    "W50": LoadFromDiskWizard(WizardDefinition(
        id="W50",
        category="operations",
        name="Load All From Disk",
        description="Load all config modules from disk into memory (LOAD ... TO MEMORY)",
        icon="download",
        target_table="mysql_servers",
        auto_apply_module="MYSQL SERVERS",
        fields=[],
    )),
    "W51": ResetStatsWizard(WizardDefinition(
        id="W51",
        category="operations",
        name="Reset Statistics",
        description="Reset ProxySQL statistics counters (STATS_RESET)",
        icon="rotate-ccw",
        target_table="stats_mysql_global",
        fields=[],
    )),
    "W52": _planned("W52", "operations", "Flush Query Cache",
                    "Flush the ProxySQL query cache", "trash-2", "stats_mysql_global"),

    # ── Monitoring & diagnostics (W53-W63) ──
    "W53": _planned("W53", "monitoring", "Slow / High-Frequency Query Analysis",
                    "Visualize Top-N slow/high-frequency queries from stats_mysql_query_digest",
                    "bar-chart", "stats_mysql_query_digest"),
    "W54": _planned("W54", "monitoring", "Query Command Statistics",
                    "View per-command statistics from stats_mysql_commands_counters",
                    "bar-chart", "stats_mysql_commands_counters"),
    "W55": _planned("W55", "monitoring", "Query Rule Hit Statistics",
                    "Show hit counts per rule from stats_mysql_query_rules",
                    "bar-chart", "stats_mysql_query_rules"),
    "W56": _planned("W56", "monitoring", "Query Error Analysis",
                    "Analyze backend errors from stats_mysql_errors",
                    "alert-triangle", "stats_mysql_errors"),
    "W57": _planned("W57", "monitoring", "Connection Pool Monitoring",
                    "Visualize connection pool usage from stats_mysql_connection_pool",
                    "activity", "stats_mysql_connection_pool"),
    "W58": _planned("W58", "monitoring", "Realtime Process List",
                    "Show current active sessions from stats_mysql_processlist",
                    "list", "stats_mysql_processlist"),
    "W59": _planned("W59", "monitoring", "User Connection Statistics",
                    "Show per-user connection stats from stats_mysql_users",
                    "users", "stats_mysql_users"),
    "W60": _planned("W60", "monitoring", "Backend Topology Visualization",
                    "Visualize hostgroup topology and read-write split flow",
                    "share-2", "mysql_servers"),
    "W61": _planned("W61", "monitoring", "Global Status Panel",
                    "Show global status & memory metrics", "gauge", "stats_mysql_global"),
    "W62": _planned("W62", "monitoring", "GTID Sync Status",
                    "View GTID execution status per backend", "git-commit", "stats_mysql_gtid_executed"),
    "W63": _planned("W63", "monitoring", "ProxySQL Cluster Status",
                    "View cluster node status & config consistency",
                    "servers", "stats_proxysql_servers_metrics"),
}


# ── Merge: replace planned stubs with real implementations ──────
# The modules in ``app.services.wizards`` provide concrete
# implementations (with full field definitions) for the wizards that
# were formerly "planned" stubs above. We iterate over each module's
# ``DEFINITIONS`` dict — which maps ``wizard_id`` to a
# ``(WizardDefinition, WizardClass)`` tuple — and replace the stub
# with an instantiated wizard.
for _module in (_monitor_mod, _ops_mod, _system_mod, _firewall_mod,
                _routing_mod, _topology_mod, _server_mod, _user_mod):
    for _wid, (_def, _cls) in _module.DEFINITIONS.items():
        WIZARD_REGISTRY[_wid] = _cls(_def)

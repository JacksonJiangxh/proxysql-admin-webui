"""W32-W42: System configuration wizards.

These wizards update ProxySQL ``global_variables`` and related config
tables (scheduler, restapi_routes, proxysql_servers, etc.).
"""
from app.services.wizard_engine import BaseWizard, WizardDefinition, WizardField, _quote_val


class _JsonVariablesWizard(BaseWizard):
    """Shared helper: update a set of global_variables from a JSON mapping."""

    VARIABLE_PREFIX = "mysql-"

    def validate(self, fields: dict) -> list[str]:
        errors = []
        variables = fields.get("variables")
        if not variables or not isinstance(variables, dict):
            errors.append("variables mapping ({name: value}) is required")
            return errors
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


class MultiplexingVariablesWizard(_JsonVariablesWizard):
    """W32: Multiplex-related variables."""
    VARIABLE_PREFIX = "mysql-"


class LoggingEventsWizard(_JsonVariablesWizard):
    """W33: Logging & events variables."""
    VARIABLE_PREFIX = "mysql-"


class MonitorVariablesWizard(_JsonVariablesWizard):
    """W34: mysql-monitor_* variables."""
    VARIABLE_PREFIX = "mysql-monitor_"


class AdminUserManagementWizard(BaseWizard):
    """W35: Manage ProxySQL admin credentials (admin-admin_credentials).

    Parses a list of user:password entries and builds the credential
    string for the ``admin-admin_credentials`` (or ``admin-stats_credentials``)
    global variable.
    """

    def validate(self, fields: dict) -> list[str]:
        errors = []
        action = fields.get("action", "list")
        if action not in ("list", "add", "remove", "set"):
            errors.append("action must be list, add, remove, or set")
        if action == "add":
            if not fields.get("username"):
                errors.append("username is required for add action")
            if not fields.get("password"):
                errors.append("password is required for add action")
        if action == "set":
            if not fields.get("credentials"):
                errors.append("credentials string is required for set action")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        action = fields.get("action", "list")
        target = fields.get("target", "admin_credentials")
        var_name = f"admin-{target}"

        if action == "list":
            return [f"SELECT variable_value FROM global_variables WHERE variable_name = '{var_name}'"]

        if action == "set":
            creds = fields["credentials"]
            return [
                f"UPDATE global_variables SET variable_value = {_quote_val(creds)} "
                f"WHERE variable_name = {_quote_val(var_name)}"
            ]

        # add / remove would need to read current value first; for SQL preview
        # we generate the UPDATE with the new credentials string
        username = fields.get("username", "")
        password = fields.get("password", "")
        if action == "add":
            # Append user:password to existing credentials (concatenated with comma)
            # The actual merge logic is handled at execute time via a read-then-update.
            new_cred = f"{username}:{password}"
            return [
                f"UPDATE global_variables SET variable_value = "
                f"variable_value || ',{new_cred}' "
                f"WHERE variable_name = {_quote_val(var_name)}"
            ]
        if action == "remove":
            return [
                f"UPDATE global_variables SET variable_value = '' "
                f"WHERE variable_name = {_quote_val(var_name)}"
            ]
        return []


class NetworkInterfaceWizard(_JsonVariablesWizard):
    """W36: admin-* network interface variables."""
    VARIABLE_PREFIX = "admin-"


class ClusterNodeWizard(BaseWizard):
    """W37: Add/remove ProxySQL cluster nodes (proxysql_servers table)."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        action = fields.get("action", "add")
        if action not in ("add", "remove", "list"):
            errors.append("action must be add, remove, or list")
        if action in ("add", "remove"):
            if not fields.get("hostname"):
                errors.append("hostname is required")
            if fields.get("port") is None:
                errors.append("port is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        action = fields.get("action", "add")
        if action == "list":
            return ["SELECT hostname, port, weight, comment FROM proxysql_servers"]
        if action == "remove":
            return [
                f"DELETE FROM proxysql_servers WHERE hostname = {_quote_val(fields['hostname'])} "
                f"AND port = {int(fields['port'])}"
            ]
        # add
        cols = ["hostname", "port", "weight", "comment"]
        vals = [
            fields["hostname"],
            int(fields.get("port", 6032)),
            int(fields.get("weight", 1)),
            fields.get("comment", ""),
        ]
        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO proxysql_servers ({cols_str}) VALUES ({vals_str})"]


class ClusterSyncVariablesWizard(_JsonVariablesWizard):
    """W38: admin-cluster_* sync variables."""
    VARIABLE_PREFIX = "admin-cluster_"


class SchedulerTaskWizard(BaseWizard):
    """W39: Add/edit/delete scheduler entries."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        action = fields.get("action", "add")
        if action not in ("add", "update", "delete", "list"):
            errors.append("action must be add, update, delete, or list")
        if action == "add":
            if not fields.get("filename"):
                errors.append("filename is required for add action")
            if fields.get("interval_ms") is not None:
                im = int(fields["interval_ms"])
                if not (100 <= im <= 100000000):
                    errors.append("interval_ms must be between 100 and 100000000")
        if action in ("update", "delete") and fields.get("id") is None:
            errors.append("id is required for update/delete action")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        action = fields.get("action", "add")
        if action == "list":
            return ["SELECT id, active, interval_ms, filename, arg1, arg2, arg3, arg4, arg5, comment FROM scheduler"]
        if action == "delete":
            return [f"DELETE FROM scheduler WHERE id = {int(fields['id'])}"]
        if action == "update":
            updates = {}
            for key in ("active", "interval_ms", "filename", "arg1", "arg2",
                        "arg3", "arg4", "arg5", "comment"):
                if fields.get(key) is not None:
                    updates[key] = fields[key]
            if not updates:
                return []
            set_clause = ", ".join(f"{k} = {_quote_val(v)}" for k, v in updates.items())
            return [f"UPDATE scheduler SET {set_clause} WHERE id = {int(fields['id'])}"]
        # add
        cols = ["active", "interval_ms", "filename", "comment"]
        vals = [
            int(fields.get("active", 1)),
            int(fields.get("interval_ms", 1000)),
            fields["filename"],
            fields.get("comment", ""),
        ]
        for arg_key in ("arg1", "arg2", "arg3", "arg4", "arg5"):
            if fields.get(arg_key):
                cols.append(arg_key)
                vals.append(fields[arg_key])
        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO scheduler ({cols_str}) VALUES ({vals_str})"]


class RestApiRouteWizard(BaseWizard):
    """W40: Add/edit/delete REST API routes (restapi_routes table)."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        action = fields.get("action", "add")
        if action not in ("add", "update", "delete", "list"):
            errors.append("action must be add, update, delete, or list")
        if action == "add":
            if not fields.get("uri"):
                errors.append("uri is required")
            if not fields.get("script"):
                errors.append("script is required")
            method = fields.get("method", "GET")
            if method not in ("GET", "POST"):
                errors.append("method must be GET or POST")
        if action in ("update", "delete") and fields.get("id") is None:
            errors.append("id is required for update/delete action")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        action = fields.get("action", "add")
        if action == "list":
            return ["SELECT id, active, timeout_ms, method, uri, script, comment FROM restapi_routes"]
        if action == "delete":
            return [f"DELETE FROM restapi_routes WHERE id = {int(fields['id'])}"]
        if action == "update":
            updates = {}
            for key in ("active", "timeout_ms", "method", "uri", "script", "comment"):
                if fields.get(key) is not None:
                    updates[key] = fields[key]
            if not updates:
                return []
            set_clause = ", ".join(f"{k} = {_quote_val(v)}" for k, v in updates.items())
            return [f"UPDATE restapi_routes SET {set_clause} WHERE id = {int(fields['id'])}"]
        # add
        cols = ["active", "timeout_ms", "method", "uri", "script", "comment"]
        vals = [
            int(fields.get("active", 1)),
            int(fields.get("timeout_ms", 1000)),
            fields.get("method", "GET"),
            fields["uri"],
            fields["script"],
            fields.get("comment", ""),
        ]
        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO restapi_routes ({cols_str}) VALUES ({vals_str})"]


class SslBackendWizard(_JsonVariablesWizard):
    """W41: mysql-ssl_* backend connection SSL variables."""
    VARIABLE_PREFIX = "mysql-ssl_"


class CharsetVersionWizard(_JsonVariablesWizard):
    """W42: Charset & version variables."""
    VARIABLE_PREFIX = "mysql-"


# ── Wizard Definitions ──────────────────────────────────────────

def _json_fields(label, desc, default):
    return [WizardField("variables", f"{label} (JSON: {{name: value}})", "textarea",
                        required=True, default=default,
                        placeholder='{"mysql-example": "value"}')]


DEFINITIONS = {
    "W32": (WizardDefinition(
        id="W32", category="system_config", name="Multiplexing Variables",
        description="Configure multiplex-related variables (multiplexing, max_transaction_time, ...)",
        icon="shuffle", target_table="global_variables", auto_apply_module="MYSQL VARIABLES",
        fields=_json_fields("Variables", "mpx", '{"mysql-multiplexing": "true"}'),
        status="implemented",
    ), MultiplexingVariablesWizard),

    "W33": (WizardDefinition(
        id="W33", category="system_config", name="Logging & Events Variables",
        description="Configure eventslog/auditlog variables",
        icon="file-text", target_table="global_variables", auto_apply_module="MYSQL VARIABLES",
        fields=_json_fields("Variables", "log", '{"mysql-eventslog_filename": "events.log"}'),
        status="implemented",
    ), LoggingEventsWizard),

    "W34": (WizardDefinition(
        id="W34", category="system_config", name="MySQL Monitor User & Variables",
        description="Configure the monitor credentials ProxySQL uses to check backend MySQL health (mysql-monitor_username, mysql-monitor_password) and monitoring intervals",
        icon="activity", target_table="global_variables", auto_apply_module="MYSQL VARIABLES",
        fields=_json_fields("Variables", "mon",
                            '{"mysql-monitor_username": "monitor", "mysql-monitor_password": "monitor"}'),
        status="implemented",
    ), MonitorVariablesWizard),

    "W35": (WizardDefinition(
        id="W35", category="system_config", name="ProxySQL Admin User Management",
        description="Manage admin-admin_credentials / admin-stats_credentials users",
        icon="shield", target_table="global_variables", auto_apply_module="ADMIN VARIABLES",
        fields=[
            WizardField("action", "Action", "select", required=True, default="list",
                        options=[{"value": "list", "label": "List Current"},
                                 {"value": "add", "label": "Add User"},
                                 {"value": "remove", "label": "Remove User"},
                                 {"value": "set", "label": "Set Credentials String"}]),
            WizardField("target", "Target Variable", "select", default="admin_credentials",
                        options=[{"value": "admin_credentials", "label": "admin_credentials"},
                                 {"value": "stats_credentials", "label": "stats_credentials"}]),
            WizardField("username", "Username (for add/remove)", "text"),
            WizardField("password", "Password (for add)", "password"),
            WizardField("credentials", "Full Credentials String (for set)", "text",
                        placeholder="user1:pass1,user2:pass2"),
        ], status="implemented",
    ), AdminUserManagementWizard),

    "W36": (WizardDefinition(
        id="W36", category="system_config", name="Network Interface Variables",
        description="Configure admin-mysql_ifaces / admin-web_enabled / admin-restapi_enabled",
        icon="network", target_table="global_variables", auto_apply_module="ADMIN VARIABLES",
        fields=_json_fields("Variables", "net",
                            '{"admin-mysql_ifaces": "0.0.0.0:6032"}'),
        status="implemented",
    ), NetworkInterfaceWizard),

    "W37": (WizardDefinition(
        id="W37", category="system_config", name="Cluster Node Management",
        description="Add/remove proxysql_servers entries for ProxySQL cluster",
        icon="server", target_table="proxysql_servers", auto_apply_module="PROXYSQL SERVERS",
        fields=[
            WizardField("action", "Action", "select", required=True, default="add",
                        options=[{"value": "add", "label": "Add Node"},
                                 {"value": "remove", "label": "Remove Node"},
                                 {"value": "list", "label": "List Nodes"}]),
            WizardField("_lookup", "Select Existing Node (auto-fill for remove)", "lookup",
                        lookup={
                            "table": "proxysql_servers",
                            "label_template": "{hostname}:{port} | weight={weight}",
                            "linked_fields": {
                                "hostname": "hostname",
                                "port": "port",
                                "weight": "weight",
                                "comment": "comment",
                            },
                        }),
            WizardField("hostname", "Hostname", "text"),
            WizardField("port", "Port", "number", default=6032, min=1, max=65535),
            WizardField("weight", "Weight", "number", default=1, min=0),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), ClusterNodeWizard),

    "W38": (WizardDefinition(
        id="W38", category="system_config", name="Cluster Sync Variables",
        description="Configure admin-cluster_* sync parameters",
        icon="refresh-cw", target_table="global_variables", auto_apply_module="ADMIN VARIABLES",
        fields=_json_fields("Variables", "cluster",
                            '{"admin-cluster_username": "admin", "admin-cluster_password": "admin"}'),
        status="implemented",
    ), ClusterSyncVariablesWizard),

    "W39": (WizardDefinition(
        id="W39", category="system_config", name="Scheduler Task Management",
        description="Add/edit/delete scheduled script tasks (scheduler table)",
        icon="clock", target_table="scheduler", auto_apply_module="SCHEDULER",
        fields=[
            WizardField("action", "Action", "select", required=True, default="add",
                        options=[{"value": "add", "label": "Add Task"},
                                 {"value": "update", "label": "Update Task"},
                                 {"value": "delete", "label": "Delete Task"},
                                 {"value": "list", "label": "List Tasks"}]),
            WizardField("_lookup", "Select Existing Task (auto-fill for update/delete)", "lookup",
                        lookup={
                            "table": "scheduler",
                            "label_template": "id={id} | {filename} | interval={interval_ms}ms",
                            "linked_fields": {
                                "id": "id",
                                "active": "active",
                                "interval_ms": "interval_ms",
                                "filename": "filename",
                                "arg1": "arg1",
                                "arg2": "arg2",
                                "arg3": "arg3",
                                "arg4": "arg4",
                                "arg5": "arg5",
                                "comment": "comment",
                            },
                        }),
            WizardField("id", "Task ID (for update/delete)", "number"),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("interval_ms", "Interval (ms)", "number", default=1000, min=100, max=100000000),
            WizardField("filename", "Script Path", "text", placeholder="/path/to/script.sh"),
            WizardField("arg1", "Argument 1", "text"),
            WizardField("arg2", "Argument 2", "text"),
            WizardField("arg3", "Argument 3", "text"),
            WizardField("arg4", "Argument 4", "text"),
            WizardField("arg5", "Argument 5", "text"),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), SchedulerTaskWizard),

    "W40": (WizardDefinition(
        id="W40", category="system_config", name="REST API Route Management",
        description="Add/edit/delete custom REST API endpoints (restapi_routes table)",
        icon="code", target_table="restapi_routes", auto_apply_module="PROXYSQL SERVERS",
        fields=[
            WizardField("action", "Action", "select", required=True, default="add",
                        options=[{"value": "add", "label": "Add Route"},
                                 {"value": "update", "label": "Update Route"},
                                 {"value": "delete", "label": "Delete Route"},
                                 {"value": "list", "label": "List Routes"}]),
            WizardField("_lookup", "Select Existing Route (auto-fill for update/delete)", "lookup",
                        lookup={
                            "table": "restapi_routes",
                            "label_template": "id={id} | {method} {uri} | active={active}",
                            "linked_fields": {
                                "id": "id",
                                "active": "active",
                                "timeout_ms": "timeout_ms",
                                "method": "method",
                                "uri": "uri",
                                "script": "script",
                                "comment": "comment",
                            },
                        }),
            WizardField("id", "Route ID (for update/delete)", "number"),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("timeout_ms", "Timeout (ms)", "number", default=1000),
            WizardField("method", "HTTP Method", "select", default="GET",
                        options=[{"value": "GET", "label": "GET"}, {"value": "POST", "label": "POST"}]),
            WizardField("uri", "URI", "text", placeholder="/custom/route"),
            WizardField("script", "Script Path", "text", placeholder="/path/to/script"),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), RestApiRouteWizard),

    "W41": (WizardDefinition(
        id="W41", category="system_config", name="SSL/TLS Backend Variables",
        description="Configure mysql-ssl_* variables for backend SSL connections",
        icon="lock", target_table="global_variables", auto_apply_module="MYSQL VARIABLES",
        fields=_json_fields("Variables", "ssl",
                            '{"mysql-ssl_p2s_ca": "", "mysql-ssl_p2s_cert": ""}'),
        status="implemented",
    ), SslBackendWizard),

    "W42": (WizardDefinition(
        id="W42", category="system_config", name="Charset & Version Variables",
        description="Configure default_charset / server_version / handle_unknown_charset",
        icon="type", target_table="global_variables", auto_apply_module="MYSQL VARIABLES",
        fields=_json_fields("Variables", "charset",
                            '{"mysql-default_charset": "utf8mb4", "mysql-server_version": "8.0.30"}'),
        status="implemented",
    ), CharsetVersionWizard),
}

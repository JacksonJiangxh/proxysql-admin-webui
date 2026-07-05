"""W10, W14-W15: Backend user management wizards."""
from app.services.wizard_engine import BaseWizard, WizardDefinition, WizardField, _quote_val


class AddPgsqlUserWizard(BaseWizard):
    """W10: Create a PostgreSQL backend user (pgsql_users table)."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if not fields.get("username"):
            errors.append("username is required")
        if not fields.get("password"):
            errors.append("password is required")
        if fields.get("default_hostgroup") is None:
            errors.append("default_hostgroup is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        cols = ["username", "password", "active", "default_hostgroup",
                "max_connections", "transaction_persistent", "fast_forward",
                "frontend", "backend", "comment"]
        vals = [
            fields["username"],
            fields.get("password", ""),
            int(fields.get("active", 1)),
            int(fields.get("default_hostgroup", 0)),
            int(fields.get("max_connections", 10000)),
            int(fields.get("transaction_persistent", 1)),
            int(fields.get("fast_forward", 0)),
            int(fields.get("frontend", 1)),
            int(fields.get("backend", 1)),
            fields.get("comment", ""),
        ]
        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO pgsql_users ({cols_str}) VALUES ({vals_str})"]


class LdapUserMappingWizard(BaseWizard):
    """W14: Configure LDAP user mapping (mysql_ldap_mapping table)."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if not fields.get("frontend_entity"):
            errors.append("frontend_entity is required")
        if not fields.get("backend_entity"):
            errors.append("backend_entity is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        cols = ["priority", "frontend_entity", "backend_entity", "active", "comment"]
        vals = [
            int(fields.get("priority", 1)),
            fields["frontend_entity"],
            fields["backend_entity"],
            int(fields.get("active", 1)),
            fields.get("comment", ""),
        ]
        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO mysql_ldap_mapping ({cols_str}) VALUES ({vals_str})"]


class FrontendBackendUserWizard(BaseWizard):
    """W15: Control ProxySQL user direction (frontend / backend).

    ProxySQL's ``frontend`` and ``backend`` columns are **direction
    flags** for a single user — they are NOT a username-mapping
    mechanism.  The same username is always forwarded to the backend
    MySQL when a client connects through ProxySQL.

    Meaning of each flag:
      frontend=1  → client CAN authenticate to ProxySQL as this user
      backend=1   → ProxySQL CAN use this user to open backend
                     connections to MySQL servers

    IMPORTANT: A row with ``frontend=1, backend=0`` alone is
    **non-functional** — the user can log into ProxySQL but cannot
    execute any query because ProxySQL has no backend credential
    for that username.

    The ONLY valid "separation" scenario is creating TWO rows for
    the SAME username (option ``split_directions``):

        INSERT INTO mysql_users (... frontend=1, backend=0 ...)
        INSERT INTO mysql_users (... frontend=0, backend=1 ...)

    This allows independently toggling each direction without
    deleting the user, while preserving normal query routing.

    Options:
      - ``both``: single row, frontend=1 backend=1 (standard user)
      - ``backend_only``: single row, frontend=0 backend=1
        (ProxySQL→MySQL pool user, clients cannot use this name)
      - ``split_directions``: TWO rows for the same username
        (frontend=1,backend=0 + frontend=0,backend=1)
    """

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if not fields.get("username"):
            errors.append("username is required")
        if not fields.get("password"):
            errors.append("password is required")
        user_type = fields.get("user_type", "both")
        if user_type not in ("backend_only", "both", "split_directions"):
            errors.append("user_type must be backend_only, both, or split_directions")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        user_type = fields.get("user_type", "both")

        cols = ["username", "password", "active", "default_hostgroup",
                "frontend", "backend", "max_connections", "comment"]

        def _build_row(fe: int, be: int, extra_comment: str = "") -> str:
            vals = [
                fields["username"],
                fields.get("password", ""),
                int(fields.get("active", 1)),
                int(fields.get("default_hostgroup", 0)),
                fe,
                be,
                int(fields.get("max_connections", 10000)),
                (fields.get("comment", "") + extra_comment).strip(),
            ]
            cols_str = ", ".join(cols)
            vals_str = ", ".join(_quote_val(v) for v in vals)
            return f"INSERT INTO mysql_users ({cols_str}) VALUES ({vals_str})"

        if user_type == "backend_only":
            return [_build_row(0, 1, " (backend-only)")]
        elif user_type == "split_directions":
            return [
                _build_row(1, 0, " (frontend direction)"),
                _build_row(0, 1, " (backend direction)"),
            ]
        else:  # both
            return [_build_row(1, 1)]


# ── Wizard Definitions ──────────────────────────────────────────

DEFINITIONS = {
    "W10": (WizardDefinition(
        id="W10", category="backend_users", name="Create PostgreSQL Backend User",
        description="Create a new PostgreSQL user for backend connections",
        icon="user", target_table="pgsql_users", auto_apply_module="PGSQL USERS",
        fields=[
            WizardField("username", "Username", "text", required=True, placeholder="e.g. app_user"),
            WizardField("password", "Password", "password", required=True),
            WizardField("default_hostgroup", "Default Hostgroup", "number", required=True, default=0),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("max_connections", "Max Connections", "number", default=10000),
            WizardField("transaction_persistent", "Transaction Persistent", "toggle", default=1),
            WizardField("fast_forward", "Fast Forward", "toggle", default=0),
            WizardField("frontend", "Frontend Auth", "toggle", default=1),
            WizardField("backend", "Backend Auth", "toggle", default=1),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), AddPgsqlUserWizard),

    "W14": (WizardDefinition(
        id="W14", category="backend_users", name="LDAP User Mapping",
        description="Configure LDAP user mapping (mysql_ldap_mapping) for enterprise LDAP auth",
        icon="users", target_table="mysql_ldap_mapping", auto_apply_module="MYSQL USERS",
        fields=[
            WizardField("priority", "Priority", "number", default=1),
            WizardField("frontend_entity", "Frontend Entity", "text", required=True),
            WizardField("backend_entity", "Backend Entity", "text", required=True),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), LdapUserMappingWizard),

    "W15": (WizardDefinition(
        id="W15", category="backend_users", name="ProxySQL User Direction Control",
        description="Control frontend/backend direction flags for a mysql_users entry. "
                    "NOT a username mapper — the same username is forwarded to backend MySQL.",
        icon="user", target_table="mysql_users", auto_apply_module="MYSQL USERS",
        guide=(
            "ProxySQL has two direction flags per user:\n"
            "  • frontend=1 → clients can use this name to log into ProxySQL\n"
            "  • backend=1  → ProxySQL can use this name to connect to backend MySQL\n\n"
            "These are NOT a username-mapping mechanism. The same username\n"
            "is always forwarded to the backend. To actually query data,\n"
            "backend=1 must be set for some row with this username.\n\n"
            "Options:\n"
            "  • both (default): One row with frontend=1, backend=1.\n"
            "    Standard user — works for most cases.\n"
            "  • backend_only: One row with frontend=0, backend=1.\n"
            "    Useful for pre-creating backend connection pools;\n"
            "    clients cannot authenticate with this name.\n"
            "  • split_directions: TWO rows for the same username:\n"
            "    one (f=1,b=0) + one (f=0,b=1). Lets you toggle each\n"
            "    direction independently without deleting the user.\n\n"
            "IMPORTANT: The user must also exist on the backend MySQL\n"
            "server with the same password — otherwise queries will\n"
            "fail with access-denied errors."
        ),
        fields=[
            WizardField("user_type", "User Type", "select", required=True, default="both",
                        options=[{"value": "both", "label": "both"},
                                 {"value": "backend_only", "label": "backend_only"},
                                 {"value": "split_directions", "label": "split_directions"}]),
            WizardField("username", "Username", "text", required=True),
            WizardField("password", "Password", "password", required=True),
            WizardField("default_hostgroup", "Default Hostgroup", "number", default=0),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("max_connections", "Max Connections", "number", default=10000),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), FrontendBackendUserWizard),
}

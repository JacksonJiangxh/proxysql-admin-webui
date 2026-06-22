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
    """W15: Configure frontend-only or backend-only users.

    Creates a mysql_users entry with frontend=0 (backend-only) or
    backend=0 (frontend-only), useful for split authentication setups.
    """

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if not fields.get("username"):
            errors.append("username is required")
        if not fields.get("password"):
            errors.append("password is required")
        user_type = fields.get("user_type", "both")
        if user_type not in ("frontend_only", "backend_only", "both"):
            errors.append("user_type must be frontend_only, backend_only, or both")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        user_type = fields.get("user_type", "both")
        if user_type == "frontend_only":
            frontend, backend = 1, 0
        elif user_type == "backend_only":
            frontend, backend = 0, 1
        else:
            frontend, backend = 1, 1

        cols = ["username", "password", "active", "default_hostgroup",
                "frontend", "backend", "max_connections", "comment"]
        vals = [
            fields["username"],
            fields.get("password", ""),
            int(fields.get("active", 1)),
            int(fields.get("default_hostgroup", 0)),
            frontend,
            backend,
            int(fields.get("max_connections", 10000)),
            fields.get("comment", ""),
        ]
        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO mysql_users ({cols_str}) VALUES ({vals_str})"]


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
        id="W15", category="backend_users", name="Frontend/Backend User Separation",
        description="Configure frontend-only or backend-only users (mysql_users)",
        icon="user", target_table="mysql_users", auto_apply_module="MYSQL USERS",
        fields=[
            WizardField("user_type", "User Type", "select", required=True, default="both",
                        options=[{"value": "frontend_only", "label": "frontend_only"},
                                 {"value": "backend_only", "label": "backend_only"},
                                 {"value": "both", "label": "both"}]),
            WizardField("username", "Username", "text", required=True),
            WizardField("password", "Password", "password", required=True),
            WizardField("default_hostgroup", "Default Hostgroup", "number", default=0),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("max_connections", "Max Connections", "number", default=10000),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), FrontendBackendUserWizard),
}

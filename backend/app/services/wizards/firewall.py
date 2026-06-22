"""W43-W45: Firewall & security wizards."""
from app.services.wizard_engine import BaseWizard, WizardDefinition, WizardField, _quote_val


class FirewallUserWhitelistWizard(BaseWizard):
    """W43: Manage mysql_firewall_whitelist_users entries."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        action = fields.get("action", "add")
        if action not in ("add", "update", "delete", "list"):
            errors.append("action must be add, update, delete, or list")
        if action in ("add", "update"):
            if not fields.get("username"):
                errors.append("username is required")
            mode = fields.get("mode", "OFF")
            if mode not in ("OFF", "DETECTING", "PROTECTING"):
                errors.append("mode must be OFF, DETECTING, or PROTECTING")
        if action in ("update", "delete") and fields.get("id") is None:
            errors.append("id is required for update/delete action")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        action = fields.get("action", "add")
        if action == "list":
            return ["SELECT id, active, username, client_address, mode, comment FROM mysql_firewall_whitelist_users"]
        if action == "delete":
            return [f"DELETE FROM mysql_firewall_whitelist_users WHERE id = {int(fields['id'])}"]
        if action == "update":
            updates = {}
            for key in ("active", "username", "client_address", "mode", "comment"):
                if fields.get(key) is not None:
                    updates[key] = fields[key]
            if not updates:
                return []
            set_clause = ", ".join(f"{k} = {_quote_val(v)}" for k, v in updates.items())
            return [f"UPDATE mysql_firewall_whitelist_users SET {set_clause} WHERE id = {int(fields['id'])}"]
        # add
        cols = ["active", "username", "client_address", "mode", "comment"]
        vals = [
            int(fields.get("active", 1)),
            fields["username"],
            fields.get("client_address", ""),
            fields.get("mode", "OFF"),
            fields.get("comment", ""),
        ]
        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO mysql_firewall_whitelist_users ({cols_str}) VALUES ({vals_str})"]


class FirewallRuleWhitelistWizard(BaseWizard):
    """W44: Manage mysql_firewall_whitelist_rules entries."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        action = fields.get("action", "add")
        if action not in ("add", "update", "delete", "list"):
            errors.append("action must be add, update, delete, or list")
        if action == "add":
            if not fields.get("username"):
                errors.append("username is required")
        if action in ("update", "delete") and fields.get("id") is None:
            errors.append("id is required for update/delete action")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        action = fields.get("action", "add")
        if action == "list":
            return ["SELECT id, active, username, client_address, schemaname, flagIN, digest, comment FROM mysql_firewall_whitelist_rules"]
        if action == "delete":
            return [f"DELETE FROM mysql_firewall_whitelist_rules WHERE id = {int(fields['id'])}"]
        if action == "update":
            updates = {}
            for key in ("active", "username", "client_address", "schemaname",
                        "flagIN", "digest", "comment"):
                if fields.get(key) is not None:
                    updates[key] = fields[key]
            if not updates:
                return []
            set_clause = ", ".join(f"{k} = {_quote_val(v)}" for k, v in updates.items())
            return [f"UPDATE mysql_firewall_whitelist_rules SET {set_clause} WHERE id = {int(fields['id'])}"]
        # add
        cols = ["active", "username", "client_address", "schemaname", "flagIN", "comment"]
        vals = [
            int(fields.get("active", 1)),
            fields["username"],
            fields.get("client_address", ""),
            fields.get("schemaname", ""),
            int(fields.get("flagIN", 0)),
            fields.get("comment", ""),
        ]
        if fields.get("digest"):
            cols.append("digest")
            vals.append(fields["digest"])
        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO mysql_firewall_whitelist_rules ({cols_str}) VALUES ({vals_str})"]


class SqlInjectionProtectionWizard(BaseWizard):
    """W45: Configure SQL injection detection (firewall + global variables)."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        action = fields.get("action", "enable")
        if action not in ("enable", "disable", "status"):
            errors.append("action must be enable, disable, or status")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        action = fields.get("action", "enable")
        if action == "status":
            return [
                "SELECT variable_name, variable_value FROM global_variables "
                "WHERE variable_name IN ('mysql-automatic_detect_sqli', "
                "'mysql-firewall_whitelist_enabled', 'mysql-firewall_whitelist_errormsg')"
            ]
        if action == "enable":
            return [
                "UPDATE global_variables SET variable_value = 'true' "
                "WHERE variable_name = 'mysql-automatic_detect_sqli'",
                "UPDATE global_variables SET variable_value = 'true' "
                "WHERE variable_name = 'mysql-firewall_whitelist_enabled'",
            ]
        # disable
        return [
            "UPDATE global_variables SET variable_value = 'false' "
            "WHERE variable_name = 'mysql-automatic_detect_sqli'",
            "UPDATE global_variables SET variable_value = 'false' "
            "WHERE variable_name = 'mysql-firewall_whitelist_enabled'",
        ]


# ── Wizard Definitions ──────────────────────────────────────────

DEFINITIONS = {
    "W43": (WizardDefinition(
        id="W43", category="firewall_security", name="Firewall User Whitelist",
        description="Manage mysql_firewall_whitelist_users (username, client_address, mode)",
        icon="shield", target_table="mysql_firewall_whitelist_users",
        auto_apply_module="MYSQL FIREWALL",
        fields=[
            WizardField("action", "Action", "select", required=True, default="add",
                        options=[{"value": "add", "label": "Add"},
                                 {"value": "update", "label": "Update"},
                                 {"value": "delete", "label": "Delete"},
                                 {"value": "list", "label": "List"}]),
            WizardField("_lookup", "Select Existing Entry (auto-fill for update/delete)", "lookup",
                        lookup={
                            "table": "mysql_firewall_whitelist_users",
                            "label_template": "id={id} | {username}@{client_address} | {mode}",
                            "linked_fields": {
                                "id": "id",
                                "active": "active",
                                "username": "username",
                                "client_address": "client_address",
                                "mode": "mode",
                                "comment": "comment",
                            },
                        }),
            WizardField("id", "ID (for update/delete)", "number"),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("_lookup_username", "Pick ProxySQL User (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_users",
                            "label_template": "{username} | hg={default_hostgroup}",
                            "linked_fields": {"username": "username"},
                        }),
            WizardField("username", "Username", "text"),
            WizardField("client_address", "Client Address", "text", placeholder="e.g. 10.0.0.%"),
            WizardField("mode", "Mode", "select", default="OFF",
                        options=[{"value": "OFF", "label": "OFF"},
                                 {"value": "DETECTING", "label": "DETECTING"},
                                 {"value": "PROTECTING", "label": "PROTECTING"}]),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), FirewallUserWhitelistWizard),

    "W44": (WizardDefinition(
        id="W44", category="firewall_security", name="Firewall Rule Whitelist",
        description="Manage mysql_firewall_whitelist_rules (username, digest, flagIN)",
        icon="shield", target_table="mysql_firewall_whitelist_rules",
        auto_apply_module="MYSQL FIREWALL",
        fields=[
            WizardField("action", "Action", "select", required=True, default="add",
                        options=[{"value": "add", "label": "Add"},
                                 {"value": "update", "label": "Update"},
                                 {"value": "delete", "label": "Delete"},
                                 {"value": "list", "label": "List"}]),
            WizardField("_lookup", "Select Existing Rule (auto-fill for update/delete)", "lookup",
                        lookup={
                            "table": "mysql_firewall_whitelist_rules",
                            "label_template": "id={id} | {username}@{client_address}",
                            "linked_fields": {
                                "id": "id",
                                "active": "active",
                                "username": "username",
                                "client_address": "client_address",
                                "schemaname": "schemaname",
                                "flagIN": "flagIN",
                                "digest": "digest",
                                "comment": "comment",
                            },
                        }),
            WizardField("id", "ID (for update/delete)", "number"),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("_lookup_username", "Pick ProxySQL User (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_users",
                            "label_template": "{username} | hg={default_hostgroup}",
                            "linked_fields": {"username": "username"},
                        }),
            WizardField("username", "Username", "text"),
            WizardField("client_address", "Client Address", "text"),
            WizardField("schemaname", "Schema", "text"),
            WizardField("flagIN", "Flag IN", "number", default=0),
            WizardField("digest", "Digest", "text"),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), FirewallRuleWhitelistWizard),

    "W45": (WizardDefinition(
        id="W45", category="firewall_security", name="SQL Injection Protection",
        description="Enable/disable automatic SQL injection detection & firewall",
        icon="shield", target_table="global_variables", auto_apply_module="MYSQL VARIABLES",
        fields=[
            WizardField("action", "Action", "select", required=True, default="enable",
                        options=[{"value": "enable", "label": "Enable Protection"},
                                 {"value": "disable", "label": "Disable Protection"},
                                 {"value": "status", "label": "Check Status"}]),
        ], status="implemented",
    ), SqlInjectionProtectionWizard),
}

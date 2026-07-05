"""W18-W23, W69: Query routing rule wizards (mysql_query_rules variants)."""
from app.services.wizard_engine import BaseWizard, WizardDefinition, WizardField, _quote_val


class DeleteQueryRuleWizard(BaseWizard):
    """W69: Delete a query routing rule from mysql_query_rules by rule_id."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if fields.get("rule_id") is None:
            errors.append("rule_id is required to identify the rule")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        return [f"DELETE FROM mysql_query_rules WHERE rule_id = {int(fields['rule_id'])}"]


def _build_rule_insert(fields: dict, extra_cols: list, extra_vals: list) -> str:
    """Build an INSERT into mysql_query_rules with common + extra columns."""
    cols = ["rule_id", "active"]
    vals = [int(fields["rule_id"]), int(fields.get("active", 1))]

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

    cols.extend(extra_cols)
    vals.extend(extra_vals)

    if fields.get("destination_hostgroup") is not None:
        cols.append("destination_hostgroup")
        vals.append(int(fields["destination_hostgroup"]))
    if fields.get("apply") is not None:
        cols.append("apply")
        vals.append(int(fields.get("apply", 1)))
    if fields.get("comment"):
        cols.append("comment")
        vals.append(fields["comment"])

    cols_str = ", ".join(cols)
    vals_str = ", ".join(_quote_val(v) for v in vals)
    return f"INSERT INTO mysql_query_rules ({cols_str}) VALUES ({vals_str})"


class QueryCacheRuleWizard(BaseWizard):
    """W18: Configure query cache (cache_ttl, cache_empty_result, cache_timeout)."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if fields.get("rule_id") is None:
            errors.append("rule_id is required")
        if not fields.get("match_digest") and not fields.get("match_pattern"):
            errors.append("Either match_digest or match_pattern is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        extra_cols = ["cache_ttl", "cache_empty_result", "cache_timeout"]
        extra_vals = [
            int(fields.get("cache_ttl", 5000)),
            int(fields.get("cache_empty_result", 0)),
            int(fields.get("cache_timeout", 1000)),
        ]
        return [_build_rule_insert(fields, extra_cols, extra_vals)]


class QueryRewriteRuleWizard(BaseWizard):
    """W19: Configure query rewrite (match_pattern + replace_pattern)."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if fields.get("rule_id") is None:
            errors.append("rule_id is required")
        if not fields.get("match_pattern"):
            errors.append("match_pattern is required for query rewriting")
        if not fields.get("replace_pattern"):
            errors.append("replace_pattern is required for query rewriting")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        extra_cols = ["replace_pattern"]
        extra_vals = [fields["replace_pattern"]]
        return [_build_rule_insert(fields, extra_cols, extra_vals)]


class QueryTimeoutRuleWizard(BaseWizard):
    """W20: Configure query timeout / delay / retries."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if fields.get("rule_id") is None:
            errors.append("rule_id is required")
        if not fields.get("match_digest") and not fields.get("match_pattern"):
            errors.append("Either match_digest or match_pattern is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        extra_cols = ["timeout", "delay", "retries"]
        extra_vals = [
            int(fields.get("timeout", 0)),
            int(fields.get("delay", 0)),
            int(fields.get("retries", 0)),
        ]
        return [_build_rule_insert(fields, extra_cols, extra_vals)]


class QueryMirrorRuleWizard(BaseWizard):
    """W21: Configure query mirroring to a test hostgroup."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if fields.get("rule_id") is None:
            errors.append("rule_id is required")
        if not fields.get("match_digest") and not fields.get("match_pattern"):
            errors.append("Either match_digest or match_pattern is required")
        if fields.get("mirror_hostgroup") is None:
            errors.append("mirror_hostgroup is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        extra_cols = ["mirror_hostgroup"]
        extra_vals = [int(fields["mirror_hostgroup"])]
        if fields.get("mirror_flagOUT") is not None:
            extra_cols.append("mirror_flagOUT")
            extra_vals.append(int(fields["mirror_flagOUT"]))
        return [_build_rule_insert(fields, extra_cols, extra_vals)]


class FastRoutingWizard(BaseWizard):
    """W22: Configure O(1) fast routing (mysql_query_rules_fast_routing)."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        action = fields.get("action", "add")
        if action not in ("add", "delete", "list"):
            errors.append("action must be add, delete, or list")
        if action == "add":
            if not fields.get("username"):
                errors.append("username is required")
            if fields.get("destination_hostgroup") is None:
                errors.append("destination_hostgroup is required")
        if action == "delete":
            if not fields.get("username"):
                errors.append("username is required to identify the rule")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        action = fields.get("action", "add")
        if action == "list":
            return ["SELECT username, schemaname, flagIN, destination_hostgroup, comment FROM mysql_query_rules_fast_routing"]
        if action == "delete":
            where = f"username = {_quote_val(fields['username'])}"
            if fields.get("schemaname"):
                where += f" AND schemaname = {_quote_val(fields['schemaname'])}"
            if fields.get("flagIN") is not None:
                where += f" AND flagIN = {int(fields['flagIN'])}"
            return [f"DELETE FROM mysql_query_rules_fast_routing WHERE {where}"]
        # add
        cols = ["username", "schemaname", "flagIN", "destination_hostgroup"]
        vals = [
            fields["username"],
            fields.get("schemaname", ""),
            int(fields.get("flagIN", 0)),
            int(fields["destination_hostgroup"]),
        ]
        if fields.get("comment"):
            cols.append("comment")
            vals.append(fields["comment"])
        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO mysql_query_rules_fast_routing ({cols_str}) VALUES ({vals_str})"]


class QueryLoggingRuleWizard(BaseWizard):
    """W23: Enable logging for specific queries (log=1)."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if fields.get("rule_id") is None:
            errors.append("rule_id is required")
        if not fields.get("match_digest") and not fields.get("match_pattern"):
            errors.append("Either match_digest or match_pattern is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        extra_cols = ["log"]
        extra_vals = [1]
        return [_build_rule_insert(fields, extra_cols, extra_vals)]


# ── Wizard Definitions ──────────────────────────────────────────

DEFINITIONS = {
    "W18": (WizardDefinition(
        id="W18", category="query_routing", name="Query Cache Rule",
        description="Configure cache_ttl/cache_empty_result/cache_timeout for a query",
        icon="database", target_table="mysql_query_rules", auto_apply_module="MYSQL QUERY RULES",
        fields=[
            WizardField("rule_id", "Rule ID", "number", required=True),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("match_digest", "Match Digest (regex)", "text", placeholder="^SELECT"),
            WizardField("match_pattern", "Match Pattern (regex)", "text"),
            WizardField("_lookup_username", "Pick User (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_users",
                            "label_template": "{username} | hg={default_hostgroup}",
                            "linked_fields": {"username": "username"},
                        }),
            WizardField("username", "Username (optional)", "text"),
            WizardField("schemaname", "Schema (optional)", "text"),
            WizardField("cache_ttl", "Cache TTL (ms)", "number", default=5000),
            WizardField("cache_empty_result", "Cache Empty Result", "toggle", default=0),
            WizardField("cache_timeout", "Cache Timeout (ms)", "number", default=1000),
            WizardField("apply", "Apply (stop matching)", "toggle", default=1),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), QueryCacheRuleWizard),

    "W19": (WizardDefinition(
        id="W19", category="query_routing", name="Query Rewrite Rule",
        description="Set match_pattern + replace_pattern for SQL rewriting",
        icon="edit", target_table="mysql_query_rules", auto_apply_module="MYSQL QUERY RULES",
        fields=[
            WizardField("rule_id", "Rule ID", "number", required=True),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("match_pattern", "Match Pattern (regex)", "text", required=True),
            WizardField("replace_pattern", "Replace Pattern", "text", required=True),
            WizardField("_lookup_username", "Pick User (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_users",
                            "label_template": "{username} | hg={default_hostgroup}",
                            "linked_fields": {"username": "username"},
                        }),
            WizardField("username", "Username (optional)", "text"),
            WizardField("schemaname", "Schema (optional)", "text"),
            WizardField("_lookup_hg", "Pick Hostgroup (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_servers",
                            "label_template": "hg={hostgroup_id} | {hostname}:{port}",
                            "linked_fields": {"destination_hostgroup": "hostgroup_id"},
                        }),
            WizardField("destination_hostgroup", "Destination Hostgroup (optional)", "number"),
            WizardField("apply", "Apply (stop matching)", "toggle", default=1),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), QueryRewriteRuleWizard),

    "W20": (WizardDefinition(
        id="W20", category="query_routing", name="Query Timeout/Rate-Limit Rule",
        description="Configure timeout, delay and retries for a query",
        icon="clock", target_table="mysql_query_rules", auto_apply_module="MYSQL QUERY RULES",
        fields=[
            WizardField("rule_id", "Rule ID", "number", required=True),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("match_digest", "Match Digest (regex)", "text"),
            WizardField("match_pattern", "Match Pattern (regex)", "text"),
            WizardField("timeout", "Timeout (ms, 0=disabled)", "number", default=0),
            WizardField("delay", "Delay (ms, 0=none)", "number", default=0),
            WizardField("retries", "Retries (0=none)", "number", default=0),
            WizardField("_lookup_hg", "Pick Hostgroup (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_servers",
                            "label_template": "hg={hostgroup_id} | {hostname}:{port}",
                            "linked_fields": {"destination_hostgroup": "hostgroup_id"},
                        }),
            WizardField("destination_hostgroup", "Destination Hostgroup (optional)", "number"),
            WizardField("apply", "Apply (stop matching)", "toggle", default=1),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), QueryTimeoutRuleWizard),

    "W21": (WizardDefinition(
        id="W21", category="query_routing", name="Query Mirror Rule",
        description="Mirror traffic to a test hostgroup (mirror_hostgroup)",
        icon="copy", target_table="mysql_query_rules", auto_apply_module="MYSQL QUERY RULES",
        fields=[
            WizardField("rule_id", "Rule ID", "number", required=True),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("match_digest", "Match Digest (regex)", "text"),
            WizardField("match_pattern", "Match Pattern (regex)", "text"),
            WizardField("_lookup_hg", "Pick Mirror Hostgroup (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_servers",
                            "label_template": "hg={hostgroup_id} | {hostname}:{port}",
                            "linked_fields": {"mirror_hostgroup": "hostgroup_id"},
                        }),
            WizardField("mirror_hostgroup", "Mirror Hostgroup", "number", required=True),
            WizardField("mirror_flagOUT", "Mirror Flag OUT (optional)", "number"),
            WizardField("apply", "Apply (stop matching)", "toggle", default=0),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), QueryMirrorRuleWizard),

    "W22": (WizardDefinition(
        id="W22", category="query_routing", name="Fast Routing Table",
        description="Configure O(1) fast routing (mysql_query_rules_fast_routing)",
        icon="zap", target_table="mysql_query_rules_fast_routing", auto_apply_module="MYSQL QUERY RULES",
        fields=[
            WizardField("action", "Action", "select", required=True, default="add",
                        options=[{"value": "add", "label": "Add"},
                                 {"value": "delete", "label": "Delete"},
                                 {"value": "list", "label": "List"}]),
            WizardField("_lookup_username", "Pick User (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_users",
                            "label_template": "{username} | hg={default_hostgroup}",
                            "linked_fields": {"username": "username"},
                        }),
            WizardField("username", "Username", "text", required=True),
            WizardField("schemaname", "Schema", "text"),
            WizardField("flagIN", "Flag IN", "number", default=0),
            WizardField("_lookup_hg", "Pick Hostgroup (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_servers",
                            "label_template": "hg={hostgroup_id} | {hostname}:{port}",
                            "linked_fields": {"destination_hostgroup": "hostgroup_id"},
                        }),
            WizardField("destination_hostgroup", "Destination Hostgroup", "number", required=True),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), FastRoutingWizard),

    "W23": (WizardDefinition(
        id="W23", category="query_routing", name="Query Logging Rule",
        description="Enable logging for specific queries (log=1)",
        icon="file-text", target_table="mysql_query_rules", auto_apply_module="MYSQL QUERY RULES",
        fields=[
            WizardField("rule_id", "Rule ID", "number", required=True),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("match_digest", "Match Digest (regex)", "text"),
            WizardField("match_pattern", "Match Pattern (regex)", "text"),
            WizardField("_lookup_username", "Pick User (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_users",
                            "label_template": "{username} | hg={default_hostgroup}",
                            "linked_fields": {"username": "username"},
                        }),
            WizardField("username", "Username (optional)", "text"),
            WizardField("schemaname", "Schema (optional)", "text"),
            WizardField("_lookup_hg", "Pick Hostgroup (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_servers",
                            "label_template": "hg={hostgroup_id} | {hostname}:{port}",
                            "linked_fields": {"destination_hostgroup": "hostgroup_id"},
                        }),
            WizardField("destination_hostgroup", "Destination Hostgroup (optional)", "number"),
            WizardField("apply", "Apply (stop matching)", "toggle", default=1),
            WizardField("comment", "Comment", "text"),
        ], status="implemented",
    ), QueryLoggingRuleWizard),

    "W69": (WizardDefinition(
        id="W69", category="query_routing", name="Delete Query Routing Rule",
        description="Remove a query routing rule from mysql_query_rules by rule_id",
        icon="trash", target_table="mysql_query_rules", auto_apply_module="MYSQL QUERY RULES",
        guide=(
            "⚠ DANGER: This permanently removes the query rule from ProxySQL.\n"
            "The rule identified by rule_id will be deleted from mysql_query_rules.\n\n"
            "Before deleting:\n"
            "1. Use W55 (Query Rule Hit Statistics) to confirm the rule is unused\n"
            "2. Verify no traffic depends on this rule for routing\n"
            "3. Deleting a rule that was handling critical traffic (e.g. read-write\n"
            "   split) may cause queries to be routed incorrectly"
        ),
        fields=[
            WizardField("_lookup", "Select Rule to Delete (auto-fill)", "lookup",
                        lookup={
                            "table": "mysql_query_rules",
                            "label_template": "rule_id={rule_id} | {match_digest} | hg={destination_hostgroup}",
                            "linked_fields": {
                                "rule_id": "rule_id",
                            },
                        }),
            WizardField("rule_id", "Rule ID", "number", required=True),
            WizardField("confirm_delete", "I confirm I want to DELETE this rule",
                        "checkbox", required=True, default=False),
        ], status="implemented",
    ), DeleteQueryRuleWizard),
}

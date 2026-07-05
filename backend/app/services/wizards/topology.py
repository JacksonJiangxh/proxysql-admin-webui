"""W25-W28, W70: Replication & cluster topology configuration wizards."""
from app.services.wizard_engine import BaseWizard, WizardDefinition, WizardField, _quote_val


class DeleteReplicationHostgroupsWizard(BaseWizard):
    """W70: Delete a replication/cluster hostgroup configuration.

    Supports all replication hostgroup tables:
    - mysql_replication_hostgroups (by writer_hostgroup + reader_hostgroup)
    - mysql_group_replication_hostgroups (by writer_hostgroup)
    - mysql_galera_hostgroups (by writer_hostgroup)
    - mysql_aws_aurora_hostgroups (by writer_hostgroup)
    - pgsql_replication_hostgroups (by writer_hostgroup + reader_hostgroup)
    """

    _VALID_TABLES = {
        "mysql_replication_hostgroups",
        "mysql_group_replication_hostgroups",
        "mysql_galera_hostgroups",
        "mysql_aws_aurora_hostgroups",
        "pgsql_replication_hostgroups",
    }

    def validate(self, fields: dict) -> list[str]:
        errors = []
        target = fields.get("target_table")
        if target not in self._VALID_TABLES:
            errors.append(f"target_table must be one of: {', '.join(sorted(self._VALID_TABLES))}")
        if fields.get("writer_hostgroup") is None:
            errors.append("writer_hostgroup is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        target = fields["target_table"]
        writer = int(fields["writer_hostgroup"])
        reader = fields.get("reader_hostgroup")

        where = f"writer_hostgroup = {writer}"
        if reader is not None and target in ("mysql_replication_hostgroups", "pgsql_replication_hostgroups"):
            where += f" AND reader_hostgroup = {int(reader)}"

        return [f"DELETE FROM {target} WHERE {where}"]


class GroupReplicationWizard(BaseWizard):
    """W25: Configure MySQL Group Replication hostgroups."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        writer = int(fields.get("writer_hostgroup", -1))
        reader = int(fields.get("reader_hostgroup", -1))
        offline = int(fields.get("offline_hostgroup", -1))
        if writer < 0:
            errors.append("writer_hostgroup is required")
        if reader < 0:
            errors.append("reader_hostgroup is required")
        if offline < 0:
            errors.append("offline_hostgroup is required")
        if len({writer, reader, offline}) < 3:
            errors.append("writer, reader, and offline hostgroups must all be different")
        max_writers = int(fields.get("max_writers", 1))
        if max_writers < 1:
            errors.append("max_writers must be >= 1")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        cols = ["writer_hostgroup", "backup_writer_hostgroup", "reader_hostgroup",
                "offline_hostgroup", "active", "max_writers", "writer_is_also_reader",
                "max_transactions_behind", "comment"]
        vals = [
            int(fields["writer_hostgroup"]),
            int(fields.get("backup_writer_hostgroup", -1)),
            int(fields["reader_hostgroup"]),
            int(fields["offline_hostgroup"]),
            int(fields.get("active", 1)),
            int(fields.get("max_writers", 1)),
            int(fields.get("writer_is_also_reader", 2)),
            int(fields.get("max_transactions_behind", 100)),
            fields.get("comment", ""),
        ]
        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO mysql_group_replication_hostgroups ({cols_str}) VALUES ({vals_str})"]


class GaleraClusterWizard(BaseWizard):
    """W26: Configure Galera Cluster hostgroups."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        writer = int(fields.get("writer_hostgroup", -1))
        reader = int(fields.get("reader_hostgroup", -1))
        offline = int(fields.get("offline_hostgroup", -1))
        if writer < 0:
            errors.append("writer_hostgroup is required")
        if reader < 0:
            errors.append("reader_hostgroup is required")
        if offline < 0:
            errors.append("offline_hostgroup is required")
        if len({writer, reader, offline}) < 3:
            errors.append("writer, reader, and offline hostgroups must all be different")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        cols = ["writer_hostgroup", "backup_writer_hostgroup", "reader_hostgroup",
                "offline_hostgroup", "active", "max_writers", "writer_is_also_reader",
                "max_transactions_behind", "comment"]
        vals = [
            int(fields["writer_hostgroup"]),
            int(fields.get("backup_writer_hostgroup", -1)),
            int(fields["reader_hostgroup"]),
            int(fields["offline_hostgroup"]),
            int(fields.get("active", 1)),
            int(fields.get("max_writers", 1)),
            int(fields.get("writer_is_also_reader", 2)),
            int(fields.get("max_transactions_behind", 100)),
            fields.get("comment", ""),
        ]
        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO mysql_galera_hostgroups ({cols_str}) VALUES ({vals_str})"]


class AwsAuroraWizard(BaseWizard):
    """W27: Configure AWS Aurora cluster hostgroups."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        if int(fields.get("writer_hostgroup", -1)) < 0:
            errors.append("writer_hostgroup is required")
        if int(fields.get("reader_hostgroup", -1)) < 0:
            errors.append("reader_hostgroup is required")
        if not fields.get("domain_name"):
            errors.append("domain_name is required (Aurora cluster endpoint)")
        if fields.get("writer_hostgroup") == fields.get("reader_hostgroup"):
            errors.append("writer and reader hostgroups must be different")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        cols = ["writer_hostgroup", "reader_hostgroup", "active", "domain_name",
                "aurora_port", "max_lag_ms", "check_interval_ms", "check_timeout_ms",
                "new_reader_weight", "autopurge_missing_checks", "add_lag_ms",
                "min_lag_ms", "lag_num_checks", "comment"]
        vals = [
            int(fields["writer_hostgroup"]),
            int(fields["reader_hostgroup"]),
            int(fields.get("active", 1)),
            fields["domain_name"],
            int(fields.get("aurora_port", 3306)),
            int(fields.get("max_lag_ms", 600000)),
            int(fields.get("check_interval_ms", 1000)),
            int(fields.get("check_timeout_ms", 800)),
            int(fields.get("new_reader_weight", 1000)),
            int(fields.get("autopurge_missing_checks", 3)),
            int(fields.get("add_lag_ms", 300000)),
            int(fields.get("min_lag_ms", 0)),
            int(fields.get("lag_num_checks", 3)),
            fields.get("comment", ""),
        ]
        cols_str = ", ".join(cols)
        vals_str = ", ".join(_quote_val(v) for v in vals)
        return [f"INSERT INTO mysql_aws_aurora_hostgroups ({cols_str}) VALUES ({vals_str})"]


class PgsqlReplicationWizard(BaseWizard):
    """W28: Configure PostgreSQL primary/replica replication hostgroups."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        writer = int(fields.get("writer_hostgroup", -1))
        reader = int(fields.get("reader_hostgroup", -1))
        if writer < 0:
            errors.append("writer_hostgroup is required")
        if reader < 0:
            errors.append("reader_hostgroup is required")
        if writer == reader:
            errors.append("writer and reader hostgroups must be different")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        return [
            f"INSERT INTO pgsql_replication_hostgroups "
            f"(writer_hostgroup, reader_hostgroup, check_type, comment) "
            f"VALUES ({int(fields['writer_hostgroup'])}, {int(fields['reader_hostgroup'])}, "
            f"{_quote_val(fields.get('check_type', 'read_only'))}, "
            f"{_quote_val(fields.get('comment', 'pgsql-replication'))})"
        ]


# ── Wizard Definitions ──────────────────────────────────────────

DEFINITIONS = {
    "W25": (WizardDefinition(
        id="W25", category="replication_topology", name="Configure Group Replication",
        description="Configure mysql_group_replication_hostgroups",
        icon="git-branch", target_table="mysql_group_replication_hostgroups",
        auto_apply_module="MYSQL SERVERS",
        fields=[
            WizardField("writer_hostgroup", "Writer Hostgroup", "number", required=True),
            WizardField("backup_writer_hostgroup", "Backup Writer Hostgroup", "number"),
            WizardField("reader_hostgroup", "Reader Hostgroup", "number", required=True),
            WizardField("offline_hostgroup", "Offline Hostgroup", "number", required=True),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("max_writers", "Max Writers", "number", default=1),
            WizardField("writer_is_also_reader", "Writer Is Also Reader", "select", default=2,
                        options=[{"value": 0, "label": "0 (No)"},
                                 {"value": 1, "label": "1 (Yes)"},
                                 {"value": 2, "label": "2 (Yes, after demotion)"}]),
            WizardField("max_transactions_behind", "Max Transactions Behind", "number", default=100),
            WizardField("comment", "Comment", "text", default="group-replication"),
        ], status="implemented",
    ), GroupReplicationWizard),

    "W26": (WizardDefinition(
        id="W26", category="replication_topology", name="Configure Galera Cluster",
        description="Configure mysql_galera_hostgroups",
        icon="git-branch", target_table="mysql_galera_hostgroups",
        auto_apply_module="MYSQL SERVERS",
        fields=[
            WizardField("writer_hostgroup", "Writer Hostgroup", "number", required=True),
            WizardField("backup_writer_hostgroup", "Backup Writer Hostgroup", "number"),
            WizardField("reader_hostgroup", "Reader Hostgroup", "number", required=True),
            WizardField("offline_hostgroup", "Offline Hostgroup", "number", required=True),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("max_writers", "Max Writers", "number", default=1),
            WizardField("writer_is_also_reader", "Writer Is Also Reader", "select", default=2,
                        options=[{"value": 0, "label": "0 (No)"},
                                 {"value": 1, "label": "1 (Yes)"},
                                 {"value": 2, "label": "2 (Yes, after demotion)"}]),
            WizardField("max_transactions_behind", "Max Transactions Behind", "number", default=100),
            WizardField("comment", "Comment", "text", default="galera-cluster"),
        ], status="implemented",
    ), GaleraClusterWizard),

    "W27": (WizardDefinition(
        id="W27", category="replication_topology", name="Configure AWS Aurora Cluster",
        description="Configure mysql_aws_aurora_hostgroups",
        icon="cloud", target_table="mysql_aws_aurora_hostgroups",
        auto_apply_module="MYSQL SERVERS",
        fields=[
            WizardField("writer_hostgroup", "Writer Hostgroup", "number", required=True),
            WizardField("reader_hostgroup", "Reader Hostgroup", "number", required=True),
            WizardField("active", "Active", "toggle", default=1),
            WizardField("domain_name", "Aurora Cluster Domain", "text", required=True,
                        placeholder="my-cluster.cluster-xxx.region.rds.amazonaws.com"),
            WizardField("aurora_port", "Aurora Port", "number", default=3306),
            WizardField("max_lag_ms", "Max Lag (ms)", "number", default=600000),
            WizardField("check_interval_ms", "Check Interval (ms)", "number", default=1000),
            WizardField("check_timeout_ms", "Check Timeout (ms)", "number", default=800),
            WizardField("new_reader_weight", "New Reader Weight", "number", default=1000),
            WizardField("comment", "Comment", "text", default="aws-aurora"),
        ], status="implemented",
    ), AwsAuroraWizard),

    "W28": (WizardDefinition(
        id="W28", category="replication_topology", name="Configure PostgreSQL Replication",
        description="Configure pgsql_replication_hostgroups",
        icon="git-branch", target_table="pgsql_replication_hostgroups",
        auto_apply_module="PGSQL SERVERS",
        fields=[
            WizardField("writer_hostgroup", "Writer Hostgroup", "number", required=True),
            WizardField("reader_hostgroup", "Reader Hostgroup", "number", required=True),
            WizardField("check_type", "Check Type", "select", default="read_only",
                        options=[{"value": "read_only", "label": "read_only"}]),
            WizardField("comment", "Comment", "text", default="pgsql-replication"),
        ], status="implemented",
    ), PgsqlReplicationWizard),

    "W70": (WizardDefinition(
        id="W70", category="replication_topology", name="Delete Replication Cluster Config",
        description="Remove a replication/cluster hostgroup configuration from ProxySQL",
        icon="trash", target_table="mysql_replication_hostgroups", auto_apply_module="MYSQL SERVERS",
        guide=(
            "⚠ DANGER: This permanently removes the replication cluster\n"
            "configuration from ProxySQL.\n\n"
            "Select the target table type and identify the config by its\n"
            "writer_hostgroup (and reader_hostgroup for some types).\n\n"
            "After deletion:\n"
            "  • Auto-read_only detection will stop for these hostgroups\n"
            "  • Servers will remain in their current hostgroups\n"
            "  • Read-write split rules may need to be updated separately (W69)\n\n"
            "Before deleting, ensure no application traffic depends on\n"
            "the automatic failover this configuration provides."
        ),
        fields=[
            WizardField("target_table", "Replication Table", "select", required=True,
                        options=[
                            {"value": "mysql_replication_hostgroups", "label": "MySQL Replication"},
                            {"value": "mysql_group_replication_hostgroups", "label": "Group Replication"},
                            {"value": "mysql_galera_hostgroups", "label": "Galera Cluster"},
                            {"value": "mysql_aws_aurora_hostgroups", "label": "AWS Aurora"},
                            {"value": "pgsql_replication_hostgroups", "label": "PostgreSQL Replication"},
                        ]),
            WizardField("writer_hostgroup", "Writer Hostgroup", "number", required=True),
            WizardField("reader_hostgroup", "Reader Hostgroup (for replication types)", "number"),
            WizardField("confirm_delete", "I confirm I want to DELETE this cluster configuration",
                        "checkbox", required=True, default=False),
        ], status="implemented",
    ), DeleteReplicationHostgroupsWizard),
}

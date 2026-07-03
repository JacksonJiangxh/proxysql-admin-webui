"""W53-W64: Monitoring & diagnostics wizards.

W53-W63: Read-only query-based monitoring wizards that query ProxySQL
stats tables and return data for the frontend to render as tables,
charts, or topology diagrams.

W64: Monitor check mode switcher — one-click switching of ProxySQL's
backend MySQL health-check strategy with built-in templates for
different architectures (standard, replication, MGR, Galera, etc.).
"""
from app.services.wizard_engine import BaseWizard, WizardDefinition, WizardField, _quote_val
from app.services.wizards.query_base import QueryWizard


class SlowQueryAnalysisWizard(QueryWizard):
    """W53: Slow / high-frequency query analysis from stats_mysql_query_digest."""

    def validate(self, fields: dict) -> list[str]:
        errors = []
        sort_by = fields.get("sort_by", "sum_time")
        if sort_by not in ("sum_time", "count_star", "avg_time", "sum_rows_affected"):
            errors.append("sort_by must be sum_time, count_star, avg_time, or sum_rows_affected")
        limit = int(fields.get("limit", 20))
        if not (1 <= limit <= 500):
            errors.append("limit must be between 1 and 500")
        return errors

    def generate_queries(self, fields: dict) -> dict[str, str]:
        sort_by = fields.get("sort_by", "sum_time")
        limit = int(fields.get("limit", 20))
        hostgroup = fields.get("hostgroup")
        schemaname = fields.get("schemaname")
        username = fields.get("username")

        where_clauses = []
        if hostgroup not in (None, "", "all"):
            where_clauses.append(f"hostgroup = {int(hostgroup)}")
        if schemaname not in (None, "", "all"):
            where_clauses.append(f"schemaname = '{str(schemaname).replace(chr(39), chr(39)*2)}'")
        if username not in (None, "", "all"):
            where_clauses.append(f"username = '{str(username).replace(chr(39), chr(39)*2)}'")
        where = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        queries = {
            "top_queries": (
                f"SELECT hostgroup, schemaname, username, digest, digest_text, "
                f"count_star, sum_time, min_time, max_time, avg_time, "
                f"sum_rows_affected, sum_rows_sent, first_seen, last_seen "
                f"FROM stats_mysql_query_digest{where} "
                f"ORDER BY {sort_by} DESC LIMIT {limit}"
            ),
            "by_schema": (
                f"SELECT schemaname, SUM(sum_time) as total_time, "
                f"SUM(count_star) as total_count, COUNT(*) as query_count "
                f"FROM stats_mysql_query_digest{where} "
                f"GROUP BY schemaname ORDER BY total_time DESC"
            ),
            "by_command": (
                "SELECT Command, Total_Time_us, Total_cnt "
                "FROM stats_mysql_commands_counters ORDER BY Total_Time_us DESC"
            ),
        }
        return queries


class QueryCommandStatsWizard(QueryWizard):
    """W54: Per-command statistics from stats_mysql_commands_counters."""

    def validate(self, fields: dict) -> list[str]:
        return []

    def generate_queries(self, fields: dict) -> dict[str, str]:
        sort_by = fields.get("sort_by", "Total_Time_us")
        return {
            "commands": (
                f"SELECT Command, Total_Time_us, Total_cnt, "
                f"cnt_100us, cnt_500us, cnt_1ms, cnt_5ms, cnt_10ms, "
                f"cnt_50ms, cnt_100ms, cnt_500ms, cnt_1s, cnt_5s, cnt_10s "
                f"FROM stats_mysql_commands_counters ORDER BY {sort_by} DESC"
            ),
        }


class QueryRuleHitsWizard(QueryWizard):
    """W55: Query rule hit statistics from stats_mysql_query_rules."""

    def validate(self, fields: dict) -> list[str]:
        return []

    def generate_queries(self, fields: dict) -> dict[str, str]:
        return {
            "rule_hits": (
                "SELECT r.rule_id, r.active, r.match_digest, r.destination_hostgroup, "
                "r.apply, r.comment, s.hits "
                "FROM mysql_query_rules r "
                "LEFT JOIN stats_mysql_query_rules s ON r.rule_id = s.rule_id "
                "ORDER BY s.hits DESC"
            ),
        }


class QueryErrorAnalysisWizard(QueryWizard):
    """W56: Backend error analysis from stats_mysql_errors."""

    def validate(self, fields: dict) -> list[str]:
        return []

    def generate_queries(self, fields: dict) -> dict[str, str]:
        limit = int(fields.get("limit", 50))
        return {
            "errors": (
                f"SELECT hostgroup, hostname, port, username, schemaname, "
                f"errno, count_star, first_seen, last_seen, last_error "
                f"FROM stats_mysql_errors ORDER BY count_star DESC LIMIT {limit}"
            ),
            "by_hostgroup": (
                "SELECT hostgroup, errno, SUM(count_star) as total_errors "
                "FROM stats_mysql_errors GROUP BY hostgroup, errno "
                "ORDER BY total_errors DESC"
            ),
        }


class ConnectionPoolMonitorWizard(QueryWizard):
    """W57: Connection pool monitoring from stats_mysql_connection_pool."""

    def validate(self, fields: dict) -> list[str]:
        return []

    def generate_queries(self, fields: dict) -> dict[str, str]:
        return {
            "connection_pool": (
                "SELECT hostgroup, srv_host, srv_port, status, "
                "ConnUsed, ConnFree, ConnOK, ConnERR, MaxConnUsed, "
                "Queries, Queries_GTID_sync, Bytes_data_sent, Bytes_data_recv, "
                "Latency_us "
                "FROM stats_mysql_connection_pool ORDER BY hostgroup, srv_host"
            ),
            "summary": (
                "SELECT SUM(ConnUsed) as total_used, SUM(ConnFree) as total_free, "
                "SUM(ConnOK) as total_ok, SUM(ConnERR) as total_err, "
                "SUM(Queries) as total_queries "
                "FROM stats_mysql_connection_pool"
            ),
        }


class RealtimeProcessListWizard(QueryWizard):
    """W58: Realtime process list from stats_mysql_processlist."""

    def validate(self, fields: dict) -> list[str]:
        return []

    def generate_queries(self, fields: dict) -> dict[str, str]:
        return {
            "processlist": (
                "SELECT ThreadID, SessionID, user, db, cli_host, cli_port, "
                "hostgroup, srv_host, srv_port, command, time_ms, info "
                "FROM stats_mysql_processlist ORDER BY time_ms DESC"
            ),
        }


class UserConnectionStatsWizard(QueryWizard):
    """W59: Per-user connection statistics from stats_mysql_users."""

    def validate(self, fields: dict) -> list[str]:
        return []

    def generate_queries(self, fields: dict) -> dict[str, str]:
        return {
            "user_stats": (
                "SELECT username, frontend_connections, frontend_max_connections "
                "FROM stats_mysql_users ORDER BY frontend_connections DESC"
            ),
        }


class BackendTopologyWizard(QueryWizard):
    """W60: Backend server topology visualization."""

    def validate(self, fields: dict) -> list[str]:
        return []

    def generate_queries(self, fields: dict) -> dict[str, str]:
        return {
            "servers": (
                "SELECT hostgroup_id, hostname, port, status, weight, "
                "max_connections, max_replication_lag, use_ssl, comment "
                "FROM mysql_servers ORDER BY hostgroup_id, hostname"
            ),
            "replication_hostgroups": (
                "SELECT writer_hostgroup, reader_hostgroup, check_type, comment "
                "FROM mysql_replication_hostgroups"
            ),
            "pool_status": (
                "SELECT hostgroup, srv_host, srv_port, status, ConnUsed, ConnFree, "
                "Latency_us FROM stats_mysql_connection_pool"
            ),
        }


class GlobalStatusWizard(QueryWizard):
    """W61: Global status panel from stats_mysql_global + stats_memory_metrics."""

    def validate(self, fields: dict) -> list[str]:
        return []

    def generate_queries(self, fields: dict) -> dict[str, str]:
        return {
            "global_status": (
                "SELECT Variable_Name, Variable_Value FROM stats_mysql_global "
                "ORDER BY Variable_Name"
            ),
            "memory_metrics": (
                "SELECT Variable_Name, Variable_Value FROM stats_memory_metrics "
                "ORDER BY Variable_Name"
            ),
            "connections": (
                "SELECT SUM(ConnUsed) as used, SUM(ConnFree) as free, "
                "SUM(ConnOK) as ok, SUM(ConnERR) as error "
                "FROM stats_mysql_connection_pool"
            ),
        }


class GtidSyncStatusWizard(QueryWizard):
    """W62: GTID execution status from stats_mysql_gtid_executed."""

    def validate(self, fields: dict) -> list[str]:
        return []

    def generate_queries(self, fields: dict) -> dict[str, str]:
        return {
            "gtid": (
                "SELECT hostname, port, gtid_executed FROM stats_mysql_gtid_executed"
            ),
        }


class ClusterStatusWizard(QueryWizard):
    """W63: ProxySQL cluster status from stats_proxysql_servers_*."""

    def validate(self, fields: dict) -> list[str]:
        return []

    def generate_queries(self, fields: dict) -> dict[str, str]:
        return {
            "cluster_metrics": (
                "SELECT hostname, port, weight, comment, "
                "response_time_ms, last_check_ms, check_type "
                "FROM stats_proxysql_servers_metrics"
            ),
            "cluster_checksums": (
                "SELECT hostname, port, name, version, epoch, checksum "
                "FROM stats_proxysql_servers_checksums"
            ),
            "cluster_status": (
                "SELECT hostname, port, weight, comment, status "
                "FROM stats_proxysql_servers_status"
            ),
        }


# ── W64: Monitor Check Mode Switcher ────────────────────────────
#
# ProxySQL 监控检测模式说明：
# 默认情况下 ProxySQL 的 monitor 模块通过定时 ping/connect 检测
# 后端 MySQL 是否在线。对于 MGR (MySQL Group Replication) 架构，
# 需要特殊的健康检测逻辑来准确识别组内成员的在线状态和角色。
#
# 检测模式模板：
# 1. standard    - 标准 TCP 连接检测（默认），仅判断服务器可达
# 2. replication - 主从复制检测，通过 read_only 判断主从角色
# 3. mgr         - MGR 组复制健康检测，读取 replication_group_members
#                  表来判断节点状态（ONLINE/RECOVERING/OFFLINE/ERROR）
# 4. mgr_enhanced- MGR 增强检测，同时启用 groupreplication_healthcheck
#                  和 replication_lag 检查
# 5. galera      - Galera 集群检测，通过 wsrep 状态判断节点角色
# 6. aurora      - AWS Aurora 检测，通过 aurora 健康检查 API
#
# 核心原理：
# - mysql-monitor_username / mysql-monitor_password: 监控用户凭证
# - mysql-monitor_ping_interval: ping 检测间隔
# - mysql-monitor_connect_interval: 连接检测间隔
# - mysql-monitor_read_only_interval: read_only 检测间隔
# - mysql-monitor_replication_lag_interval: 复制延迟检测间隔
# - mysql-monitor_groupreplication_healthcheck_interval: MGR 健康检测间隔
# - mysql-monitor_groupreplication_healthcheck_timeout: MGR 检测超时
# - mysql-monitor_groupreplication_max_transactions_behind: MGR 最大事务延迟
# - mysql-monitor_galera_healthcheck_*: Galera 集群检测参数


# ── Built-in monitor check mode templates ──────────────────────

MONITOR_CHECK_TEMPLATES = {
    "standard": {
        "label": "Standard TCP Health Check",
        "description": "Basic ping/connect check — determines if the MySQL backend is reachable. "
                       "Status shown as ONLINE (reachable) or SHUNNED (unreachable). "
                       "Suitable for single-node or simple setups without replication awareness.",
        "icon": "activity",
        "variables": {
            "mysql-monitor_ping_interval": "10000",
            "mysql-monitor_connect_interval": "60000",
            "mysql-monitor_read_only_interval": "0",  # disabled
            "mysql-monitor_replication_lag_interval": "0",  # disabled
            "mysql-monitor_groupreplication_healthcheck_interval": "0",  # disabled
            "mysql-monitor_galera_healthcheck_interval": "0",  # disabled
        },
        "notes": [
            "Only ping and connect checks are enabled.",
            "No read_only, replication lag, or group-replication health checks.",
            "mysql_servers.status will be ONLINE (reachable) or SHUNNED (unreachable).",
        ],
    },
    "replication": {
        "label": "Primary/Replica Replication Check",
        "description": "Standard async replication check — uses read_only flag to distinguish "
                       "primary (writer) from replica (reader) nodes. "
                       "Status shows ONLINE (read_only=0, primary) or ONLINE (read_only=1, replica).",
        "icon": "git-branch",
        "variables": {
            "mysql-monitor_ping_interval": "10000",
            "mysql-monitor_connect_interval": "60000",
            "mysql-monitor_read_only_interval": "1500",
            "mysql-monitor_replication_lag_interval": "10000",
            "mysql-monitor_groupreplication_healthcheck_interval": "0",  # disabled
            "mysql-monitor_galera_healthcheck_interval": "0",  # disabled
        },
        "notes": [
            "Requires mysql_replication_hostgroups configuration.",
            "read_only=0 → writer hostgroup, read_only=1 → reader hostgroup.",
            "Replication lag monitoring enabled (10s interval).",
        ],
    },
    "mgr": {
        "label": "MGR Group Replication Health Check",
        "description": "MySQL Group Replication health check — reads "
                       "performance_schema.replication_group_members to accurately detect "
                       "each node's status (ONLINE / RECOVERING / OFFLINE / ERROR) and "
                       "role (PRIMARY / SECONDARY) within the MGR group.",
        "icon": "shield",
        "variables": {
            "mysql-monitor_ping_interval": "10000",
            "mysql-monitor_connect_interval": "60000",
            "mysql-monitor_read_only_interval": "1500",
            "mysql-monitor_replication_lag_interval": "10000",
            "mysql-monitor_groupreplication_healthcheck_interval": "5000",
            "mysql-monitor_groupreplication_healthcheck_timeout": "800",
            "mysql-monitor_groupreplication_max_transactions_behind": "100",
            "mysql-monitor_galera_healthcheck_interval": "0",  # disabled
        },
        "notes": [
            "Requires mysql_group_replication_hostgroups configuration.",
            "Monitor user must have SELECT on performance_schema.replication_group_members.",
            "Node status maps: ONLINE → writer/reader hostgroup, RECOVERING/OFFLINE/ERROR → offline_hostgroup.",
            "MGR health check interval: 5s (recommended for production).",
        ],
    },
    "mgr_enhanced": {
        "label": "MGR Enhanced Health Check (Recommended)",
        "description": "Enhanced MGR health check with stricter timeouts and additional "
                       "replication lag monitoring. Best for production environments "
                       "where quick failover detection is critical.",
        "icon": "shield-off",
        "variables": {
            "mysql-monitor_ping_interval": "5000",
            "mysql-monitor_connect_interval": "30000",
            "mysql-monitor_read_only_interval": "1000",
            "mysql-monitor_replication_lag_interval": "5000",
            "mysql-monitor_groupreplication_healthcheck_interval": "3000",
            "mysql-monitor_groupreplication_healthcheck_timeout": "500",
            "mysql-monitor_groupreplication_max_transactions_behind": "50",
            "mysql-monitor_galera_healthcheck_interval": "0",  # disabled
        },
        "notes": [
            "Faster detection intervals (3s MGR check, 5s ping).",
            "Stricter transaction behind threshold (50 vs 100).",
            "Shorter timeout (500ms) for quicker failover detection.",
            "Recommended for production MGR deployments.",
        ],
    },
    "galera": {
        "label": "Galera Cluster Health Check",
        "description": "Galera/PXC cluster health check — uses wsrep status variables "
                       "to detect node readiness, donor/desync state, and primary status.",
        "icon": "link",
        "variables": {
            "mysql-monitor_ping_interval": "10000",
            "mysql-monitor_connect_interval": "60000",
            "mysql-monitor_read_only_interval": "1500",
            "mysql-monitor_replication_lag_interval": "0",
            "mysql-monitor_groupreplication_healthcheck_interval": "0",  # disabled
            "mysql-monitor_galera_healthcheck_interval": "5000",
            "mysql-monitor_galera_healthcheck_timeout": "800",
            "mysql-monitor_galera_healthcheck_max_transactions_behind": "100",
        },
        "notes": [
            "Requires mysql_galera_hostgroups configuration.",
            "Uses wsrep_local_state and wsrep_desync for node status detection.",
            "Galera health check interval: 5s.",
        ],
    },
    "aurora": {
        "label": "AWS Aurora Health Check",
        "description": "AWS Aurora cluster health check — uses the Aurora DNS-based "
                       "discovery mechanism to detect writer/reader endpoints.",
        "icon": "cloud",
        "variables": {
            "mysql-monitor_ping_interval": "10000",
            "mysql-monitor_connect_interval": "60000",
            "mysql-monitor_read_only_interval": "1500",
            "mysql-monitor_replication_lag_interval": "10000",
            "mysql-monitor_groupreplication_healthcheck_interval": "0",  # disabled
            "mysql-monitor_galera_healthcheck_interval": "0",  # disabled
            "mysql-monitor_aurora_interval": "5000",
        },
        "notes": [
            "Requires mysql_aws_aurora_hostgroups configuration.",
            "Uses Aurora DNS endpoints for automatic topology discovery.",
            "Aurora health check interval: 5s.",
        ],
    },
    "custom": {
        "label": "Custom (Manual Configuration)",
        "description": "Manually configure all monitor check intervals. "
                       "Use this mode to fine-tune parameters for your specific environment.",
        "icon": "settings",
        "variables": {},
        "notes": [
            "All check intervals can be independently configured.",
            "Set an interval to 0 to disable that specific check.",
        ],
    },
}


class MonitorCheckModeWizard(BaseWizard):
    """W64: One-click switch ProxySQL backend health-check strategy.

    Allows users to select from built-in monitor check templates
    (standard, replication, MGR, Galera, Aurora, custom) and instantly
    apply the corresponding ``mysql-monitor_*`` global variable
    configuration.

    Additionally generates the appropriate hostgroup table configuration
    (mysql_replication_hostgroups, mysql_group_replication_hostgroups,
    mysql_galera_hostgroups, or mysql_aws_aurora_hostgroups) when
    switching to topology-aware modes.
    """

    def validate(self, fields: dict) -> list[str]:
        errors = []
        mode = fields.get("mode", "")
        if mode not in MONITOR_CHECK_TEMPLATES:
            errors.append(
                f"Invalid mode '{mode}'. Must be one of: "
                f"{', '.join(MONITOR_CHECK_TEMPLATES.keys())}"
            )
        # Monitor credentials are required
        if not fields.get("monitor_username"):
            errors.append("monitor_username is required")
        if not fields.get("monitor_password"):
            errors.append("monitor_password is required")
        # Topology-aware modes require hostgroup configuration
        if mode in ("replication", "mgr", "mgr_enhanced", "galera", "aurora"):
            if mode in ("replication",):
                if fields.get("writer_hostgroup") is None:
                    errors.append("writer_hostgroup is required for replication mode")
                if fields.get("reader_hostgroup") is None:
                    errors.append("reader_hostgroup is required for replication mode")
            if mode in ("mgr", "mgr_enhanced"):
                if fields.get("writer_hostgroup") is None:
                    errors.append("writer_hostgroup is required for MGR mode")
                if fields.get("reader_hostgroup") is None:
                    errors.append("reader_hostgroup is required for MGR mode")
                if fields.get("offline_hostgroup") is None:
                    errors.append("offline_hostgroup is required for MGR mode")
            if mode == "galera":
                if fields.get("writer_hostgroup") is None:
                    errors.append("writer_hostgroup is required for Galera mode")
                if fields.get("reader_hostgroup") is None:
                    errors.append("reader_hostgroup is required for Galera mode")
                if fields.get("offline_hostgroup") is None:
                    errors.append("offline_hostgroup is required for Galera mode")
            if mode == "aurora":
                if fields.get("writer_hostgroup") is None:
                    errors.append("writer_hostgroup is required for Aurora mode")
                if fields.get("reader_hostgroup") is None:
                    errors.append("reader_hostgroup is required for Aurora mode")
        # Custom mode requires explicit variables
        if mode == "custom":
            variables = fields.get("custom_variables")
            if not variables or not isinstance(variables, dict) or len(variables) == 0:
                errors.append("custom_variables must be a non-empty dict for custom mode")
        # Validate intervals
        for interval_key in ("monitor_ping_interval", "monitor_connect_interval",
                             "monitor_read_only_interval", "monitor_replication_lag_interval",
                             "monitor_groupreplication_healthcheck_interval"):
            if fields.get(interval_key) is not None:
                try:
                    v = int(fields[interval_key])
                    if v < 0:
                        errors.append(f"{interval_key} must be >= 0")
                except (ValueError, TypeError):
                    errors.append(f"{interval_key} must be an integer")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        mode = fields.get("mode", "standard")
        sqls: list[str] = []

        # ── 1. Set monitor credentials ──
        monitor_user = _quote_val(fields["monitor_username"])
        monitor_pass = _quote_val(fields["monitor_password"])
        sqls.append(
            f"UPDATE global_variables SET variable_value = {monitor_user} "
            f"WHERE variable_name = 'mysql-monitor_username'"
        )
        sqls.append(
            f"UPDATE global_variables SET variable_value = {monitor_pass} "
            f"WHERE variable_name = 'mysql-monitor_password'"
        )

        # ── 2. Apply template variables ──
        template = MONITOR_CHECK_TEMPLATES.get(mode, {})
        variables: dict[str, str] = {}

        if mode == "custom":
            custom_vars = fields.get("custom_variables", {})
            if isinstance(custom_vars, dict):
                variables = {str(k): str(v) for k, v in custom_vars.items()}
        else:
            variables = dict(template.get("variables", {}))

        # Override template variables with user-provided custom intervals
        user_overrides = {
            "mysql-monitor_ping_interval": "monitor_ping_interval",
            "mysql-monitor_connect_interval": "monitor_connect_interval",
            "mysql-monitor_read_only_interval": "monitor_read_only_interval",
            "mysql-monitor_replication_lag_interval": "monitor_replication_lag_interval",
            "mysql-monitor_groupreplication_healthcheck_interval": "monitor_groupreplication_healthcheck_interval",
            "mysql-monitor_groupreplication_healthcheck_timeout": "monitor_groupreplication_healthcheck_timeout",
            "mysql-monitor_groupreplication_max_transactions_behind": "monitor_groupreplication_max_transactions_behind",
            "mysql-monitor_galera_healthcheck_interval": "monitor_galera_healthcheck_interval",
            "mysql-monitor_galera_healthcheck_timeout": "monitor_galera_healthcheck_timeout",
            "mysql-monitor_galera_healthcheck_max_transactions_behind": "monitor_galera_healthcheck_max_transactions_behind",
        }
        for var_name, field_name in user_overrides.items():
            if fields.get(field_name) is not None:
                variables[var_name] = str(fields[field_name])

        # Write all monitor variables
        for var_name, var_value in variables.items():
            sqls.append(
                f"UPDATE global_variables SET variable_value = {_quote_val(var_value)} "
                f"WHERE variable_name = {_quote_val(var_name)}"
            )

        # ── 3. Generate hostgroup topology configuration ──
        # If user selected a topology-aware mode and provided hostgroups,
        # generate the corresponding hostgroup table INSERT.
        if mode == "replication":
            writer_hg = int(fields.get("writer_hostgroup", 0))
            reader_hg = int(fields.get("reader_hostgroup", 1))
            check_type = _quote_val(fields.get("check_type", "read_only"))
            comment = _quote_val(fields.get("comment", "auto-configured-replication"))
            sqls.append(
                f"INSERT INTO mysql_replication_hostgroups "
                f"(writer_hostgroup, reader_hostgroup, check_type, comment) "
                f"VALUES ({writer_hg}, {reader_hg}, {check_type}, {comment})"
            )

        elif mode in ("mgr", "mgr_enhanced"):
            writer_hg = int(fields.get("writer_hostgroup", 0))
            reader_hg = int(fields.get("reader_hostgroup", 1))
            offline_hg = int(fields.get("offline_hostgroup", 2))
            backup_writer = int(fields.get("backup_writer_hostgroup", 3))
            max_writers = int(fields.get("max_writers", 1))
            writer_is_reader = int(fields.get("writer_is_also_reader", 2))
            max_txn_behind = int(fields.get("max_transactions_behind", 100))
            comment = _quote_val(fields.get("comment", "auto-configured-mgr"))
            cols = ["writer_hostgroup", "backup_writer_hostgroup", "reader_hostgroup",
                    "offline_hostgroup", "active", "max_writers", "writer_is_also_reader",
                    "max_transactions_behind", "comment"]
            vals = [writer_hg, backup_writer, reader_hg, offline_hg, 1,
                    max_writers, writer_is_reader, max_txn_behind,
                    fields.get("comment", "auto-configured-mgr")]
            cols_str = ", ".join(cols)
            vals_str = ", ".join(_quote_val(v) for v in vals)
            sqls.append(
                f"INSERT INTO mysql_group_replication_hostgroups ({cols_str}) VALUES ({vals_str})"
            )

        elif mode == "galera":
            writer_hg = int(fields.get("writer_hostgroup", 0))
            reader_hg = int(fields.get("reader_hostgroup", 1))
            offline_hg = int(fields.get("offline_hostgroup", 2))
            backup_writer = int(fields.get("backup_writer_hostgroup", 3))
            max_writers = int(fields.get("max_writers", 1))
            writer_is_reader = int(fields.get("writer_is_also_reader", 2))
            max_txn_behind = int(fields.get("max_transactions_behind", 100))
            comment = _quote_val(fields.get("comment", "auto-configured-galera"))
            cols = ["writer_hostgroup", "backup_writer_hostgroup", "reader_hostgroup",
                    "offline_hostgroup", "active", "max_writers", "writer_is_also_reader",
                    "max_transactions_behind", "comment"]
            vals = [writer_hg, backup_writer, reader_hg, offline_hg, 1,
                    max_writers, writer_is_reader, max_txn_behind,
                    fields.get("comment", "auto-configured-galera")]
            cols_str = ", ".join(cols)
            vals_str = ", ".join(_quote_val(v) for v in vals)
            sqls.append(
                f"INSERT INTO mysql_galera_hostgroups ({cols_str}) VALUES ({vals_str})"
            )

        elif mode == "aurora":
            writer_hg = int(fields.get("writer_hostgroup", 0))
            reader_hg = int(fields.get("reader_hostgroup", 1))
            domain = _quote_val(fields.get("domain_name", ""))
            aurora_port = int(fields.get("aurora_port", 3306))
            comment = _quote_val(fields.get("comment", "auto-configured-aurora"))
            cols = ["writer_hostgroup", "reader_hostgroup", "active", "domain_name",
                    "aurora_port", "comment"]
            vals = [writer_hg, reader_hg, 1, fields.get("domain_name", ""),
                    aurora_port, fields.get("comment", "auto-configured-aurora")]
            cols_str = ", ".join(cols)
            vals_str = ", ".join(_quote_val(v) for v in vals)
            sqls.append(
                f"INSERT INTO mysql_aws_aurora_hostgroups ({cols_str}) VALUES ({vals_str})"
            )

        return sqls


# ── Wizard Definitions ──────────────────────────────────────────

def _def(wizard_id, name, desc, icon, table, fields):
    return WizardDefinition(
        id=wizard_id, category="monitoring", name=name,
        description=desc, icon=icon, target_table=table,
        auto_apply_module=None, fields=fields, status="implemented",
    )


DEFINITIONS = {
    "W53": (_def("W53", "Slow / High-Frequency Query Analysis",
                 "Visualize Top-N slow/high-frequency queries from stats_mysql_query_digest",
                 "bar-chart", "stats_mysql_query_digest",
                 [WizardField("sort_by", "Sort By", "select", default="sum_time",
                              options=[{"value": "sum_time", "label": "Total Time"},
                                       {"value": "count_star", "label": "Execution Count"},
                                       {"value": "avg_time", "label": "Average Time"},
                                       {"value": "sum_rows_affected", "label": "Rows Affected"}]),
                  WizardField("limit", "Top N", "number", default=20, min=1, max=500),
                  WizardField("hostgroup", "Hostgroup (optional)", "number"),
                  WizardField("schemaname", "Schema (optional)", "text"),
                  WizardField("username", "Username (optional)", "text"),
                 ]), SlowQueryAnalysisWizard),

    "W54": (_def("W54", "Query Command Statistics",
                 "View per-command statistics from stats_mysql_commands_counters",
                 "bar-chart", "stats_mysql_commands_counters",
                 [WizardField("sort_by", "Sort By", "select", default="Total_Time_us",
                              options=[{"value": "Total_Time_us", "label": "Total Time"},
                                       {"value": "Total_cnt", "label": "Total Count"}]),
                 ]), QueryCommandStatsWizard),

    "W55": (_def("W55", "Query Rule Hit Statistics",
                 "Show hit counts per rule from stats_mysql_query_rules",
                 "bar-chart", "stats_mysql_query_rules", []), QueryRuleHitsWizard),

    "W56": (_def("W56", "Query Error Analysis",
                 "Analyze backend errors from stats_mysql_errors",
                 "alert-triangle", "stats_mysql_errors",
                 [WizardField("limit", "Limit", "number", default=50, min=1, max=500),
                 ]), QueryErrorAnalysisWizard),

    "W57": (_def("W57", "Connection Pool Monitoring",
                 "Visualize connection pool usage from stats_mysql_connection_pool",
                 "activity", "stats_mysql_connection_pool", []), ConnectionPoolMonitorWizard),

    "W58": (_def("W58", "Realtime Process List",
                 "Show current active sessions from stats_mysql_processlist",
                 "list", "stats_mysql_processlist", []), RealtimeProcessListWizard),

    "W59": (_def("W59", "User Connection Statistics",
                 "Show per-user connection stats from stats_mysql_users",
                 "users", "stats_mysql_users", []), UserConnectionStatsWizard),

    "W60": (_def("W60", "Backend Topology Visualization",
                 "Visualize hostgroup topology and read-write split flow",
                 "share-2", "mysql_servers", []), BackendTopologyWizard),

    "W61": (_def("W61", "Global Status Panel",
                 "Show global status & memory metrics",
                 "gauge", "stats_mysql_global", []), GlobalStatusWizard),

    "W62": (_def("W62", "GTID Sync Status",
                 "View GTID execution status per backend",
                 "git-commit", "stats_mysql_gtid_executed", []), GtidSyncStatusWizard),

    "W63": (_def("W63", "ProxySQL Cluster Status",
                 "View cluster node status & config consistency",
                 "servers", "stats_proxysql_servers_metrics", []), ClusterStatusWizard),

    "W64": (WizardDefinition(
        id="W64", category="monitoring", name="Monitor Check Mode Switcher",
        description="One-click switch ProxySQL backend health-check strategy. "
                    "Choose from built-in templates (standard, replication, MGR, "
                    "Galera, Aurora) or custom manual configuration.",
        icon="eye", target_table="global_variables",
        auto_apply_module="MYSQL VARIABLES",
        guide=(
            "ProxySQL's monitor module periodically checks backend MySQL servers "
            "to determine their health status and roles. Different architectures "
            "require different detection strategies:\n\n"
            "- **Standard**: Simple TCP ping/connect — suitable for single-node setups.\n"
            "- **Replication**: Uses read_only flag to distinguish primary vs replica.\n"
            "- **MGR**: Reads performance_schema.replication_group_members for accurate "
            "MGR node status (ONLINE/RECOVERING/OFFLINE) and role (PRIMARY/SECONDARY).\n"
            "- **MGR Enhanced**: Stricter intervals and timeouts for production MGR.\n"
            "- **Galera**: Uses wsrep status for Galera/PXC cluster health.\n"
            "- **Aurora**: Uses Aurora DNS discovery for writer/reader detection.\n\n"
            "Select a template, provide monitor credentials, and optionally configure "
            "hostgroup mappings for topology-aware modes."
        ),
        related_tables=[
            "mysql_replication_hostgroups", "mysql_group_replication_hostgroups",
            "mysql_galera_hostgroups", "mysql_aws_aurora_hostgroups",
        ],
        fields=[
            # ── Mode selection ──
            WizardField("mode", "Check Mode Template", "select", required=True,
                        default="mgr",
                        options=[
                            {"value": "standard", "label": "Standard TCP Health Check"},
                            {"value": "replication", "label": "Primary/Replica Replication Check"},
                            {"value": "mgr", "label": "MGR Group Replication Health Check"},
                            {"value": "mgr_enhanced", "label": "MGR Enhanced (Production)"},
                            {"value": "galera", "label": "Galera Cluster Health Check"},
                            {"value": "aurora", "label": "AWS Aurora Health Check"},
                            {"value": "custom", "label": "Custom (Manual)"},
                        ],
                        help_text="Select the monitoring strategy that matches your backend architecture"),
            # ── Monitor credentials ──
            WizardField("monitor_username", "Monitor Username", "text", required=True,
                        default="monitor",
                        help_text="MySQL user for health checks (must exist on all backends)"),
            WizardField("monitor_password", "Monitor Password", "password", required=True,
                        default="monitor",
                        help_text="Password for the monitor user"),
            # ── Hostgroup configuration (for topology-aware modes) ──
            WizardField("writer_hostgroup", "Writer Hostgroup", "number", default=0,
                        help_text="Hostgroup ID for write (primary) nodes"),
            WizardField("reader_hostgroup", "Reader Hostgroup", "number", default=1,
                        help_text="Hostgroup ID for read (secondary) nodes"),
            WizardField("offline_hostgroup", "Offline Hostgroup", "number", default=2,
                        help_text="Hostgroup ID for offline/unavailable nodes"),
            WizardField("backup_writer_hostgroup", "Backup Writer Hostgroup", "number", default=3,
                        help_text="Hostgroup ID for backup writer nodes"),
            WizardField("max_writers", "Max Writers", "number", default=1,
                        help_text="Maximum number of writer nodes allowed"),
            WizardField("writer_is_also_reader", "Writer Is Also Reader", "select", default=2,
                        options=[
                            {"value": 0, "label": "0 (No)"},
                            {"value": 1, "label": "1 (Yes)"},
                            {"value": 2, "label": "2 (Yes, after demotion)"},
                        ],
                        help_text="Whether writer nodes also serve read traffic"),
            WizardField("max_transactions_behind", "Max Transactions Behind", "number", default=100,
                        help_text="Maximum allowed transaction lag before marking node as lagging"),
            WizardField("check_type", "Check Type (Replication)", "select", default="read_only",
                        options=[
                            {"value": "read_only", "label": "read_only"},
                            {"value": "innodb_read_only", "label": "innodb_read_only"},
                            {"value": "super_read_only", "label": "super_read_only"},
                            {"value": "read_only|innodb_read_only", "label": "read_only OR innodb_read_only"},
                            {"value": "read_only&innodb_read_only", "label": "read_only AND innodb_read_only"},
                        ],
                        help_text="How to determine if a node is a replica (for replication mode)"),
            # ── Aurora-specific ──
            WizardField("domain_name", "Aurora Cluster Domain", "text",
                        placeholder="my-cluster.cluster-xxx.region.rds.amazonaws.com",
                        help_text="Aurora cluster endpoint domain (for Aurora mode)"),
            WizardField("aurora_port", "Aurora Port", "number", default=3306,
                        help_text="Port for Aurora cluster connections"),
            # ── Custom interval overrides ──
            WizardField("monitor_ping_interval", "Ping Interval (ms)", "number",
                        help_text="Override ping check interval. Set to 0 to disable."),
            WizardField("monitor_connect_interval", "Connect Interval (ms)", "number",
                        help_text="Override connect check interval."),
            WizardField("monitor_read_only_interval", "Read-Only Check Interval (ms)", "number",
                        help_text="Override read_only check interval."),
            WizardField("monitor_replication_lag_interval", "Replication Lag Check Interval (ms)", "number",
                        help_text="Override replication lag check interval."),
            WizardField("monitor_groupreplication_healthcheck_interval", "MGR Health Check Interval (ms)", "number",
                        help_text="Override MGR group-replication health check interval."),
            WizardField("monitor_groupreplication_healthcheck_timeout", "MGR Health Check Timeout (ms)", "number",
                        help_text="Override MGR health check timeout."),
            WizardField("monitor_groupreplication_max_transactions_behind", "MGR Max Transactions Behind", "number",
                        help_text="Override MGR max transactions behind threshold."),
            WizardField("monitor_galera_healthcheck_interval", "Galera Health Check Interval (ms)", "number",
                        help_text="Override Galera health check interval."),
            WizardField("monitor_galera_healthcheck_timeout", "Galera Health Check Timeout (ms)", "number",
                        help_text="Override Galera health check timeout."),
            WizardField("monitor_galera_healthcheck_max_transactions_behind", "Galera Max Transactions Behind", "number",
                        help_text="Override Galera max transactions behind threshold."),
            # ── Custom mode variables ──
            WizardField("custom_variables", "Custom Variables (JSON: {name: value})", "textarea",
                        placeholder='{"mysql-monitor_ping_interval": "10000", "mysql-monitor_connect_interval": "60000"}',
                        help_text="For custom mode only: define all monitor variables as a JSON key-value map"),
            # ── Comment ──
            WizardField("comment", "Comment", "text", default="",
                        help_text="Optional comment for the hostgroup configuration"),
        ], status="implemented",
    ), MonitorCheckModeWizard),
}

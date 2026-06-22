"""W53-W63: Monitoring & diagnostics wizards (read-only query-based).

These wizards query ProxySQL stats tables and return data for the
frontend to render as tables, charts, or topology diagrams.
"""
from app.services.wizard_engine import WizardDefinition, WizardField
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
}

"""Dashboard service for real-time monitoring data aggregation."""
from datetime import datetime, timezone
from typing import Optional

from app.services.proxysql import proxysql_service


class DashboardService:
    """Aggregates real-time monitoring data from ProxySQL stats tables."""

    METRICS_QUERIES = {
        "connections": """
            SELECT
                SUM(ConnUsed) as used,
                SUM(ConnFree) as free,
                SUM(ConnOK) as ok,
                SUM(ConnERR) as error
            FROM stats_mysql_connection_pool
        """,
        "qps": """
            SELECT variable_value as questions
            FROM stats_mysql_global
            WHERE variable_name = 'Questions'
        """,
        "traffic": """
            SELECT
                SUM(Queries) as queries
            FROM stats_mysql_commands_counters
        """,
        "memory": """
            SELECT
                variable_name,
                variable_value
            FROM stats_memory_metrics
            LIMIT 20
        """,
        "hostgroups": """
            SELECT
                hostgroup,
                srv_host,
                srv_port,
                status,
                ConnUsed,
                ConnFree,
                ConnOK,
                ConnERR,
                Queries,
                Latency_us
            FROM stats_mysql_connection_pool
            ORDER BY hostgroup, srv_host
        """,
    }

    async def get_snapshot(
        self, host: str, port: int, user: str, password: str,
        digest_limit: int = 10,
    ) -> dict:
        """Get a current monitoring snapshot."""
        results = {}
        for name, query in self.METRICS_QUERIES.items():
            try:
                rows = await proxysql_service.execute_query(
                    host, port, user, password, query
                )
                results[name] = rows
            except Exception as e:
                results[name] = {"error": str(e)}

        # Also get query digest
        try:
            digest_rows = await proxysql_service.execute_query(
                host, port, user, password,
                """SELECT hostgroup, schemaname, username, digest_text,
                   count_star, sum_time, min_time, max_time, avg_time
                   FROM stats_mysql_query_digest
                   ORDER BY sum_time DESC LIMIT ?""",
                [digest_limit]
            )
            results["query_digest"] = digest_rows
        except Exception as e:
            results["query_digest"] = {"error": str(e)}

        results["timestamp"] = datetime.now(timezone.utc).isoformat()
        return results


dashboard_service = DashboardService()

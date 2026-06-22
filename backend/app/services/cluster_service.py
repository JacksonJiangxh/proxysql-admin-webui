"""ProxySQL native cluster management service.

Manages cluster groups, member discovery via proxysql_servers table,
cross-node configuration sync, and cluster health monitoring.
"""
import json
import asyncio
from typing import Optional
from dataclasses import dataclass

from app.services.proxysql import proxysql_service
from app.services.sync_service import sync_service, SyncAction
from app.utils.security import decrypt_credential
from app.database import get_db


@dataclass
class NodeCredentials:
    """Decrypted credentials for a ProxySQL node."""
    host: str
    port: int
    user: str
    password: str


class ClusterService:
    """Manages ProxySQL native cluster operations."""

    # ProxySQL cluster-related tables
    CLUSTER_TABLES = [
        "proxysql_servers",
        "mysql_servers",
        "mysql_users",
        "mysql_query_rules",
        "mysql_variables",
        "admin_variables",
        "scheduler",
    ]

    async def _get_server_credentials(self, server_id: str) -> NodeCredentials:
        """Fetch and decrypt credentials for a server."""
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT host, port, admin_user, admin_password_encrypted FROM server_configs WHERE id = ?",
                (server_id,),
            )
            row = await cursor.fetchone()
            if not row:
                raise ValueError(f"Server {server_id} not found")
            return NodeCredentials(
                host=row["host"],
                port=row["port"],
                user=row["admin_user"],
                password=decrypt_credential(row["admin_password_encrypted"]),
            )
        finally:
            await db.close()

    async def get_cluster_node_status(
        self, server_id: str, role: str = "slave"
    ) -> dict:
        """Query a single node's status for cluster health monitoring."""
        creds = await self._get_server_credentials(server_id)
        result = {
            "server_id": server_id,
            "host": creds.host,
            "port": creds.port,
            "role": role,
            "online": False,
            "version": None,
            "uptime_seconds": None,
            "checksums_match": None,
            "error": None,
        }
        try:
            # Get version and uptime
            vars_rows = await proxysql_service.execute_query(
                creds.host, creds.port, creds.user, creds.password,
                "SELECT variable_name, variable_value FROM runtime_global_variables "
                "WHERE variable_name IN ('mysql-server_version', 'admin-version')"
            )
            for row in vars_rows:
                if row.get("variable_name") == "admin-version":
                    result["version"] = row.get("variable_value")

            # Uptime
            status_rows = await proxysql_service.execute_query(
                creds.host, creds.port, creds.user, creds.password,
                "SELECT variable_value FROM stats_mysql_global WHERE variable_name = 'Uptime'"
            )
            if status_rows:
                result["uptime_seconds"] = int(status_rows[0].get("variable_value", 0))

            # Check if proxysql_servers has cluster config
            try:
                cluster_rows = await proxysql_service.execute_query(
                    creds.host, creds.port, creds.user, creds.password,
                    "SELECT hostname, port, weight, comment FROM runtime_proxysql_servers"
                )
                result["cluster_members"] = cluster_rows
            except Exception:
                result["cluster_members"] = []

            # Check checksums
            try:
                checksum_rows = await proxysql_service.execute_query(
                    creds.host, creds.port, creds.user, creds.password,
                    "SELECT * FROM stats_proxysql_servers_checksums"
                )
                result["checksums"] = checksum_rows
            except Exception:
                result["checksums"] = []

            result["online"] = True
        except Exception as e:
            result["error"] = str(e)

        return result

    async def get_cluster_status(
        self, cluster_id: str
    ) -> dict:
        """Get full cluster status with all member health."""
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, name, master_server_id, sync_variables FROM cluster_groups WHERE id = ?",
                (cluster_id,),
            )
            cluster_row = await cursor.fetchone()
            if not cluster_row:
                raise ValueError(f"Cluster {cluster_id} not found")

            cursor = await db.execute(
                """SELECT cm.server_id, cm.role, sc.name, sc.host, sc.port
                   FROM cluster_members cm
                   JOIN server_configs sc ON cm.server_id = sc.id
                   WHERE cm.cluster_id = ?""",
                (cluster_id,),
            )
            members = await cursor.fetchall()
        finally:
            await db.close()

        nodes = []
        for m in members:
            status = await self.get_cluster_node_status(m["server_id"], m["role"])
            status["server_name"] = m["name"]
            nodes.append(status)

        # Compute config consistency across nodes
        config_consistency = await self._compute_cluster_consistency(
            [m["server_id"] for m in members]
        )

        return {
            "cluster_id": cluster_row["id"],
            "cluster_name": cluster_row["name"],
            "nodes": nodes,
            "config_consistency": config_consistency,
        }

    async def _compute_cluster_consistency(
        self, server_ids: list[str]
    ) -> dict:
        """Compare key config tables across cluster members for consistency."""
        if len(server_ids) < 2:
            return {"status": "single_node", "message": "Need at least 2 nodes to compare"}

        checksum_maps = {}
        for sid in server_ids:
            try:
                creds = await self._get_server_credentials(sid)
                checksums = await proxysql_service.execute_query(
                    creds.host, creds.port, creds.user, creds.password,
                    "SELECT * FROM stats_proxysql_servers_checksums"
                )
                checksum_maps[sid] = checksums
            except Exception:
                checksum_maps[sid] = []

        # Compare checksums across nodes
        tables_compared = set()
        for checksums in checksum_maps.values():
            for row in checksums:
                tables_compared.add(row.get("name", ""))

        results = {}
        for table in sorted(tables_compared):
            values = {}
            for sid, checksums in checksum_maps.items():
                for row in checksums:
                    if row.get("name") == table:
                        values[sid] = row.get("checksum", "")
                        break
                if sid not in values:
                    values[sid] = None

            unique_checksums = set(v for v in values.values() if v is not None)
            results[table] = {
                "consistent": len(unique_checksums) <= 1,
                "node_count": len(values),
                "unique_checksum_count": len(unique_checksums),
            }

        total_tables = len(results)
        consistent_tables = sum(1 for r in results.values() if r["consistent"])
        all_consistent = total_tables == consistent_tables if total_tables > 0 else True

        return {
            "status": "consistent" if all_consistent else "inconsistent",
            "tables": results,
            "total_tables": total_tables,
            "consistent_tables": consistent_tables,
        }

    async def sync_to_cluster(
        self,
        cluster_id: str,
        source_server_id: str,
        modules: Optional[list[str]] = None,
        auto_apply: bool = True,
        auto_save: bool = False,
        target_servers: Optional[list[str]] = None,
    ) -> dict:
        """Sync configuration from source to target cluster members.

        Strategy: pull config from source, push to each target.
        Uses the sync_service to LOAD/SAVE/APPLY per module.
        """
        db = await get_db()
        try:
            # Get cluster members
            cursor = await db.execute(
                """SELECT cm.server_id, cm.role
                   FROM cluster_members cm
                   WHERE cm.cluster_id = ?""",
                (cluster_id,),
            )
            members = await cursor.fetchall()
        finally:
            await db.close()

        if target_servers:
            target_ids = [m["server_id"] for m in members if m["server_id"] in target_servers]
        else:
            # Default: sync to all slaves
            target_ids = [m["server_id"] for m in members if m["role"] == "slave"]

        if not target_ids:
            return {"status": "no_targets", "message": "No target servers to sync to"}

        source_creds = await self._get_server_credentials(source_server_id)

        if modules is None:
            modules = self.CLUSTER_TABLES

        results = []
        success_count = 0
        failed_count = 0

        for target_id in target_ids:
            target_creds = await self._get_server_credentials(target_id)
            node_result = {"server_id": target_id, "modules": [], "success": True}

            for module in modules:
                module_result = {"module": module, "success": True}
                try:
                    # Step 1: Pull config from source node's RUNTIME
                    source_rows = await proxysql_service.execute_query(
                        source_creds.host, source_creds.port,
                        source_creds.user, source_creds.password,
                        f"SELECT * FROM runtime_{module}"
                    )

                    if not source_rows:
                        module_result["rows"] = 0
                        node_result["modules"].append(module_result)
                        continue

                    # Step 2: Push to target MEMORY
                    # Delete existing rows, then insert
                    await proxysql_service.execute_modify(
                        target_creds.host, target_creds.port,
                        target_creds.user, target_creds.password,
                        f"DELETE FROM {module}"
                    )

                    # Insert rows from source
                    columns = list(source_rows[0].keys())
                    col_placeholders = ", ".join(["?" for _ in columns])
                    col_names = ", ".join(columns)

                    for row in source_rows:
                        values = [row[col] for col in columns]
                        await proxysql_service.execute_modify(
                            target_creds.host, target_creds.port,
                            target_creds.user, target_creds.password,
                            f"INSERT INTO {module} ({col_names}) VALUES ({col_placeholders})",
                            values,
                        )

                    module_result["rows"] = len(source_rows)

                    # Step 3: Apply to RUNTIME if requested
                    if auto_apply:
                        module_name = sync_service.CONFIG_MODULES.get(module, module.upper())
                        await proxysql_service.execute_admin_command(
                            target_creds.host, target_creds.port,
                            target_creds.user, target_creds.password,
                            f"LOAD {module_name} TO RUNTIME"
                        )

                    # Step 4: Save to DISK if requested
                    if auto_save:
                        module_name = sync_service.CONFIG_MODULES.get(module, module.upper())
                        await proxysql_service.execute_admin_command(
                            target_creds.host, target_creds.port,
                            target_creds.user, target_creds.password,
                            f"SAVE {module_name} TO DISK"
                        )

                    success_count += 1
                except Exception as e:
                    module_result["success"] = False
                    module_result["error"] = str(e)
                    node_result["success"] = False
                    failed_count += 1

                node_result["modules"].append(module_result)

            results.append(node_result)

        return {
            "status": "completed",
            "source_server_id": source_server_id,
            "target_count": len(target_ids),
            "modules": modules,
            "auto_apply": auto_apply,
            "auto_save": auto_save,
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results,
        }

    async def configure_cluster_variables(
        self,
        cluster_id: str,
        variables: dict[str, str],
        target_servers: Optional[list[str]] = None,
    ) -> dict:
        """Set cluster-related admin variables on cluster members.

        Example variables:
        - admin-cluster_username
        - admin-cluster_password
        - admin-cluster_check_interval_ms
        - admin-cluster_mysql_servers_diffs_before_sync
        """
        db = await get_db()
        try:
            cursor = await db.execute(
                """SELECT cm.server_id, cm.role
                   FROM cluster_members cm
                   WHERE cm.cluster_id = ?""",
                (cluster_id,),
            )
            members = await cursor.fetchall()
        finally:
            await db.close()

        if target_servers:
            target_ids = [m["server_id"] for m in members if m["server_id"] in target_servers]
        else:
            target_ids = [m["server_id"] for m in members]

        results = []
        for target_id in target_ids:
            creds = await self._get_server_credentials(target_id)
            node_result = {"server_id": target_id, "variables": {}, "success": True}

            for var_name, var_value in variables.items():
                try:
                    await proxysql_service.execute_modify(
                        creds.host, creds.port, creds.user, creds.password,
                        "UPDATE global_variables SET variable_value = ? WHERE variable_name = ?",
                        [var_value, var_name],
                    )
                    # Apply to runtime
                    await proxysql_service.execute_admin_command(
                        creds.host, creds.port, creds.user, creds.password,
                        "LOAD ADMIN VARIABLES TO RUNTIME"
                    )
                    node_result["variables"][var_name] = "ok"
                except Exception as e:
                    node_result["variables"][var_name] = f"error: {e}"
                    node_result["success"] = False

            results.append(node_result)

        # Save the variables to the cluster group config
        db = await get_db()
        try:
            await db.execute(
                "UPDATE cluster_groups SET sync_variables = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(variables), cluster_id),
            )
            await db.commit()
        finally:
            await db.close()

        return {
            "status": "completed",
            "cluster_id": cluster_id,
            "variables": variables,
            "results": results,
        }

    async def discover_cluster_nodes(
        self, server_id: str
    ) -> list[dict]:
        """Discover cluster peers from a ProxySQL node's proxysql_servers table."""
        creds = await self._get_server_credentials(server_id)
        try:
            rows = await proxysql_service.execute_query(
                creds.host, creds.port, creds.user, creds.password,
                "SELECT hostname, port, weight, comment FROM proxysql_servers"
            )
            return rows
        except Exception:
            # proxysql_servers may be in main only, not runtime
            try:
                rows = await proxysql_service.execute_query(
                    creds.host, creds.port, creds.user, creds.password,
                    "SELECT hostname, port, weight, comment FROM main.proxysql_servers"
                )
                return rows
            except Exception:
                return []


# Global singleton
cluster_service = ClusterService()

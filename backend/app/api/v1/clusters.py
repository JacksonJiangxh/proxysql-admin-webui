"""Cluster management API endpoints.

Manages cluster groups, members, cross-node sync, and health monitoring.
"""
import uuid
import json
from fastapi import APIRouter, HTTPException, Depends

from app.database import get_db
from app.models import (
    ClusterGroupCreate, ClusterGroupUpdate, ClusterGroup,
    ClusterMember, ClusterMemberAdd, ClusterSyncRequest,
    ClusterStatusResponse, ClusterNodeStatus,
)
from app.services.cluster_service import cluster_service
from app.middleware import get_current_user

router = APIRouter()


# ── Cluster Group CRUD ──

@router.get("", response_model=list[ClusterGroup])
async def list_clusters(user=Depends(get_current_user)):
    """List all cluster groups with member counts."""
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT cg.*, COUNT(cm.server_id) as member_count
            FROM cluster_groups cg
            LEFT JOIN cluster_members cm ON cg.id = cm.cluster_id
            GROUP BY cg.id
            ORDER BY cg.name
        """)
        rows = await cursor.fetchall()
        return [
            ClusterGroup(
                id=r["id"], name=r["name"], description=r["description"],
                master_server_id=r["master_server_id"],
                sync_variables=r["sync_variables"],
                member_count=r["member_count"],
                created_at=r["created_at"], updated_at=r["updated_at"],
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.post("", response_model=ClusterGroup)
async def create_cluster(data: ClusterGroupCreate, user=Depends(get_current_user)):
    """Create a new cluster group."""
    db = await get_db()
    try:
        # Check name uniqueness
        cursor = await db.execute("SELECT id FROM cluster_groups WHERE name = ?", (data.name,))
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail="Cluster name already exists")

        cluster_id = str(uuid.uuid4())[:8]
        await db.execute(
            """INSERT INTO cluster_groups (id, name, description, master_server_id, sync_variables)
               VALUES (?, ?, ?, ?, ?)""",
            (cluster_id, data.name, data.description, data.master_server_id,
             data.sync_variables or "{}"),
        )
        await db.commit()

        # If master_server_id is specified, auto-add it as master member
        if data.master_server_id:
            await db.execute(
                "INSERT OR IGNORE INTO cluster_members (cluster_id, server_id, role) VALUES (?, ?, ?)",
                (cluster_id, data.master_server_id, "master"),
            )
            await db.commit()

        cursor = await db.execute(
            "SELECT cg.*, 0 as member_count FROM cluster_groups cg WHERE cg.id = ?",
            (cluster_id,),
        )
        row = await cursor.fetchone()
        return ClusterGroup(
            id=row["id"], name=row["name"], description=row["description"],
            master_server_id=row["master_server_id"],
            sync_variables=row["sync_variables"],
            member_count=0,
            created_at=row["created_at"], updated_at=row["updated_at"],
        )
    finally:
        await db.close()


@router.get("/{cluster_id}", response_model=ClusterGroup)
async def get_cluster(cluster_id: str, user=Depends(get_current_user)):
    """Get cluster group details."""
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT cg.*, COUNT(cm.server_id) as member_count
            FROM cluster_groups cg
            LEFT JOIN cluster_members cm ON cg.id = cm.cluster_id
            WHERE cg.id = ?
            GROUP BY cg.id
        """, (cluster_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cluster not found")
        return ClusterGroup(
            id=row["id"], name=row["name"], description=row["description"],
            master_server_id=row["master_server_id"],
            sync_variables=row["sync_variables"],
            member_count=row["member_count"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )
    finally:
        await db.close()


@router.put("/{cluster_id}", response_model=ClusterGroup)
async def update_cluster(cluster_id: str, data: ClusterGroupUpdate, user=Depends(get_current_user)):
    """Update a cluster group."""
    db = await get_db()
    try:
        updates = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.description is not None:
            updates["description"] = data.description
        if data.master_server_id is not None:
            updates["master_server_id"] = data.master_server_id
        if data.sync_variables is not None:
            updates["sync_variables"] = data.sync_variables

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [cluster_id]
            await db.execute(
                f"UPDATE cluster_groups SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values,
            )
            await db.commit()

        cursor = await db.execute("""
            SELECT cg.*, COUNT(cm.server_id) as member_count
            FROM cluster_groups cg
            LEFT JOIN cluster_members cm ON cg.id = cm.cluster_id
            WHERE cg.id = ?
            GROUP BY cg.id
        """, (cluster_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cluster not found")
        return ClusterGroup(
            id=row["id"], name=row["name"], description=row["description"],
            master_server_id=row["master_server_id"],
            sync_variables=row["sync_variables"],
            member_count=row["member_count"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )
    finally:
        await db.close()


@router.delete("/{cluster_id}")
async def delete_cluster(cluster_id: str, user=Depends(get_current_user)):
    """Delete a cluster group (members are cascade-deleted)."""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM cluster_groups WHERE id = ?", (cluster_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Cluster not found")
    finally:
        await db.close()
    return {"ok": True, "message": "Cluster deleted"}


# ── Cluster Members ──

@router.get("/{cluster_id}/members", response_model=list[ClusterMember])
async def list_cluster_members(cluster_id: str, user=Depends(get_current_user)):
    """List all members of a cluster group."""
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT cm.cluster_id, cm.server_id, cm.role,
                   sc.name as server_name, sc.host as server_host, sc.port as server_port
            FROM cluster_members cm
            JOIN server_configs sc ON cm.server_id = sc.id
            WHERE cm.cluster_id = ?
            ORDER BY cm.role DESC, sc.name
        """, (cluster_id,))
        rows = await cursor.fetchall()
        return [
            ClusterMember(
                cluster_id=r["cluster_id"], server_id=r["server_id"], role=r["role"],
                server_name=r["server_name"], server_host=r["server_host"],
                server_port=r["server_port"],
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.post("/{cluster_id}/members")
async def add_cluster_member(cluster_id: str, data: ClusterMemberAdd, user=Depends(get_current_user)):
    """Add a server to a cluster group."""
    db = await get_db()
    try:
        # Validate cluster exists
        cursor = await db.execute("SELECT id FROM cluster_groups WHERE id = ?", (cluster_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Cluster not found")

        # Validate server exists
        cursor = await db.execute("SELECT id FROM server_configs WHERE id = ?", (data.server_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Server not found")

        # Only one master allowed
        if data.role == "master":
            await db.execute(
                "UPDATE cluster_members SET role = 'slave' WHERE cluster_id = ? AND role = 'master'",
                (cluster_id,),
            )

        await db.execute(
            "INSERT OR REPLACE INTO cluster_members (cluster_id, server_id, role) VALUES (?, ?, ?)",
            (cluster_id, data.server_id, data.role),
        )
        await db.commit()
    finally:
        await db.close()
    return {"ok": True, "message": "Member added"}


@router.delete("/{cluster_id}/members/{server_id}")
async def remove_cluster_member(cluster_id: str, server_id: str, user=Depends(get_current_user)):
    """Remove a server from a cluster group."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM cluster_members WHERE cluster_id = ? AND server_id = ?",
            (cluster_id, server_id),
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Member not found")
    finally:
        await db.close()
    return {"ok": True, "message": "Member removed"}


# ── Cluster Operations ──

@router.get("/{cluster_id}/status")
async def get_cluster_status(cluster_id: str, user=Depends(get_current_user)):
    """Get cluster health status for all members."""
    try:
        status = await cluster_service.get_cluster_status(cluster_id)
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cluster status: {str(e)}")


@router.post("/{cluster_id}/sync")
async def sync_cluster_config(cluster_id: str, data: ClusterSyncRequest, user=Depends(get_current_user)):
    """Sync configuration from master to slave nodes in the cluster.

    Pulls config from source (master by default) and pushes to targets.
    """
    db = await get_db()
    try:
        # Determine source: use target_servers if provided, otherwise master
        if data.target_servers and len(data.target_servers) > 0:
            source_id = data.target_servers[0]
        else:
            cursor = await db.execute(
                "SELECT server_id FROM cluster_members WHERE cluster_id = ? AND role = 'master'",
                (cluster_id,),
            )
            master_row = await cursor.fetchone()
            if not master_row:
                raise HTTPException(status_code=400, detail="No master node configured for this cluster")
            source_id = master_row["server_id"]

        # Log the sync operation
        username = user.get("username", "unknown") if isinstance(user, dict) else "unknown"
        await db.execute(
            """INSERT INTO cluster_sync_logs
               (cluster_id, user_id, username, action, source_server_id, target_servers, module)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (cluster_id, user.get("id") if isinstance(user, dict) else None, username, "sync",
             source_id, json.dumps(data.target_servers or []),
             json.dumps(data.modules or [])),
        )
        await db.commit()
    finally:
        await db.close()

    try:
        result = await cluster_service.sync_to_cluster(
            cluster_id=cluster_id,
            source_server_id=source_id,
            modules=data.modules,
            auto_apply=data.auto_apply,
            auto_save=data.auto_save,
            target_servers=data.target_servers,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/{cluster_id}/configure-variables")
async def configure_cluster_variables(
    cluster_id: str,
    variables: dict[str, str],
    user=Depends(get_current_user),
):
    """Set cluster-related admin variables on cluster members."""
    try:
        result = await cluster_service.configure_cluster_variables(cluster_id, variables)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to configure variables: {str(e)}")


@router.get("/{cluster_id}/discover")
async def discover_cluster_peers(cluster_id: str, user=Depends(get_current_user)):
    """Discover cluster peers from the master node's proxysql_servers table."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT server_id FROM cluster_members WHERE cluster_id = ? AND role = 'master'",
            (cluster_id,),
        )
        master_row = await cursor.fetchone()
        if not master_row:
            cursor = await db.execute(
                "SELECT server_id FROM cluster_members WHERE cluster_id = ? LIMIT 1",
                (cluster_id,),
            )
            master_row = await cursor.fetchone()
            if not master_row:
                raise HTTPException(status_code=404, detail="Cluster has no members")
    finally:
        await db.close()

    try:
        peers = await cluster_service.discover_cluster_nodes(master_row["server_id"])
        return {"cluster_id": cluster_id, "peers": peers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.get("/{cluster_id}/sync-logs")
async def get_cluster_sync_logs(cluster_id: str, limit: int = 50, user=Depends(get_current_user)):
    """Get sync operation logs for a cluster."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM cluster_sync_logs
               WHERE cluster_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (cluster_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()

"""Integration tests for the cluster management flow.

Tests: cluster group CRUD, member management, cluster status, sync logs.
All ProxySQL connections are mocked.
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app


# ── Cluster Group CRUD ─────────────────────────────

@pytest.mark.asyncio
async def test_create_cluster(setup_db, test_app, auth_headers, test_server_id):
    """Test creating a new cluster group."""
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "test-cluster",
        "description": "A test cluster group",
        "master_server_id": test_server_id,
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test-cluster"
    assert data["description"] == "A test cluster group"
    assert data["master_server_id"] == test_server_id
    assert "id" in data
    assert data["member_count"] == 0  # master not auto-added without server existing in members table


@pytest.mark.asyncio
async def test_list_clusters_empty(setup_db, test_app, auth_headers):
    """Test listing clusters when none exist."""
    resp = await test_app.get("/api/v1/clusters", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_list_clusters(setup_db, test_app, auth_headers, test_server_id):
    """Test listing clusters after creating one."""
    # Create a cluster
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "my-cluster",
        "description": "Test",
    }, headers=auth_headers)
    assert resp.status_code == 200

    # List
    resp = await test_app.get("/api/v1/clusters", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "my-cluster"
    assert data[0]["member_count"] == 0


@pytest.mark.asyncio
async def test_get_cluster(setup_db, test_app, auth_headers, test_server_id):
    """Test getting a specific cluster."""
    # Create
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "get-cluster",
        "description": "Test get",
    }, headers=auth_headers)
    cluster_id = resp.json()["id"]

    # Get
    resp = await test_app.get(f"/api/v1/clusters/{cluster_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == cluster_id
    assert data["name"] == "get-cluster"


@pytest.mark.asyncio
async def test_get_cluster_not_found(setup_db, test_app, auth_headers):
    """Test getting a non-existent cluster."""
    resp = await test_app.get("/api/v1/clusters/nonexistent", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_cluster(setup_db, test_app, auth_headers, admin_token, refresh_csrf):
    """Test updating a cluster."""
    # Create
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "update-cluster",
    }, headers=auth_headers)
    cluster_id = resp.json()["id"]

    # Refresh CSRF token (rotated after POST)
    auth_headers = await refresh_csrf(test_app, admin_token)

    # Update
    resp = await test_app.put(f"/api/v1/clusters/{cluster_id}", json={
        "name": "updated-cluster",
        "description": "Updated description",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "updated-cluster"
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_delete_cluster(setup_db, test_app, auth_headers, admin_token, refresh_csrf):
    """Test deleting a cluster."""
    # Create
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "delete-cluster",
    }, headers=auth_headers)
    cluster_id = resp.json()["id"]

    # Refresh CSRF token (rotated after POST)
    auth_headers = await refresh_csrf(test_app, admin_token)

    # Delete
    resp = await test_app.delete(f"/api/v1/clusters/{cluster_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify gone
    resp = await test_app.get(f"/api/v1/clusters/{cluster_id}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_duplicate_cluster(setup_db, test_app, auth_headers, admin_token, refresh_csrf):
    """Test creating a cluster with duplicate name returns 409."""
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "dup-cluster",
    }, headers=auth_headers)
    assert resp.status_code == 200

    # Refresh CSRF token (rotated after POST)
    auth_headers = await refresh_csrf(test_app, admin_token)

    resp = await test_app.post("/api/v1/clusters", json={
        "name": "dup-cluster",
    }, headers=auth_headers)
    assert resp.status_code == 409


# ── Member management ──────────────────────────────

@pytest.mark.asyncio
async def test_add_cluster_member(setup_db, test_app, auth_headers, test_server_id, admin_token, refresh_csrf):
    """Test adding a server to a cluster."""
    # Create cluster
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "member-cluster",
    }, headers=auth_headers)
    cluster_id = resp.json()["id"]

    # Refresh CSRF token (rotated after POST)
    auth_headers = await refresh_csrf(test_app, admin_token)

    # Add member
    resp = await test_app.post(f"/api/v1/clusters/{cluster_id}/members", json={
        "server_id": test_server_id,
        "role": "master",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # List members
    resp = await test_app.get(f"/api/v1/clusters/{cluster_id}/members", headers=auth_headers)
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) == 1
    assert members[0]["server_id"] == test_server_id
    assert members[0]["role"] == "master"


@pytest.mark.asyncio
async def test_add_cluster_member_master_promotion(setup_db, test_app, auth_headers, test_server_id, admin_token, refresh_csrf):
    """Test that adding a master demotes existing master."""
    # Create cluster
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "promote-cluster",
    }, headers=auth_headers)
    cluster_id = resp.json()["id"]

    # Refresh CSRF token (rotated after POST)
    auth_headers = await refresh_csrf(test_app, admin_token)

    # Add first master
    resp = await test_app.post(f"/api/v1/clusters/{cluster_id}/members", json={
        "server_id": test_server_id,
        "role": "master",
    }, headers=auth_headers)
    assert resp.status_code == 200

    # Refresh CSRF token
    auth_headers = await refresh_csrf(test_app, admin_token)

    # Create a second server
    resp2 = await test_app.post("/api/v1/servers", json={
        "name": "second-server",
        "host": "127.0.0.1",
        "port": 6033,
        "admin_user": "admin",
        "admin_password": "admin",
    }, headers=auth_headers)
    assert resp2.status_code == 200
    server2_id = resp2.json()["id"]

    # Refresh CSRF token
    auth_headers = await refresh_csrf(test_app, admin_token)

    # Add second master — should demote first to slave
    resp = await test_app.post(f"/api/v1/clusters/{cluster_id}/members", json={
        "server_id": server2_id,
        "role": "master",
    }, headers=auth_headers)
    assert resp.status_code == 200

    # Verify first is now slave
    resp = await test_app.get(f"/api/v1/clusters/{cluster_id}/members", headers=auth_headers)
    members = resp.json()
    roles = {m["server_id"]: m["role"] for m in members}
    assert roles.get(server2_id) == "master"
    assert roles.get(test_server_id) == "slave"


@pytest.mark.asyncio
async def test_remove_cluster_member(setup_db, test_app, auth_headers, test_server_id, admin_token, refresh_csrf):
    """Test removing a member from a cluster."""
    # Create cluster and add member
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "remove-cluster",
    }, headers=auth_headers)
    cluster_id = resp.json()["id"]

    # Refresh CSRF token (rotated after POST)
    auth_headers = await refresh_csrf(test_app, admin_token)

    await test_app.post(f"/api/v1/clusters/{cluster_id}/members", json={
        "server_id": test_server_id,
        "role": "slave",
    }, headers=auth_headers)

    # Refresh CSRF token
    auth_headers = await refresh_csrf(test_app, admin_token)

    # Remove member
    resp = await test_app.delete(
        f"/api/v1/clusters/{cluster_id}/members/{test_server_id}",
        headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify removed
    resp = await test_app.get(f"/api/v1/clusters/{cluster_id}/members", headers=auth_headers)
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_add_member_to_nonexistent_cluster(setup_db, test_app, auth_headers, test_server_id):
    """Test adding member to non-existent cluster returns 404."""
    resp = await test_app.post("/api/v1/clusters/nonexistent/members", json={
        "server_id": test_server_id,
        "role": "slave",
    }, headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_nonexistent_server_to_cluster(setup_db, test_app, auth_headers, admin_token, refresh_csrf):
    """Test adding non-existent server to cluster returns 404."""
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "bad-member-cluster",
    }, headers=auth_headers)
    cluster_id = resp.json()["id"]

    # Refresh CSRF token (rotated after POST)
    auth_headers = await refresh_csrf(test_app, admin_token)

    resp = await test_app.post(f"/api/v1/clusters/{cluster_id}/members", json={
        "server_id": "nonexistent",
        "role": "slave",
    }, headers=auth_headers)
    assert resp.status_code == 404


# ── Cluster RBAC ───────────────────────────────────

@pytest.mark.asyncio
async def test_cluster_crud_requires_admin(setup_db, test_app, operator_token):
    """Test that operator cannot create/update/delete clusters."""
    # Create
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "op-cluster",
    }, headers={"Authorization": f"Bearer {operator_token}"})
    assert resp.status_code == 403

    # Delete
    resp = await test_app.delete("/api/v1/clusters/fake-id", headers={
        "Authorization": f"Bearer {operator_token}"
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cluster_member_management_requires_admin(setup_db, test_app, operator_token, test_server_id):
    """Test that operator cannot manage cluster members."""
    resp = await test_app.post("/api/v1/clusters/fake-id/members", json={
        "server_id": test_server_id, "role": "slave",
    }, headers={"Authorization": f"Bearer {operator_token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cluster_viewer_readonly(setup_db, test_app, viewer_token):
    """Test that viewer can list clusters but not modify."""
    # List - should work
    resp = await test_app.get("/api/v1/clusters", headers={
        "Authorization": f"Bearer {viewer_token}"
    })
    assert resp.status_code == 200

    # Create - should fail
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "viewer-cluster",
    }, headers={"Authorization": f"Bearer {viewer_token}"})
    assert resp.status_code == 403


# ── Sync logs ──────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_logs_empty(setup_db, test_app, auth_headers):
    """Test sync logs returns empty for new cluster."""
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "logs-cluster",
    }, headers=auth_headers)
    cluster_id = resp.json()["id"]

    resp = await test_app.get(f"/api/v1/clusters/{cluster_id}/sync-logs", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_sync_logs_with_limit(setup_db, test_app, auth_headers):
    """Test sync logs respects limit parameter."""
    resp = await test_app.post("/api/v1/clusters", json={
        "name": "limit-cluster",
    }, headers=auth_headers)
    cluster_id = resp.json()["id"]

    resp = await test_app.get(
        f"/api/v1/clusters/{cluster_id}/sync-logs?limit=5",
        headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) <= 5

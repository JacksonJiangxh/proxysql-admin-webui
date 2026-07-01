"""Unit tests for BackupService: create, list, restore, batch operations."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.backup_service import backup_service


@pytest.mark.asyncio
async def test_list_backups_empty():
    """list_backups returns empty list when no backups exist."""
    backups = await backup_service.list_backups("server-1")
    assert backups == []


@pytest.mark.asyncio
async def test_create_and_list_backup():
    """create_backup creates a record; list_backups returns it."""
    mock_rows = [
        {"tables": "mysql_servers"},
        {"tables": "mysql_users"},
    ]
    mock_data = [{"hostgroup_id": 0, "hostname": "10.0.0.1", "port": 3306}]

    with patch("app.services.backup_service.proxysql_service") as mock_ps:
        mock_ps.execute_query = AsyncMock(side_effect=[mock_rows, mock_data, mock_data])

        result = await backup_service.create_backup(
            server_id="server-1",
            user_id=1,
            host="127.0.0.1",
            port=6032,
            user="admin",
            password="admin",
            name="test-backup",
        )

    assert result["server_id"] == "server-1"
    assert result["name"] == "test-backup"
    assert result["table_count"] == 2
    assert result["row_count"] == 2

    # Verify it appears in list
    backups = await backup_service.list_backups("server-1")
    assert len(backups) == 1
    assert backups[0]["name"] == "test-backup"


@pytest.mark.asyncio
async def test_get_backup_not_found():
    """get_backup returns None for non-existent backup."""
    result = await backup_service.get_backup(99999)
    assert result is None


@pytest.mark.asyncio
async def test_delete_backup_not_found():
    """delete_backup returns False for non-existent backup."""
    result = await backup_service.delete_backup(99999)
    assert result is False


@pytest.mark.asyncio
async def test_create_and_delete_backup():
    """Create then delete a backup."""
    mock_rows = [{"tables": "mysql_servers"}]
    mock_data = [{"hostgroup_id": 0}]

    with patch("app.services.backup_service.proxysql_service") as mock_ps:
        mock_ps.execute_query = AsyncMock(side_effect=[mock_rows, mock_data])
        result = await backup_service.create_backup(
            server_id="server-2",
            user_id=1,
            host="127.0.0.1",
            port=6032,
            user="admin",
            password="admin",
        )
    backup_id = result["id"]

    deleted = await backup_service.delete_backup(backup_id)
    assert deleted is True

    # Verify it's gone
    assert await backup_service.get_backup(backup_id) is None


@pytest.mark.asyncio
async def test_download_backup():
    """download_backup returns (filename, json_data) tuple."""
    mock_rows = [{"tables": "mysql_servers"}]
    mock_data = [{"hostgroup_id": 0, "hostname": "10.0.0.1"}]

    with patch("app.services.backup_service.proxysql_service") as mock_ps:
        mock_ps.execute_query = AsyncMock(side_effect=[mock_rows, mock_data])
        result = await backup_service.create_backup(
            server_id="server-3",
            user_id=1,
            host="127.0.0.1",
            port=6032,
            user="admin",
            password="admin",
            name="my backup",
        )

    dl = await backup_service.download_backup(result["id"])
    assert dl is not None
    filename, data = dl
    assert "my_backup" in filename
    assert ".json" in filename
    parsed = json.loads(data)
    assert "mysql_servers" in parsed


@pytest.mark.asyncio
async def test_batch_delete_backups():
    """delete_backups removes multiple backups."""
    mock_rows = [{"tables": "mysql_servers"}]
    mock_data = [{"hostgroup_id": 0}]

    ids = []
    with patch("app.services.backup_service.proxysql_service") as mock_ps:
        for i in range(3):
            mock_ps.execute_query = AsyncMock(side_effect=[mock_rows, mock_data])
            result = await backup_service.create_backup(
                server_id="batch-server",
                user_id=1,
                host="127.0.0.1",
                port=6032,
                user="admin",
                password="admin",
            )
            ids.append(result["id"])

    # Batch delete
    deleted = await backup_service.delete_backups(ids)
    assert deleted == 3

    # Verify all gone
    for bid in ids:
        assert await backup_service.get_backup(bid) is None


@pytest.mark.asyncio
async def test_batch_delete_empty_list():
    """delete_backups with empty list returns 0."""
    assert await backup_service.delete_backups([]) == 0


@pytest.mark.asyncio
async def test_restore_backup_not_found():
    """restore_backup raises ValueError for non-existent backup."""
    with pytest.raises(ValueError, match="not found"):
        await backup_service.restore_backup(
            backup_id=99999,
            host="127.0.0.1",
            port=6032,
            user="admin",
            password="admin",
        )

"""Tests for sync service logic."""
import pytest
from app.services.sync_service import SyncAction


def test_sync_action_enum_values():
    """Test SyncAction enum values."""
    assert SyncAction.APPLY.value == "apply"
    assert SyncAction.SAVE.value == "save"
    assert SyncAction.DISCARD.value == "discard"
    assert SyncAction.LOAD.value == "load"


def test_row_hash_consistency():
    """Test that row_hash produces consistent results."""
    from app.utils.helpers import row_hash

    row1 = {"id": 1, "name": "test", "value": 100}
    row2 = {"id": 1, "name": "test", "value": 100}
    row3 = {"id": 1, "name": "test", "value": 200}

    assert row_hash(row1) == row_hash(row2)
    assert row_hash(row1) != row_hash(row3)


def test_row_hash_order_independent():
    """Test that row_hash is order-independent for keys."""
    from app.utils.helpers import row_hash

    row1 = {"a": 1, "b": 2}
    row2 = {"b": 2, "a": 1}

    assert row_hash(row1) == row_hash(row2)

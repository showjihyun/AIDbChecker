# Spec: FS-SCHEMA-001
"""Tests for FS-SCHEMA-001 Acceptance Criteria (Schema Change Detection).

Covers:
- AC-1: New table CREATE detected via compare_snapshots()
- AC-2: Column ALTER (type/nullable change) detected
- AC-3: Index CREATE/DROP detected
- AC-5: Snapshot caching in Valkey (mocked)

NOTE: AC-4 (GET /instances/{id}/schema-changes works) is fully covered
in test_schema_changes_api.py with real assertions.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services.schema_detector import (
    _set_cached_snapshot,
    _valkey_key,
    compare_snapshots,
)
from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

def _empty_snapshot() -> dict:
    """Return a snapshot with no tables, columns, or indexes."""
    return {"columns": {}, "indexes": {}}


def _snapshot_with_table(
    schema: str = "public",
    table: str = "users",
    columns: list[tuple[str, str, str]] | None = None,
) -> dict:
    """Build a snapshot with one table and its columns.

    columns: list of (column_name, data_type, is_nullable) tuples.
    """
    if columns is None:
        columns = [
            ("id", "uuid", "NO"),
            ("name", "character varying", "NO"),
            ("email", "character varying", "NO"),
        ]

    cols = {}
    for col_name, data_type, is_nullable in columns:
        col_key = f"{schema}.{table}.{col_name}"
        cols[col_key] = {
            "table_schema": schema,
            "table_name": table,
            "column_name": col_name,
            "data_type": data_type,
            "is_nullable": is_nullable,
        }

    return {"columns": cols, "indexes": {}}


def _snapshot_with_index(
    schema: str = "public",
    table: str = "users",
    index_name: str = "idx_users_email",
    indexdef: str = "CREATE INDEX idx_users_email ON public.users USING btree (email)",
    base_columns: list[tuple[str, str, str]] | None = None,
) -> dict:
    """Build a snapshot with one table and one index."""
    snap = _snapshot_with_table(schema, table, base_columns)
    idx_key = f"{schema}.{index_name}"
    snap["indexes"] = {
        idx_key: {
            "schemaname": schema,
            "tablename": table,
            "indexname": index_name,
            "indexdef": indexdef,
        }
    }
    return snap


# ---------------------------------------------------------------------------
# AC-1: New table CREATE detected
# ---------------------------------------------------------------------------

@spec_ref("FS-SCHEMA-001", "AC-1")
async def test_fs_schema_001_ac1_create_schema_changes() -> None:
    """FS-SCHEMA-001 AC-1: A new table appearing in the snapshot is detected as CREATE TABLE.

    compare_snapshots(old=empty, new=has_table) should return a change with
    change_type=CREATE, object_type=TABLE.
    """
    old = _empty_snapshot()
    new = _snapshot_with_table("public", "orders")

    changes = compare_snapshots(old, new)

    # Should detect at least one CREATE TABLE change
    create_changes = [
        c for c in changes
        if c["change_type"] == "CREATE" and c["object_type"] == "TABLE"
    ]
    assert len(create_changes) == 1, (
        f"Expected 1 CREATE TABLE change, got {len(create_changes)}: {changes}"
    )
    assert "orders" in create_changes[0]["object_name"]
    assert create_changes[0]["before_state"] is None
    assert create_changes[0]["after_state"] is not None


@spec_ref("FS-SCHEMA-001", "AC-1")
async def test_fs_schema_001_ac1_drop_table_detected() -> None:
    """AC-1 complement: a table disappearing is detected as DROP TABLE."""
    old = _snapshot_with_table("public", "legacy_table")
    new = _empty_snapshot()

    changes = compare_snapshots(old, new)

    drop_changes = [
        c for c in changes
        if c["change_type"] == "DROP" and c["object_type"] == "TABLE"
    ]
    assert len(drop_changes) == 1
    assert "legacy_table" in drop_changes[0]["object_name"]


# ---------------------------------------------------------------------------
# AC-2: Column ALTER (type/nullable change) detected
# ---------------------------------------------------------------------------

@spec_ref("FS-SCHEMA-001", "AC-2")
async def test_fs_schema_001_ac2_alter_nullable() -> None:
    """FS-SCHEMA-001 AC-2: Column ALTER detected when nullable changes.

    Changing a column from NOT NULL to NULL should produce an ALTER COLUMN change.
    """
    old = _snapshot_with_table("public", "users", columns=[
        ("id", "uuid", "NO"),
        ("email", "character varying", "NO"),
    ])
    new = _snapshot_with_table("public", "users", columns=[
        ("id", "uuid", "NO"),
        ("email", "character varying", "YES"),  # nullable changed
    ])

    changes = compare_snapshots(old, new)

    alter_changes = [
        c for c in changes
        if c["change_type"] == "ALTER" and c["object_type"] == "COLUMN"
    ]
    assert len(alter_changes) == 1, (
        f"Expected 1 ALTER COLUMN change, got {len(alter_changes)}: {changes}"
    )
    change = alter_changes[0]
    assert "email" in change["object_name"]
    assert change["before_state"]["is_nullable"] == "NO"
    assert change["after_state"]["is_nullable"] == "YES"


@spec_ref("FS-SCHEMA-001", "AC-2")
async def test_fs_schema_001_ac2_alter_data_type() -> None:
    """AC-2 complement: Column data_type change detected."""
    old = _snapshot_with_table("public", "users", columns=[
        ("id", "uuid", "NO"),
        ("email", "character varying", "NO"),
    ])
    new = _snapshot_with_table("public", "users", columns=[
        ("id", "uuid", "NO"),
        ("email", "text", "NO"),  # data_type changed
    ])

    changes = compare_snapshots(old, new)

    alter_changes = [
        c for c in changes
        if c["change_type"] == "ALTER" and c["object_type"] == "COLUMN"
    ]
    assert len(alter_changes) == 1
    assert alter_changes[0]["before_state"]["data_type"] == "character varying"
    assert alter_changes[0]["after_state"]["data_type"] == "text"


@spec_ref("FS-SCHEMA-001", "AC-2")
async def test_fs_schema_001_ac2_new_column_added() -> None:
    """AC-2 complement: A new column on an existing table is detected as ALTER COLUMN."""
    old = _snapshot_with_table("public", "users", columns=[
        ("id", "uuid", "NO"),
    ])
    new = _snapshot_with_table("public", "users", columns=[
        ("id", "uuid", "NO"),
        ("avatar_url", "text", "YES"),  # new column
    ])

    changes = compare_snapshots(old, new)

    alter_changes = [
        c for c in changes
        if c["change_type"] == "ALTER" and c["object_type"] == "COLUMN"
    ]
    assert len(alter_changes) == 1
    assert "avatar_url" in alter_changes[0]["object_name"]
    assert alter_changes[0]["before_state"] is None  # column did not exist before


@spec_ref("FS-SCHEMA-001", "AC-2")
async def test_fs_schema_001_ac2_column_removed() -> None:
    """AC-2 complement: A removed column is detected as ALTER COLUMN."""
    old = _snapshot_with_table("public", "users", columns=[
        ("id", "uuid", "NO"),
        ("deprecated_col", "text", "YES"),
    ])
    new = _snapshot_with_table("public", "users", columns=[
        ("id", "uuid", "NO"),
    ])

    changes = compare_snapshots(old, new)

    alter_changes = [
        c for c in changes
        if c["change_type"] == "ALTER" and c["object_type"] == "COLUMN"
    ]
    assert len(alter_changes) == 1
    assert "deprecated_col" in alter_changes[0]["object_name"]
    assert alter_changes[0]["after_state"] is None  # column no longer exists


# ---------------------------------------------------------------------------
# AC-3: Index CREATE/DROP detected
# ---------------------------------------------------------------------------

@spec_ref("FS-SCHEMA-001", "AC-3")
async def test_fs_schema_001_ac3_create_drop() -> None:
    """FS-SCHEMA-001 AC-3: Index CREATE and DROP are detected.

    Adding an index to the new snapshot produces CREATE INDEX.
    Removing an index from the old snapshot produces DROP INDEX.
    """
    base_columns = [("id", "uuid", "NO"), ("email", "character varying", "NO")]

    # Test CREATE INDEX
    old_no_idx = _snapshot_with_table("public", "users", base_columns)
    new_with_idx = _snapshot_with_index(
        "public", "users", "idx_users_email",
        "CREATE INDEX idx_users_email ON public.users USING btree (email)",
        base_columns,
    )

    create_changes = compare_snapshots(old_no_idx, new_with_idx)
    idx_creates = [
        c for c in create_changes
        if c["change_type"] == "CREATE" and c["object_type"] == "INDEX"
    ]
    assert len(idx_creates) == 1, (
        f"Expected 1 CREATE INDEX, got {len(idx_creates)}: {create_changes}"
    )
    assert "idx_users_email" in idx_creates[0]["object_name"]
    assert idx_creates[0]["after_state"]["indexdef"] is not None

    # Test DROP INDEX (reverse)
    drop_changes = compare_snapshots(new_with_idx, old_no_idx)
    idx_drops = [
        c for c in drop_changes
        if c["change_type"] == "DROP" and c["object_type"] == "INDEX"
    ]
    assert len(idx_drops) == 1, (
        f"Expected 1 DROP INDEX, got {len(idx_drops)}: {drop_changes}"
    )
    assert "idx_users_email" in idx_drops[0]["object_name"]


@spec_ref("FS-SCHEMA-001", "AC-3")
async def test_fs_schema_001_ac3_no_changes_when_identical() -> None:
    """AC-3 complement: identical snapshots produce zero changes."""
    base_columns = [("id", "uuid", "NO")]
    snap = _snapshot_with_index("public", "users", "idx_pk", "CREATE INDEX", base_columns)

    changes = compare_snapshots(snap, snap)
    assert changes == [], f"Identical snapshots should produce no changes: {changes}"


# ---------------------------------------------------------------------------
# AC-5: Snapshot cached in Valkey (mocked)
# ---------------------------------------------------------------------------

@spec_ref("FS-SCHEMA-001", "AC-5")
async def test_fs_schema_001_ac5_valkey() -> None:
    """FS-SCHEMA-001 AC-5: Snapshot is cached in Valkey with a per-instance key.

    Mock the Valkey client to verify _set_cached_snapshot calls SET with
    the correct key format and TTL.
    """
    instance_id = uuid4()
    snapshot = {"columns": {"test": "data"}, "indexes": {}}

    # Verify key format follows the convention
    expected_key = f"neuraldb:schema_snapshot:{instance_id}"
    assert _valkey_key(instance_id) == expected_key

    # Mock the Valkey client to verify SET is called
    mock_valkey = AsyncMock()
    mock_valkey.ping = AsyncMock(return_value=True)
    mock_valkey.set = AsyncMock(return_value=True)
    mock_valkey.aclose = AsyncMock()

    with patch(
        "app.services.schema_detector._get_valkey_client",
        return_value=mock_valkey,
    ):
        await _set_cached_snapshot(instance_id, snapshot)

    # Verify SET was called with the correct key and TTL
    mock_valkey.set.assert_called_once()
    call_args = mock_valkey.set.call_args
    assert call_args[0][0] == expected_key  # key
    assert call_args[1].get("ex") == 7200  # TTL 2 hours


@spec_ref("FS-SCHEMA-001", "AC-5")
async def test_fs_schema_001_ac5_fallback_to_memory() -> None:
    """AC-5 complement: when Valkey is unavailable, falls back to in-memory cache.

    _set_cached_snapshot should still store the snapshot in _snapshot_fallback
    even when Valkey is unreachable.
    """
    from app.services.schema_detector import _snapshot_fallback

    instance_id = uuid4()
    snapshot = {"columns": {"fallback": "test"}, "indexes": {}}
    key = _valkey_key(instance_id)

    # Clean up any existing fallback entry
    _snapshot_fallback.pop(key, None)

    # Mock Valkey as unavailable
    with patch(
        "app.services.schema_detector._get_valkey_client",
        return_value=None,
    ):
        await _set_cached_snapshot(instance_id, snapshot)

    # Should be in the in-memory fallback
    assert key in _snapshot_fallback
    assert _snapshot_fallback[key] == snapshot

    # Clean up
    _snapshot_fallback.pop(key, None)

# Spec: FS-SCHEMA-001, MVP-SCHEMA-001, MVP-SCHEMA-002
"""SchemaDetector — polling-based DDL change detection via information_schema snapshots.

Compares current schema state against a Valkey-cached snapshot to detect
CREATE/ALTER/DROP changes on tables, columns, and indexes.

Uses the adapter's asyncpg pool for querying the target DB (NOT SQLAlchemy).
Valkey is used for snapshot caching with graceful fallback to in-memory cache.
"""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import asyncpg
import structlog

from app.db.session import AsyncSessionLocal
from app.models.schema_change import SchemaChange

logger = structlog.get_logger(__name__)

# Spec: FS-SCHEMA-001 §2.2 — snapshot SQL queries
_SQL_COLUMNS = """
SELECT table_schema, table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name, ordinal_position;
"""

_SQL_INDEXES = """
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema');
"""

# In-memory fallback when Valkey is unreachable
_snapshot_fallback: dict[str, dict] = {}


def _valkey_key(instance_id: UUID) -> str:
    """Spec: FS-SCHEMA-001 AC-5 — Valkey cache key per instance."""
    return f"neuraldb:schema_snapshot:{instance_id}"


async def _get_valkey_client():
    """Lazy-init Valkey async client. Returns None if unavailable."""
    try:
        import redis.asyncio as aioredis
        from app.config import settings

        client = aioredis.from_url(settings.VALKEY_URL, socket_timeout=2)
        await client.ping()
        return client
    except Exception:
        return None


async def _get_cached_snapshot(instance_id: UUID) -> dict | None:
    """Retrieve cached snapshot from Valkey, falling back to in-memory."""
    key = _valkey_key(instance_id)

    # Try Valkey first
    valkey = await _get_valkey_client()
    if valkey is not None:
        try:
            raw = await valkey.get(key)
            if raw is not None:
                return json.loads(raw)
        except Exception:
            logger.debug("schema_detector.valkey_get_error", instance_id=str(instance_id))
        finally:
            await valkey.aclose()

    # Fallback to in-memory
    return _snapshot_fallback.get(key)


async def _set_cached_snapshot(instance_id: UUID, snapshot: dict) -> None:
    """Store snapshot in Valkey (TTL 2 hours) with in-memory fallback."""
    key = _valkey_key(instance_id)
    serialized = json.dumps(snapshot, default=str)

    # Try Valkey first
    valkey = await _get_valkey_client()
    if valkey is not None:
        try:
            await valkey.set(key, serialized, ex=7200)
        except Exception:
            logger.debug("schema_detector.valkey_set_error", instance_id=str(instance_id))
        finally:
            await valkey.aclose()

    # Always update in-memory fallback
    _snapshot_fallback[key] = snapshot


async def take_snapshot(pool: asyncpg.Pool) -> dict:
    """Query information_schema.columns + pg_indexes to build a schema snapshot.

    Returns a dict with 'columns' and 'indexes' keyed by qualified name.
    """
    async with pool.acquire() as conn:
        col_rows = await conn.fetch(_SQL_COLUMNS)
        idx_rows = await conn.fetch(_SQL_INDEXES)

    columns: dict[str, dict[str, Any]] = {}
    for row in col_rows:
        table_key = f"{row['table_schema']}.{row['table_name']}"
        col_key = f"{table_key}.{row['column_name']}"
        columns[col_key] = {
            "table_schema": row["table_schema"],
            "table_name": row["table_name"],
            "column_name": row["column_name"],
            "data_type": row["data_type"],
            "is_nullable": row["is_nullable"],
        }

    indexes: dict[str, dict[str, Any]] = {}
    for row in idx_rows:
        idx_key = f"{row['schemaname']}.{row['indexname']}"
        indexes[idx_key] = {
            "schemaname": row["schemaname"],
            "tablename": row["tablename"],
            "indexname": row["indexname"],
            "indexdef": row["indexdef"],
        }

    return {"columns": columns, "indexes": indexes}


def compare_snapshots(
    old: dict, new: dict
) -> list[dict[str, Any]]:
    """Compare two snapshots and return a list of detected change dicts.

    Spec: FS-SCHEMA-001 §2.3 — change type determination.
    """
    changes: list[dict[str, Any]] = []

    old_cols = old.get("columns", {})
    new_cols = new.get("columns", {})
    old_idxs = old.get("indexes", {})
    new_idxs = new.get("indexes", {})

    # --- Table-level detection ---
    old_tables = {
        f"{v['table_schema']}.{v['table_name']}" for v in old_cols.values()
    }
    new_tables = {
        f"{v['table_schema']}.{v['table_name']}" for v in new_cols.values()
    }

    # New tables
    for table in new_tables - old_tables:
        changes.append({
            "change_type": "CREATE",
            "object_type": "TABLE",
            "object_name": table,
            "before_state": None,
            "after_state": {"table": table},
        })

    # Dropped tables
    for table in old_tables - new_tables:
        changes.append({
            "change_type": "DROP",
            "object_type": "TABLE",
            "object_name": table,
            "before_state": {"table": table},
            "after_state": None,
        })

    # --- Column-level detection (only for tables that exist in both) ---
    surviving_tables = old_tables & new_tables

    for col_key, new_col in new_cols.items():
        table_key = f"{new_col['table_schema']}.{new_col['table_name']}"
        if table_key not in surviving_tables:
            continue  # Already reported as CREATE TABLE
        if col_key not in old_cols:
            # New column added
            changes.append({
                "change_type": "ALTER",
                "object_type": "COLUMN",
                "object_name": col_key,
                "before_state": None,
                "after_state": {
                    "data_type": new_col["data_type"],
                    "is_nullable": new_col["is_nullable"],
                },
            })

    for col_key, old_col in old_cols.items():
        table_key = f"{old_col['table_schema']}.{old_col['table_name']}"
        if table_key not in surviving_tables:
            continue  # Already reported as DROP TABLE
        if col_key not in new_cols:
            # Column removed
            changes.append({
                "change_type": "ALTER",
                "object_type": "COLUMN",
                "object_name": col_key,
                "before_state": {
                    "data_type": old_col["data_type"],
                    "is_nullable": old_col["is_nullable"],
                },
                "after_state": None,
            })
        elif col_key in new_cols:
            new_col = new_cols[col_key]
            # Column type or nullable change
            if (
                old_col["data_type"] != new_col["data_type"]
                or old_col["is_nullable"] != new_col["is_nullable"]
            ):
                changes.append({
                    "change_type": "ALTER",
                    "object_type": "COLUMN",
                    "object_name": col_key,
                    "before_state": {
                        "data_type": old_col["data_type"],
                        "is_nullable": old_col["is_nullable"],
                    },
                    "after_state": {
                        "data_type": new_col["data_type"],
                        "is_nullable": new_col["is_nullable"],
                    },
                })

    # --- Index-level detection ---
    for idx_key in new_idxs.keys() - old_idxs.keys():
        idx = new_idxs[idx_key]
        changes.append({
            "change_type": "CREATE",
            "object_type": "INDEX",
            "object_name": idx_key,
            "before_state": None,
            "after_state": {"indexdef": idx["indexdef"]},
        })

    for idx_key in old_idxs.keys() - new_idxs.keys():
        idx = old_idxs[idx_key]
        changes.append({
            "change_type": "DROP",
            "object_type": "INDEX",
            "object_name": idx_key,
            "before_state": {"indexdef": idx["indexdef"]},
            "after_state": None,
        })

    return changes


async def detect_changes(instance_id: UUID, pool: asyncpg.Pool) -> int:
    """Compare current schema with cached snapshot. Persist changes and update cache.

    Returns the number of changes detected.
    Spec: FS-SCHEMA-001 AC-1~AC-5.
    """
    now = datetime.now(timezone.utc)

    # Take current snapshot
    new_snapshot = await take_snapshot(pool)

    # Get cached (previous) snapshot
    old_snapshot = await _get_cached_snapshot(instance_id)

    if old_snapshot is None:
        # First run — cache current snapshot, no diff to report
        await _set_cached_snapshot(instance_id, new_snapshot)
        logger.info(
            "schema_detector.initial_snapshot",
            instance_id=str(instance_id),
            tables=len({
                f"{v['table_schema']}.{v['table_name']}"
                for v in new_snapshot.get("columns", {}).values()
            }),
        )
        return 0

    # Compare
    changes = compare_snapshots(old_snapshot, new_snapshot)

    if not changes:
        # Update cache even when no changes (refresh TTL)
        await _set_cached_snapshot(instance_id, new_snapshot)
        return 0

    # Persist changes to schema_changes table
    async with AsyncSessionLocal() as session:
        for change in changes:
            row = SchemaChange(
                instance_id=instance_id,
                change_type=change["change_type"],
                object_type=change["object_type"],
                object_name=change["object_name"],
                before_state=change.get("before_state"),
                after_state=change.get("after_state"),
                detected_at=now,
            )
            session.add(row)
        await session.commit()

    # Update cached snapshot
    await _set_cached_snapshot(instance_id, new_snapshot)

    logger.info(
        "schema_detector.changes_detected",
        instance_id=str(instance_id),
        count=len(changes),
    )
    return len(changes)

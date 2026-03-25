# Spec: FS-SCHEMA-001, MVP-SCHEMA-001
"""Celery task for periodic schema change detection.

Iterates all active PostgreSQL instances every 60 seconds, compares
information_schema snapshots against cached state, and persists detected
DDL changes (CREATE/ALTER/DROP) to the schema_changes table.

Resilience: failures on individual instances are logged and skipped.
"""

import asyncio
from uuid import UUID

import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.db_instance import DBInstance
from app.services.schema_detector import detect_changes
from app.tasks.collect import _get_adapter

logger = structlog.get_logger(__name__)


async def _get_active_pg_instances() -> list[DBInstance]:
    """Fetch all active, non-deleted PostgreSQL instances."""
    async with AsyncSessionLocal() as session:
        stmt = select(DBInstance).where(
            DBInstance.is_active.is_(True),
            DBInstance.deleted_at.is_(None),
            DBInstance.db_type == "postgresql",
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def _detect_schema_changes_async() -> None:
    """Core async loop: iterate instances and detect schema changes.

    Spec: FS-SCHEMA-001 — skip instances on error (resilient).
    """
    instances = await _get_active_pg_instances()
    if not instances:
        return

    for instance in instances:
        try:
            adapter = await _get_adapter(instance)
            if adapter is None:
                logger.warning(
                    "schema.adapter_unavailable",
                    instance_id=str(instance.id),
                )
                continue

            # Use the adapter's asyncpg pool directly (NOT SQLAlchemy)
            pool = adapter._pool
            if pool is None:
                continue

            changes_count = await detect_changes(instance.id, pool)
            if changes_count > 0:
                logger.info(
                    "schema.changes_found",
                    instance_id=str(instance.id),
                    count=changes_count,
                )

        except Exception as exc:
            # Spec: FS-SCHEMA-001 — resilient, skip on error
            logger.warning(
                "schema.instance_error",
                instance_id=str(instance.id),
                error=str(exc),
            )
            continue


@shared_task(
    name="app.tasks.schema.detect_schema_changes",
    soft_time_limit=30,
    acks_late=True,
    reject_on_worker_lost=True,
    ignore_result=True,
)
def detect_schema_changes() -> None:
    """Detect schema changes for all active instances (60-second interval)."""
    asyncio.run(_detect_schema_changes_async())

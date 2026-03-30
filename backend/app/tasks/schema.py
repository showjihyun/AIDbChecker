# Spec: FS-SCHEMA-001, MVP-SCHEMA-001
"""Celery task for periodic schema change detection.

Iterates all active PostgreSQL instances every 60 seconds, compares
information_schema snapshots against cached state, and persists detected
DDL changes (CREATE/ALTER/DROP) to the schema_changes table.

Resilience: failures on individual instances are logged and skipped.
"""

import asyncio

import structlog
from celery import shared_task
from sqlalchemy import select

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
                # Auto-refresh Knowledge Graph on schema change
                await _refresh_graph(instance.id, pool)

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


async def _refresh_graph(instance_id, pool) -> None:
    """Auto-refresh Knowledge Graph when schema changes are detected.

    Rebuilds graph_nodes + graph_edges from information_schema.
    Non-blocking — failure does not affect schema detection.
    """
    try:
        from app.db.session import create_worker_session
        from app.services.graph_rag import SchemaGraphBuilder

        SessionLocal = create_worker_session()
        async with SessionLocal() as session:
            builder = SchemaGraphBuilder()
            nodes, edges = await builder.build_graph(session, instance_id, pool)
            await session.commit()
            logger.info(
                "schema.graph_refreshed",
                instance_id=str(instance_id),
                nodes=nodes,
                edges=edges,
            )
    except Exception as exc:
        logger.warning(
            "schema.graph_refresh_failed",
            instance_id=str(instance_id),
            error=str(exc),
        )

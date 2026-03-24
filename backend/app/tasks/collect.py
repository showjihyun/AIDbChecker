# Spec: AG-001, MVP-COLLECT-001, MVP-COLLECT-004
"""Celery tasks for periodic metric and ASH collection.

Each task iterates over all active DB instances, calls the adapter,
and persists results to the system DB. Failures are logged and skipped
(silent skip) to prevent one instance's issues from blocking others.

Safety: soft_time_limit=3, acks_late=True.
"""

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import ActiveSessionSample, MetricSample
from app.adapters.postgresql.remote import PostgreSQLRemoteAdapter
from app.db.session import AsyncSessionLocal
from app.models.active_session import ActiveSession as ActiveSessionModel
from app.models.db_instance import DBInstance
from app.models.metric import MetricSample as MetricSampleModel
from app.utils.encryption import decrypt_value

logger = structlog.get_logger(__name__)

# In-memory adapter cache (per-worker process)
_adapter_cache: dict[UUID, PostgreSQLRemoteAdapter] = {}


def _build_dsn(instance: DBInstance) -> str:
    """Build asyncpg DSN from instance fields + decrypted credentials."""
    config = instance.connection_config or {}
    username = decrypt_value(config["username"]) if "username" in config else "neuraldb"
    password = decrypt_value(config["password"]) if "password" in config else ""
    ssl_mode = config.get("sslmode", "prefer")
    return (
        f"postgresql://{username}:{password}"
        f"@{instance.host}:{instance.port}/{instance.database_name}"
        f"?sslmode={ssl_mode}"
    )


async def _get_adapter(instance: DBInstance) -> PostgreSQLRemoteAdapter | None:
    """Get or create adapter for an instance. Returns None if connect fails."""
    if instance.id in _adapter_cache:
        return _adapter_cache[instance.id]

    dsn = _build_dsn(instance)
    adapter = PostgreSQLRemoteAdapter(instance_id=instance.id, dsn=dsn)
    connected = await adapter.connect()
    if not connected:
        return None

    _adapter_cache[instance.id] = adapter
    return adapter


async def _get_active_instances(session: AsyncSession) -> list[DBInstance]:
    """Fetch all active, non-deleted PostgreSQL instances."""
    stmt = select(DBInstance).where(
        DBInstance.is_active.is_(True),
        DBInstance.deleted_at.is_(None),
        DBInstance.db_type == "postgresql",
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _persist_metric(session: AsyncSession, sample: MetricSample) -> None:
    """Insert a MetricSample into the system DB."""
    row = MetricSampleModel(
        instance_id=sample.instance_id,
        sampled_at=sample.sampled_at,
        category=sample.category,
        metrics=sample.metrics,
    )
    session.add(row)
    await session.commit()


async def _persist_ash(session: AsyncSession, samples: list[ActiveSessionSample]) -> None:
    """Insert ASH samples into the system DB."""
    if not samples:
        return

    rows = [
        ActiveSessionModel(
            instance_id=s.instance_id,
            sampled_at=s.sampled_at,
            pid=s.pid,
            query=s.query[:4096] if s.query else None,  # truncate long queries
            query_hash=s.query_hash,
            state=s.state,
            wait_event_type=s.wait_event_type,
            wait_event=s.wait_event,
            backend_type=s.backend_type,
            client_addr=s.client_addr,
            application_name=s.application_name,
            query_start=s.query_start,
            duration_ms=s.duration_ms,
        )
        for s in samples
    ]
    session.add_all(rows)
    await session.commit()


async def _broadcast_metric(instance_id: UUID, sample: MetricSample) -> None:
    """Broadcast metric update via Socket.io (best-effort)."""
    try:
        from app.websocket.events import broadcast_metric

        await broadcast_metric(
            str(instance_id),
            {
                "instance_id": str(sample.instance_id),
                "sampled_at": sample.sampled_at.isoformat(),
                "category": sample.category,
                "metrics": sample.metrics,
            },
        )
    except ImportError:
        pass  # Socket.io not initialized in worker context
    except Exception:
        pass  # Best-effort broadcast, never block collection


async def _collect_metrics_async(category: str) -> None:
    """Core async collection loop for a given category."""
    async with AsyncSessionLocal() as session:
        instances = await _get_active_instances(session)

    for instance in instances:
        try:
            adapter = await _get_adapter(instance)
            if adapter is None:
                continue

            sample = await adapter.collect_metrics(category)
            if sample is None:
                continue

            async with AsyncSessionLocal() as session:
                await _persist_metric(session, sample)

            if category == "hot":
                await _broadcast_metric(instance.id, sample)

        except Exception as exc:
            # Silent skip — never let one instance block others
            logger.warning(
                "collect.instance_error",
                instance_id=str(instance.id),
                category=category,
                error=str(exc),
            )


async def _collect_ash_async() -> None:
    """Core async ASH collection loop."""
    async with AsyncSessionLocal() as session:
        instances = await _get_active_instances(session)

    for instance in instances:
        try:
            adapter = await _get_adapter(instance)
            if adapter is None:
                continue

            samples = await adapter.collect_ash()
            if not samples:
                continue

            async with AsyncSessionLocal() as session:
                await _persist_ash(session, samples)

        except Exception as exc:
            logger.warning(
                "collect.ash_error",
                instance_id=str(instance.id),
                error=str(exc),
            )


@shared_task(
    name="app.tasks.collect.collect_hot_metrics",
    soft_time_limit=3,
    acks_late=True,
    ignore_result=True,
)
def collect_hot_metrics() -> None:
    """Collect hot metrics (1-second interval) for all active instances."""
    asyncio.get_event_loop().run_until_complete(_collect_metrics_async("hot"))


@shared_task(
    name="app.tasks.collect.collect_warm_metrics",
    soft_time_limit=3,
    acks_late=True,
    ignore_result=True,
)
def collect_warm_metrics() -> None:
    """Collect warm metrics (10-second interval) for all active instances."""
    asyncio.get_event_loop().run_until_complete(_collect_metrics_async("warm"))


@shared_task(
    name="app.tasks.collect.collect_cold_metrics",
    soft_time_limit=3,
    acks_late=True,
    ignore_result=True,
)
def collect_cold_metrics() -> None:
    """Collect cold metrics (1-minute interval) for all active instances."""
    asyncio.get_event_loop().run_until_complete(_collect_metrics_async("cold"))


@shared_task(
    name="app.tasks.collect.collect_ash_samples",
    soft_time_limit=3,
    acks_late=True,
    ignore_result=True,
)
def collect_ash_samples() -> None:
    """Collect ASH samples (1-second interval) for all active instances."""
    asyncio.get_event_loop().run_until_complete(_collect_ash_async())

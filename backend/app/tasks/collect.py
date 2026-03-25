# Spec: AG-001, MVP-COLLECT-001, MVP-COLLECT-004
"""Celery tasks for periodic metric and ASH collection.

Each task iterates over all active DB instances, calls the adapter,
and persists results to the system DB. Failures are logged and skipped
(silent skip) to prevent one instance's issues from blocking others.

Safety: soft_time_limit=3, acks_late=True, reject_on_worker_lost=True.
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
from app.db.session import create_worker_session
from app.models.active_session import ActiveSession as ActiveSessionModel
from app.models.db_instance import DBInstance
from app.models.metric import MetricSample as MetricSampleModel
from app.utils.encryption import decrypt_value

logger = structlog.get_logger(__name__)

# In-memory adapter cache (per-worker process)
# Maps instance_id -> (adapter, dsn) for stale DSN detection
_adapter_cache: dict[UUID, tuple[PostgreSQLRemoteAdapter, str]] = {}


def _build_dsn(instance: DBInstance) -> str:
    """Build asyncpg DSN from instance fields + decrypted credentials."""
    import urllib.parse

    config = instance.connection_config or {}
    username = decrypt_value(config["username"]) if "username" in config else "neuraldb"
    password = decrypt_value(config["password"]) if "password" in config else ""
    ssl_mode = config.get("sslmode", "prefer")
    return (
        f"postgresql://{urllib.parse.quote_plus(username)}:{urllib.parse.quote_plus(password)}"
        f"@{instance.host}:{instance.port}/{instance.database_name}"
        f"?sslmode={ssl_mode}"
    )


async def _get_adapter(instance: DBInstance) -> PostgreSQLRemoteAdapter | None:
    """Get or create adapter for an instance. Returns None if connect fails.

    Invalidates cached adapter when the instance DSN has changed (e.g. password
    rotation or host migration).
    """
    dsn = _build_dsn(instance)

    if instance.id in _adapter_cache:
        cached_adapter, cached_dsn = _adapter_cache[instance.id]
        if cached_dsn == dsn:
            return cached_adapter
        # DSN changed — disconnect old adapter and create a new one
        logger.info(
            "adapter.cache_invalidated",
            instance_id=str(instance.id),
            reason="dsn_changed",
        )
        await cached_adapter.disconnect()
        del _adapter_cache[instance.id]

    adapter = PostgreSQLRemoteAdapter(instance_id=instance.id, dsn=dsn)
    connected = await adapter.connect()
    if not connected:
        return None

    _adapter_cache[instance.id] = (adapter, dsn)
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


async def _collect_single_metric(
    instance: DBInstance,
    category: str,
) -> tuple[MetricSampleModel | None, MetricSample | None]:
    """Collect a single instance's metric. Returns (orm_row, raw_sample) or (None, None)."""
    try:
        adapter = await _get_adapter(instance)
        if adapter is None:
            return None, None

        sample = await adapter.collect_metrics(category)
        if sample is None:
            return None, None

        row = MetricSampleModel(
            instance_id=sample.instance_id,
            sampled_at=sample.sampled_at,
            category=sample.category,
            metrics=sample.metrics,
        )
        return row, sample

    except Exception as exc:
        # Silent skip -- never let one instance block others
        logger.warning(
            "collect.instance_error",
            instance_id=str(instance.id),
            category=category,
            error=str(exc),
        )
        return None, None


async def _broadcast_metric(instance_id: UUID, sample: MetricSample) -> None:
    """Broadcast metric update via Socket.io (best-effort, via Valkey pub/sub)."""
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
    """Core async collection loop for a given category.

    Collects from all instances in parallel via asyncio.gather(),
    then batch-persists all results in a single commit.
    """
    async with create_worker_session()() as session:
        instances = await _get_active_instances(session)

    if not instances:
        return

    # Collect from all instances in parallel
    tasks = [_collect_single_metric(inst, category) for inst in instances]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Batch persist all successful results in a single commit
    rows_to_add: list[MetricSampleModel] = []
    broadcast_items: list[tuple[UUID, MetricSample]] = []

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(
                "collect.gather_error",
                instance_id=str(instances[i].id),
                category=category,
                error=str(result),
            )
            continue
        row, sample = result
        if row is not None and sample is not None:
            rows_to_add.append(row)
            if category == "hot":
                broadcast_items.append((instances[i].id, sample))

    if rows_to_add:
        async with create_worker_session()() as session:
            session.add_all(rows_to_add)
            await session.commit()

    # Best-effort broadcast for hot metrics
    for instance_id, sample in broadcast_items:
        await _broadcast_metric(instance_id, sample)

    # Spec: MVP-AI-002 -- trigger anomaly detection for each hot metric sample
    if category == "hot" and broadcast_items:
        try:
            from app.tasks.analyze import check_anomalies

            for instance_id, sample in broadcast_items:
                check_anomalies.delay(
                    str(sample.instance_id),
                    sample.metrics,
                    sample.sampled_at.isoformat(),
                )
        except Exception:
            pass  # Best-effort: anomaly check failure must not block collection


async def _collect_single_ash(
    instance: DBInstance,
) -> list[ActiveSessionModel]:
    """Collect ASH samples from a single instance. Returns ORM rows."""
    try:
        adapter = await _get_adapter(instance)
        if adapter is None:
            return []

        samples = await adapter.collect_ash()
        if not samples:
            return []

        return [
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

    except Exception as exc:
        logger.warning(
            "collect.ash_error",
            instance_id=str(instance.id),
            error=str(exc),
        )
        return []


async def _collect_ash_async() -> None:
    """Core async ASH collection loop.

    Collects from all instances in parallel via asyncio.gather(),
    then batch-persists all results in a single commit.
    """
    async with create_worker_session()() as session:
        instances = await _get_active_instances(session)

    if not instances:
        return

    # Collect from all instances in parallel
    tasks = [_collect_single_ash(inst) for inst in instances]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Batch persist
    all_rows: list[ActiveSessionModel] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(
                "collect.ash_gather_error",
                instance_id=str(instances[i].id),
                error=str(result),
            )
            continue
        all_rows.extend(result)

    if all_rows:
        async with create_worker_session()() as session:
            session.add_all(all_rows)
            await session.commit()


@shared_task(
    name="app.tasks.collect.collect_hot_metrics",
    soft_time_limit=3,
    acks_late=True,
    reject_on_worker_lost=True,
    ignore_result=True,
)
def collect_hot_metrics() -> None:
    """Collect hot metrics (1-second interval) for all active instances."""
    _adapter_cache.clear()  # Each asyncio.run() creates a new event loop
    asyncio.run(_collect_metrics_async("hot"))


@shared_task(
    name="app.tasks.collect.collect_warm_metrics",
    soft_time_limit=3,
    acks_late=True,
    reject_on_worker_lost=True,
    ignore_result=True,
)
def collect_warm_metrics() -> None:
    """Collect warm metrics (10-second interval) for all active instances."""
    _adapter_cache.clear()
    asyncio.run(_collect_metrics_async("warm"))


@shared_task(
    name="app.tasks.collect.collect_cold_metrics",
    soft_time_limit=3,
    acks_late=True,
    reject_on_worker_lost=True,
    ignore_result=True,
)
def collect_cold_metrics() -> None:
    """Collect cold metrics (1-minute interval) for all active instances."""
    _adapter_cache.clear()
    asyncio.run(_collect_metrics_async("cold"))


@shared_task(
    name="app.tasks.collect.collect_ash_samples",
    soft_time_limit=3,
    acks_late=True,
    reject_on_worker_lost=True,
    ignore_result=True,
)
def collect_ash_samples() -> None:
    """Collect ASH samples (1-second interval) for all active instances."""
    _adapter_cache.clear()
    asyncio.run(_collect_ash_async())

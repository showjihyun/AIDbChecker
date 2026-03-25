# Spec: MVP-AI-001, MVP-AI-002
"""Celery tasks for baseline training and anomaly detection.

- retrain_baselines: scheduled every 6 hours via Celery Beat.
  Iterates all active instances and retrains baselines for all hot metric types.

- check_anomalies: called after each hot metric collection.
  Checks latest metric values against baselines and creates incidents on anomaly.

Both tasks follow the same resilience pattern as collect.py:
  - Silent skip on individual instance failures
  - soft_time_limit for safety
  - async core wrapped in asyncio.run()
"""

import asyncio
from uuid import UUID

import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzers.anomaly import AnomalyDetector
from app.analyzers.baseline import BaselineAnalyzer, HOT_METRIC_KEYS
from app.db.session import AsyncSessionLocal
from app.models.db_instance import DBInstance

logger = structlog.get_logger(__name__)


async def _get_active_instances(session: AsyncSession) -> list[DBInstance]:
    """Fetch all active, non-deleted PostgreSQL instances."""
    stmt = select(DBInstance).where(
        DBInstance.is_active.is_(True),
        DBInstance.deleted_at.is_(None),
        DBInstance.db_type == "postgresql",
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _retrain_baselines_async() -> None:
    """Retrain baselines for all active instances and all hot metric types.

    Spec: MVP-AI-001 -- 6-hour retrain interval, STL + Isolation Forest.
    """
    analyzer = BaselineAnalyzer()

    async with AsyncSessionLocal() as session:
        instances = await _get_active_instances(session)

    if not instances:
        logger.info("retrain_baselines.no_instances")
        return

    total_trained = 0
    total_skipped = 0

    for instance in instances:
        for metric_type in HOT_METRIC_KEYS:
            try:
                trained = await analyzer.train(instance.id, metric_type)
                if trained:
                    total_trained += 1
                else:
                    total_skipped += 1
            except Exception as exc:
                # Silent skip -- one failure must not block other trainings
                logger.warning(
                    "retrain_baselines.error",
                    instance_id=str(instance.id),
                    metric_type=metric_type,
                    error=str(exc),
                )
                total_skipped += 1

    logger.info(
        "retrain_baselines.complete",
        instances=len(instances),
        trained=total_trained,
        skipped=total_skipped,
    )


async def _check_anomalies_async(
    instance_id: str,
    metrics: dict,
    sampled_at_iso: str | None,
) -> None:
    """Check a single metric sample against baselines.

    Spec: MVP-AI-002 -- dynamic anomaly detection after each hot metric collection.
    """
    from datetime import datetime, timezone

    detector = AnomalyDetector()

    sampled_at = None
    if sampled_at_iso:
        try:
            sampled_at = datetime.fromisoformat(sampled_at_iso)
        except (ValueError, TypeError):
            sampled_at = datetime.now(timezone.utc)

    try:
        incidents = await detector.check(
            instance_id=UUID(instance_id),
            metric_sample=metrics,
            sampled_at=sampled_at,
        )
        if incidents:
            logger.info(
                "check_anomalies.incidents_created",
                instance_id=instance_id,
                count=len(incidents),
                severities=[i.severity for i in incidents],
            )
    except Exception as exc:
        # Silent skip -- anomaly detection must never crash the pipeline
        logger.warning(
            "check_anomalies.error",
            instance_id=instance_id,
            error=str(exc),
        )


@shared_task(
    name="app.tasks.analyze.retrain_baselines",
    soft_time_limit=300,  # 5 minutes max for full retrain
    acks_late=True,
    reject_on_worker_lost=True,
    ignore_result=True,
)
def retrain_baselines() -> None:
    """Retrain all baselines. Scheduled every 6 hours via Celery Beat.

    Spec: MVP-AI-001 -- baseline_retrain_interval: 6h
    """
    asyncio.run(_retrain_baselines_async())


@shared_task(
    name="app.tasks.analyze.check_anomalies",
    soft_time_limit=10,
    acks_late=True,
    reject_on_worker_lost=True,
    ignore_result=True,
)
def check_anomalies(
    instance_id: str,
    metrics: dict,
    sampled_at_iso: str | None = None,
) -> None:
    """Check a metric sample for anomalies. Called after hot metric collection.

    Args:
        instance_id: UUID string of the DB instance.
        metrics: JSONB metrics dict from the collected sample.
        sampled_at_iso: ISO timestamp of the sample.

    Spec: MVP-AI-002 -- dynamic anomaly detection.
    """
    asyncio.run(_check_anomalies_async(instance_id, metrics, sampled_at_iso))

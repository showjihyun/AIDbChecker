# Spec: FR-AI-005, FS-AI-005
"""Celery tasks for scheduled AIGC report generation.

Weekly report: every Monday 09:00 KST (00:00 UTC)
Generates health reports for all active instances and notifies via Slack.
"""

import asyncio

import structlog

from app.tasks import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="generate_weekly_report",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=120,
    time_limit=180,
)
def generate_weekly_report(self):
    """Generate weekly health reports for all active instances.

    Spec: FS-AI-005 Section 4.4 — scheduled via Celery Beat.
    Schedule: every Monday 09:00 KST (Sunday 00:00 UTC).

    For each active instance:
      1. Generate 7-day health report
      2. Log to audit_logs (AI Decision Log)
      3. Send Slack notification with report link
    """
    logger.info("report.weekly_started")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            count = loop.run_until_complete(_generate_all_reports())
        finally:
            loop.close()

        logger.info("report.weekly_completed", instances_reported=count)
        return {"status": "completed", "instances_reported": count}

    except Exception as exc:
        logger.error("report.weekly_failed", error=str(exc))
        raise self.retry(exc=exc)


async def _generate_all_reports() -> int:
    """Generate reports for all active instances."""
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.db_instance import DBInstance
    from app.services import report_generator

    count = 0
    async with AsyncSessionLocal() as session:
        stmt = select(DBInstance).where(
            DBInstance.is_active.is_(True),
            DBInstance.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        instances = result.scalars().all()

        for instance in instances:
            try:
                report = await report_generator.generate_report(
                    session,
                    instance_id=instance.id,
                    period="7d",
                    language="ko",
                )
                if report.status == "completed":
                    count += 1
                    logger.info(
                        "report.weekly_instance_done",
                        instance=instance.name,
                        confidence=report.confidence,
                    )
            except Exception as exc:
                logger.warning(
                    "report.weekly_instance_failed",
                    instance=instance.name,
                    error=str(exc),
                )

    return count

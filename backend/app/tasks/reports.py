# Spec: FS-AI-REPORT-001
"""Celery tasks for DBA periodic reports — Daily/Weekly/Monthly."""

from __future__ import annotations

import asyncio

import structlog

from app.tasks import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="app.tasks.reports.generate_dba_report", bind=True, max_retries=2)
def generate_dba_report_task(self, period: str = "daily") -> dict:
    """Generate and send DBA report for all active instances.

    Spec: FS-AI-REPORT-001 §5 — Celery Beat scheduled task.
    """
    try:
        return asyncio.get_event_loop().run_until_complete(_run_report(period))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run_report(period))
        finally:
            loop.close()


async def _run_report(period: str) -> dict:
    """Generate reports for all active instances and send via Slack."""
    import asyncpg
    from sqlalchemy import select

    from app.config import settings
    from app.db.session import AsyncSessionLocal
    from app.models.db_instance import DBInstance
    from app.services.dba_report import format_slack_report, generate_dba_report
    from app.utils.dsn import build_target_dsn

    results = {"period": period, "reports": [], "errors": []}

    async with AsyncSessionLocal() as session:
        stmt = select(DBInstance).where(
            DBInstance.is_active.is_(True),
            DBInstance.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        instances = result.scalars().all()

        for inst in instances:
            pool = None
            try:
                # Connect to target DB for slow query data
                dsn = build_target_dsn(inst)
                pool = await asyncio.wait_for(
                    asyncpg.create_pool(dsn, min_size=1, max_size=2, command_timeout=10),
                    timeout=5,
                )

                report = await generate_dba_report(
                    session=session,
                    instance_id=inst.id,
                    instance_name=inst.name,
                    period=period,
                    pool=pool,
                )

                # Send to Slack
                if settings.SLACK_WEBHOOK_URL:
                    slack_msg = format_slack_report(report)
                    await _send_slack(slack_msg)
                    report["slack_sent"] = True
                else:
                    report["slack_sent"] = False

                results["reports"].append(
                    {
                        "instance": inst.name,
                        "incidents": report["incident_count"],
                        "slow_queries": len(report["slow_queries"]),
                        "slack_sent": report.get("slack_sent", False),
                    }
                )

            except Exception as exc:
                logger.warning(
                    "dba_report.instance_failed",
                    instance=inst.name,
                    error=str(exc),
                )
                results["errors"].append({"instance": inst.name, "error": str(exc)})
            finally:
                if pool:
                    await pool.close()

    logger.info("dba_report.batch_complete", period=period, count=len(results["reports"]))
    return results


async def _send_slack(message: str) -> None:
    """Send message to Slack webhook."""
    import httpx

    from app.config import settings

    if not settings.SLACK_WEBHOOK_URL:
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                settings.SLACK_WEBHOOK_URL,
                json={"text": message},
            )
            if resp.status_code != 200:
                logger.warning("slack.send_failed", status=resp.status_code)
    except Exception as exc:
        logger.warning("slack.error", error=str(exc))

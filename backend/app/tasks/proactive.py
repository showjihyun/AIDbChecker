# Spec: FS-DBA-003
"""Proactive Agent Celery tasks — scheduled health checks.

Registered in Celery Beat:
- proactive_quick_check: every 30 minutes
- proactive_deep_analysis: every 6 hours
- proactive_morning_report: daily at 09:00
"""

from __future__ import annotations

import asyncio

import structlog

from app.tasks import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="proactive_quick_check", bind=True, max_retries=1)
def proactive_quick_check(self):
    """AC-1: 30-min quick check across all active instances."""
    asyncio.run(_run_quick_check())


@celery_app.task(name="proactive_deep_analysis", bind=True, max_retries=0)
def proactive_deep_analysis(self):
    """AC-4: 6-hour deep analysis across all active instances."""
    asyncio.run(_run_deep_analysis())


@celery_app.task(name="proactive_morning_report", bind=True, max_retries=0)
def proactive_morning_report(self):
    """AC-8: Daily morning report across all active instances."""
    asyncio.run(_run_morning_report())


async def _run_quick_check():
    """Execute quick check for all active instances."""
    from uuid import UUID

    from sqlalchemy import select

    from app.agents.proactive_agent import ProactiveAgent
    from app.db.session import create_worker_session
    from app.models.db_instance import DBInstance

    SessionLocal = create_worker_session()
    agent = ProactiveAgent()

    async with SessionLocal() as session:
        stmt = select(DBInstance).where(
            DBInstance.is_active.is_(True),
            DBInstance.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        instances = result.scalars().all()

        for inst in instances:
            try:
                check = await agent.quick_check(inst.id, session, pool=None)
                if check["status"] == "anomaly":
                    # Send Slack alert
                    msg = agent.format_slack_alert(check, inst.name)
                    await _send_slack(msg)
                    logger.warning(
                        "proactive.alert_sent",
                        instance=inst.name,
                        findings=len(check.get("findings", [])),
                    )
            except Exception as exc:
                logger.error(
                    "proactive.quick_check_failed",
                    instance=inst.name,
                    error=str(exc),
                )


async def _run_deep_analysis():
    """Execute deep analysis for all active instances."""
    from sqlalchemy import select

    from app.agents.proactive_agent import ProactiveAgent
    from app.db.session import create_worker_session
    from app.models.db_instance import DBInstance

    SessionLocal = create_worker_session()
    agent = ProactiveAgent()

    async with SessionLocal() as session:
        stmt = select(DBInstance).where(
            DBInstance.is_active.is_(True),
            DBInstance.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        instances = result.scalars().all()

        for inst in instances:
            try:
                analysis = await agent.deep_analysis(
                    inst.id, session, pool=None,
                )
                logger.info(
                    "proactive.deep_analysis_complete",
                    instance=inst.name,
                )
            except Exception as exc:
                logger.error(
                    "proactive.deep_analysis_failed",
                    instance=inst.name,
                    error=str(exc),
                )


async def _run_morning_report():
    """Generate and send morning report for all instances."""
    from sqlalchemy import select

    from app.agents.proactive_agent import ProactiveAgent
    from app.db.session import create_worker_session
    from app.models.db_instance import DBInstance

    SessionLocal = create_worker_session()
    agent = ProactiveAgent()

    async with SessionLocal() as session:
        stmt = select(DBInstance).where(
            DBInstance.is_active.is_(True),
            DBInstance.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        instances = result.scalars().all()

        for inst in instances:
            try:
                report = await agent.morning_report(inst.id, session)
                msg = agent.format_morning_report(report, inst.name)
                await _send_slack(msg)
                logger.info("proactive.report_sent", instance=inst.name)
            except Exception as exc:
                logger.error(
                    "proactive.report_failed",
                    instance=inst.name,
                    error=str(exc),
                )


async def _send_slack(message: str):
    """Send message to Slack via configured webhook."""
    try:
        from app.config import settings

        if not settings.SLACK_WEBHOOK_URL:
            logger.debug("proactive.slack_not_configured")
            return

        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                settings.SLACK_WEBHOOK_URL,
                json={"text": message},
            )
    except Exception as exc:
        logger.error("proactive.slack_failed", error=str(exc))

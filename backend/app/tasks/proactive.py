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
            pool = None
            try:
                # Build target DB pool for this instance
                pool = await _get_pool(inst)

                check = await agent.quick_check(inst.id, session, pool=pool)
                if check["status"] == "anomaly":
                    # Send Slack alert
                    msg = agent.format_slack_alert(check, inst.name)
                    await _send_slack(msg)

                    # Self-Healing: trigger DBA Agent analysis for each finding
                    for finding in check.get("findings", []):
                        if finding.get("action") in ("analyze", "diagnose"):
                            await _trigger_dba_analysis(
                                inst, finding, session, pool,
                            )

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
            finally:
                if pool:
                    await pool.close()


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
            pool = None
            try:
                pool = await _get_pool(inst)
                analysis = await agent.deep_analysis(
                    inst.id, session, pool=pool,
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
            finally:
                if pool:
                    await pool.close()


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


async def _get_pool(instance):
    """Build asyncpg pool for a target DB instance."""
    try:
        import asyncpg

        from app.utils.dsn import build_target_dsn

        dsn = build_target_dsn(instance)
        return await asyncpg.create_pool(
            dsn, min_size=1, max_size=2,
            command_timeout=10,
            server_settings={"statement_timeout": "10000"},
        )
    except Exception as exc:
        logger.warning("proactive.pool_failed", instance=instance.name, error=str(exc))
        return None


async def _trigger_dba_analysis(instance, finding: dict, session, pool):
    """Self-Healing: trigger DBA Agent analysis on anomaly finding."""
    try:
        from app.agents.dba_agent import DBAAgent

        question = f"Analyze: {finding.get('message', 'anomaly detected')}"
        agent = DBAAgent()
        response = await agent.ask(
            question=question,
            instance_id=instance.id,
            session=session,
            pool=pool,
            autonomy_level=instance.autonomy_level,
            user_role="db_admin",
        )
        logger.info(
            "proactive.self_healing_triggered",
            instance=instance.name,
            intent=response.intent,
            metric=finding.get("metric"),
        )

        # If L3+ and actions suggested, they'll be auto-executed by DBA Agent
        if response.actions:
            action_msg = "\n".join(
                f"  [{a.status}] {a.action_type}: {a.description}"
                for a in response.actions
            )
            await _send_slack(
                f"🤖 [Self-Healing] {instance.name}\n"
                f"Trigger: {finding.get('message')}\n"
                f"Agent response ({response.intent}):\n{action_msg}"
            )
    except Exception as exc:
        logger.error(
            "proactive.self_healing_failed",
            instance=instance.name,
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

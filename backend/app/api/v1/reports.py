# Spec: FR-AI-005, FS-AI-005
"""AIGC Report API — generate and retrieve AI-powered database health reports.

POST /reports/generate — Generate a new report via LLM analysis.
GET  /reports          — List generated reports (stub for Phase 2 storage).
GET  /reports/{id}     — Retrieve a specific report (stub for Phase 2 storage).
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session, require_role
from app.models.user import User
from app.schemas.report import (
    ReportGenerateRequest,
    ReportGenerateResponse,
)
from app.services import report_generator

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post(
    "/reports/generate",
    response_model=ReportGenerateResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Generate AIGC database health report",
    description="Collects metrics, incidents, ASH, baselines, and schema changes "
    "for the specified period, then uses LLM to generate a structured health report "
    "with executive summary, analysis sections, and actionable recommendations.",
)
async def generate_report(
    body: ReportGenerateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReportGenerateResponse:
    """Generate an AIGC report.

    Spec: FS-AI-005 — AC-1: 30-second response target.
    """
    # Validate custom period
    if body.period == "custom" and (not body.period_start or not body.period_end):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_start and period_end required when period='custom'",
        )

    if (
        body.period == "custom"
        and body.period_start
        and body.period_end
        and body.period_start >= body.period_end
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_start must be before period_end",
        )

    logger.info(
        "report.generate_requested",
        instance_id=str(body.instance_id),
        period=body.period,
        report_type=body.report_type.value,
        user=current_user.email,
    )

    result = await report_generator.generate_report(
        session,
        instance_id=body.instance_id,
        period=body.period,
        period_start=body.period_start,
        period_end=body.period_end,
        report_type=body.report_type,
        report_format=body.format,
        language=body.language,
        custom_prompt=body.custom_prompt,
    )

    if result.status == "failed":
        logger.warning("report.generation_failed", report_id=str(result.report_id))

    return result


# ---------------------------------------------------------------------------
# DBA Report — Spec: FS-AI-REPORT-001
# ---------------------------------------------------------------------------


class DBAReportRequest(BaseModel):
    """DBA Report request."""

    instance_id: UUID
    period: str = Field("daily", pattern=r"^(daily|weekly|monthly)$")
    send_slack: bool = True
    slow_query_limit: int = Field(default=10, ge=1, le=50)


class DBAReportResponse(BaseModel):
    """DBA Report response."""

    instance_name: str
    period: str
    generated_at: str
    metrics_summary: dict
    incident_count: int
    slow_queries: list[dict]
    schema_changes_count: int
    ai_analysis: str
    slack_sent: bool = False


@router.post(
    "/reports/dba",
    response_model=DBAReportResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Generate DBA periodic report (Daily/Weekly/Monthly)",
)
async def generate_dba_report(
    body: DBAReportRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DBAReportResponse:
    """Spec: FS-AI-REPORT-001 — Generate DBA report with slow query details."""
    import asyncio

    import asyncpg
    from sqlalchemy import select

    from app.models.db_instance import DBInstance
    from app.services.dba_report import (
        format_slack_report,
    )
    from app.services.dba_report import (
        generate_dba_report as gen_report,
    )
    from app.utils.dsn import build_target_dsn

    # Fetch instance
    stmt = select(DBInstance).where(
        DBInstance.id == body.instance_id,
        DBInstance.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="Instance not found")

    # Connect to target DB
    pool = None
    try:
        dsn = build_target_dsn(inst)
        pool = await asyncio.wait_for(
            asyncpg.create_pool(dsn, min_size=1, max_size=2, command_timeout=10),
            timeout=5,
        )
    except Exception:
        pass  # Slow queries will be empty

    try:
        report = await gen_report(
            session=session,
            instance_id=inst.id,
            instance_name=inst.name,
            period=body.period,
            pool=pool,
            slow_query_limit=body.slow_query_limit,
        )

        # Send to Slack if requested (Bot Token or Webhook)
        slack_sent = False
        if body.send_slack:
            from app.services.slack import send_slack_message

            slack_msg = format_slack_report(report)
            slack_sent = await send_slack_message(slack_msg)

        return DBAReportResponse(
            instance_name=inst.name,
            period=body.period,
            generated_at=report["generated_at"],
            metrics_summary=report["metrics_summary"],
            incident_count=report["incident_count"],
            slow_queries=report["slow_queries"],
            schema_changes_count=report["schema_changes_count"],
            ai_analysis=report["ai_analysis"],
            slack_sent=slack_sent,
        )
    finally:
        if pool:
            await pool.close()

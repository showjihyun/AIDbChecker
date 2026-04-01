# Spec: FR-AI-005, FS-AI-005
"""AIGC Report API — generate and retrieve AI-powered database health reports.

POST /reports/generate — Generate a new report via LLM analysis.
GET  /reports          — List generated reports (stub for Phase 2 storage).
GET  /reports/{id}     — Retrieve a specific report (stub for Phase 2 storage).
"""

import io
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

    report_id: UUID | None = None  # Spec: FS-AI-REPORT-002 AC-1
    instance_name: str
    period: str
    generated_at: str
    metrics_summary: dict
    incident_count: int
    slow_queries: list[dict]
    schema_changes_count: int
    ai_analysis: str
    slack_sent: bool = False


class DBAReportSummary(BaseModel):
    """DBA Report list item. Spec: FS-AI-REPORT-002 §3.1"""

    id: UUID
    instance_name: str
    period: str
    start_at: str
    end_at: str
    incident_count: int
    slow_query_count: int
    slack_sent: bool
    created_at: str


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

        # Spec: FS-AI-REPORT-002 AC-1 — persist to DB
        from datetime import datetime as dt

        from app.models.dba_report import DBAReport

        db_report = DBAReport(
            instance_id=inst.id,
            instance_name=inst.name,
            period=body.period,
            start_at=dt.fromisoformat(report["start"]),
            end_at=dt.fromisoformat(report["end"]),
            report_data=report,
            ai_analysis=report["ai_analysis"],
            incident_count=report["incident_count"],
            slow_query_count=len(report["slow_queries"]),
            slack_sent=slack_sent,
        )
        session.add(db_report)
        await session.commit()
        await session.refresh(db_report)

        return DBAReportResponse(
            report_id=db_report.id,
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


# ---------------------------------------------------------------------------
# DBA Report List / Detail / PDF — Spec: FS-AI-REPORT-002
# ---------------------------------------------------------------------------


@router.get(
    "/reports/dba/list",
    response_model=dict,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="List saved DBA reports",
)
async def list_dba_reports(
    instance_id: UUID | None = None,
    period: str | None = None,
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Spec: FS-AI-REPORT-002 AC-2 — list persisted DBA reports."""
    from sqlalchemy import func, select

    from app.models.dba_report import DBAReport

    stmt = select(DBAReport).order_by(DBAReport.created_at.desc())
    count_stmt = select(func.count(DBAReport.id))

    if instance_id:
        stmt = stmt.where(DBAReport.instance_id == instance_id)
        count_stmt = count_stmt.where(DBAReport.instance_id == instance_id)
    if period:
        stmt = stmt.where(DBAReport.period == period)
        count_stmt = count_stmt.where(DBAReport.period == period)

    total = (await session.execute(count_stmt)).scalar_one()
    result = await session.execute(stmt.offset(offset).limit(limit))

    items = [
        DBAReportSummary(
            id=r.id,
            instance_name=r.instance_name,
            period=r.period,
            start_at=r.start_at.isoformat() if r.start_at else "",
            end_at=r.end_at.isoformat() if r.end_at else "",
            incident_count=r.incident_count,
            slow_query_count=r.slow_query_count,
            slack_sent=r.slack_sent,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in result.scalars().all()
    ]

    return {"items": [i.model_dump() for i in items], "total": total}


@router.get(
    "/reports/dba/{report_id}",
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Get DBA report detail",
)
async def get_dba_report(
    report_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Spec: FS-AI-REPORT-002 AC-3 — full report JSON."""
    from sqlalchemy import select

    from app.models.dba_report import DBAReport

    stmt = select(DBAReport).where(DBAReport.id == report_id)
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return report.report_data


@router.get(
    "/reports/dba/{report_id}/pdf",
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Download DBA report as PDF",
)
async def download_dba_report_pdf(
    report_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Spec: FS-AI-REPORT-002 AC-4 — PDF download."""
    from fastapi.responses import StreamingResponse
    from sqlalchemy import select

    from app.models.dba_report import DBAReport
    from app.services.pdf_report import generate_pdf

    stmt = select(DBAReport).where(DBAReport.id == report_id)
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    pdf_bytes = generate_pdf(report.report_data)
    filename = f"neuraldb-{report.period}-{report.instance_name}-{report.created_at.strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

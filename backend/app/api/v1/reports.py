# Spec: FR-AI-005, FS-AI-005
"""AIGC Report API — generate and retrieve AI-powered database health reports.

POST /reports/generate — Generate a new report via LLM analysis.
GET  /reports          — List generated reports (stub for Phase 2 storage).
GET  /reports/{id}     — Retrieve a specific report (stub for Phase 2 storage).
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
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

    if body.period == "custom" and body.period_start >= body.period_end:
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

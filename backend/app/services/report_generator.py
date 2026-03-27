# Spec: FR-AI-005, FS-AI-005
"""AIGC Report Generator — LLM-powered database health report generation.

Collects metrics, incidents, ASH, schema changes, and baselines,
then synthesizes a structured report via LLM.

Phase 2: On-demand + scheduled (weekly) reports.
Phase 3: Incident post-mortem reports.
"""

import json
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.active_session import ActiveSession
from app.models.baseline import Baseline
from app.models.db_instance import DBInstance
from app.models.incident import Incident
from app.models.metric import MetricSample
from app.models.schema_change import SchemaChange
from app.schemas.report import (
    Recommendation,
    ReportFormat,
    ReportGenerateResponse,
    ReportSection,
    ReportType,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Spec: FS-AI-005 Section 4.2 — LLM prompts
# ---------------------------------------------------------------------------

_REPORT_SYSTEM_PROMPT = """You are a senior DBA writing a database health report.

Analyze the provided metrics, incidents, and session data to produce a structured report.

Rules:
- Be specific with numbers and timestamps
- Compare current values against baselines when available
- Prioritize actionable recommendations
- Use {language} language for ALL text content (title, summary, sections, recommendations)
- Rate each section severity: "good", "warning", or "critical"
- Provide a confidence score (0.0-1.0) for the overall analysis
- Generate at least 5 sections and 1-3 recommendations

Output ONLY valid JSON. No markdown fences."""

_REPORT_USER_PROMPT = """Generate a {report_type} report for {instance_desc}.
Period: {period_start} to {period_end}

=== Metric Summary (aggregated) ===
{metric_summary}

=== Incidents ({incident_count} total) ===
{incidents_text}

=== ASH Top Wait Events ===
{ash_summary}

=== Schema Changes ===
{schema_changes}

=== Baseline Comparison ===
{baseline_comparison}

{custom_section}

Respond ONLY with this JSON structure:
{{
  "title": "<report title>",
  "executive_summary": "<1-3 sentence summary>",
  "sections": [
    {{
      "title": "<section title>",
      "content": "<markdown body with specific numbers>",
      "severity": "<good|warning|critical>",
      "metrics": {{"key": "value"}}
    }}
  ],
  "recommendations": [
    {{
      "priority": "<high|medium|low>",
      "title": "<short title>",
      "description": "<why this matters>",
      "action": "<executable SQL or config command or null>",
      "confidence": 0.85
    }}
  ],
  "confidence": 0.85
}}"""


# ---------------------------------------------------------------------------
# Data gathering helpers
# ---------------------------------------------------------------------------


async def _fetch_metric_summary(
    session: AsyncSession,
    instance_id: UUID | None,
    start: datetime,
    end: datetime,
) -> str:
    """Fetch aggregated metric statistics for the report period."""
    # Spec: FS-AI-005 Section 4.1
    filters = [
        MetricSample.sampled_at >= start,
        MetricSample.sampled_at <= end,
    ]
    if instance_id:
        filters.append(MetricSample.instance_id == instance_id)

    stmt = (
        select(
            MetricSample.instance_id,
            func.count().label("sample_count"),
        )
        .where(*filters)
        .group_by(MetricSample.instance_id)
    )
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        return "No metric data available for this period."

    # Fetch latest metrics JSONB for summary
    latest_stmt = (
        select(MetricSample.instance_id, MetricSample.metrics)
        .where(*filters)
        .order_by(MetricSample.sampled_at.desc())
        .limit(1)
    )
    latest = await session.execute(latest_stmt)
    latest_row = latest.first()

    lines = [f"Total samples: {sum(r.sample_count for r in rows)}"]
    if latest_row and latest_row.metrics:
        m = latest_row.metrics
        lines.append(
            f"Latest snapshot: CPU={m.get('cpu_usage', 'N/A')}%, "
            f"Memory={m.get('memory_usage', 'N/A')}%, "
            f"Connections={m.get('active_connections', 'N/A')}, "
            f"TPS={m.get('tps', 'N/A')}, "
            f"BufferHit={m.get('buffer_hit_ratio', 'N/A')}%"
        )
    return "\n".join(lines)


async def _fetch_incidents(
    session: AsyncSession,
    instance_id: UUID | None,
    start: datetime,
    end: datetime,
) -> tuple[int, str]:
    """Fetch incidents for the report period."""
    filters = [
        Incident.detected_at >= start,
        Incident.detected_at <= end,
    ]
    if instance_id:
        filters.append(Incident.instance_id == instance_id)

    stmt = select(Incident).where(*filters).order_by(Incident.detected_at.desc()).limit(20)
    result = await session.execute(stmt)
    incidents = result.scalars().all()

    if not incidents:
        return 0, "No incidents during this period."

    lines = []
    for inc in incidents:
        resolved = "Resolved" if inc.resolved_at else "Open"
        lines.append(
            f"- [{inc.severity}] {inc.title} ({inc.detected_at:%Y-%m-%d %H:%M}) — {resolved}"
        )
    return len(incidents), "\n".join(lines)


async def _fetch_ash_summary(
    session: AsyncSession,
    instance_id: UUID | None,
    start: datetime,
    end: datetime,
) -> str:
    """Fetch ASH wait event summary."""
    filters = [
        ActiveSession.sampled_at >= start,
        ActiveSession.sampled_at <= end,
    ]
    if instance_id:
        filters.append(ActiveSession.instance_id == instance_id)

    stmt = (
        select(
            ActiveSession.wait_event_type,
            func.count().label("cnt"),
        )
        .where(*filters)
        .group_by(ActiveSession.wait_event_type)
        .order_by(text("cnt DESC"))
        .limit(10)
    )
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        return "No ASH data available."

    total = sum(r.cnt for r in rows)
    lines = []
    for r in rows:
        pct = (r.cnt / total * 100) if total > 0 else 0
        event_type = r.wait_event_type or "CPU (no wait)"
        lines.append(f"- {event_type}: {r.cnt} samples ({pct:.1f}%)")
    return "\n".join(lines)


async def _fetch_schema_changes(
    session: AsyncSession,
    instance_id: UUID | None,
    start: datetime,
    end: datetime,
) -> str:
    """Fetch DDL changes during the period."""
    filters = [
        SchemaChange.detected_at >= start,
        SchemaChange.detected_at <= end,
    ]
    if instance_id:
        filters.append(SchemaChange.instance_id == instance_id)

    stmt = select(SchemaChange).where(*filters).order_by(SchemaChange.detected_at.desc()).limit(10)
    result = await session.execute(stmt)
    changes = result.scalars().all()

    if not changes:
        return "No schema changes during this period."

    lines = []
    for ch in changes:
        lines.append(
            f"- {ch.change_type} {ch.object_type} {ch.object_name} "
            f"({ch.detected_at:%Y-%m-%d %H:%M})"
        )
    return "\n".join(lines)


async def _fetch_baseline_comparison(
    session: AsyncSession,
    instance_id: UUID | None,
) -> str:
    """Fetch current baselines for comparison."""
    filters = [Baseline.is_active.is_(True)]
    if instance_id:
        filters.append(Baseline.instance_id == instance_id)

    stmt = select(Baseline).where(*filters).limit(20)
    result = await session.execute(stmt)
    baselines = result.scalars().all()

    if not baselines:
        return "No baselines trained yet."

    lines = []
    for bl in baselines:
        lines.append(
            f"- {bl.metric_type} [{bl.time_bucket}]: "
            f"normal={bl.normal_min:.1f}~{bl.normal_max:.1f}, "
            f"mean={bl.mean:.1f}, stddev={bl.stddev:.1f}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Spec: FS-AI-005 Section 4.3 — main generation pipeline
# ---------------------------------------------------------------------------


def _get_llm():
    """Get LLM instance via unified LLMProviderManager.

    Spec: FS-AI-LLM-001 — AC-6
    """
    from app.services.llm_provider import get_llm_manager

    return get_llm_manager().get_llm(
        temperature=0.3,  # slightly creative for report writing
        max_tokens=3000,
        request_timeout=60,
    )


def _parse_llm_response(raw: str) -> dict:
    """Parse LLM JSON response, stripping markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


def _resolve_period(
    period: str,
    period_start: datetime | None,
    period_end: datetime | None,
) -> tuple[datetime, datetime]:
    """Resolve period shorthand to start/end datetimes."""
    now = datetime.now(UTC)
    if period == "custom" and period_start and period_end:
        return period_start, period_end

    days_map = {"1d": 1, "7d": 7, "30d": 30}
    days = days_map.get(period, 7)
    return now - timedelta(days=days), now


async def generate_report(
    session: AsyncSession,
    *,
    instance_id: UUID | None,
    period: str = "7d",
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    report_type: ReportType = ReportType.HEALTH,
    report_format: ReportFormat = ReportFormat.HTML,
    language: str = "ko",
    custom_prompt: str | None = None,
) -> ReportGenerateResponse:
    """Generate an AIGC database health report.

    Spec: FS-AI-005 — main entry point.
    Pipeline: validate → gather data → build prompt → LLM call → parse → respond
    """
    start_time = time.monotonic()
    report_id = uuid4()

    # 1. Resolve period
    p_start, p_end = _resolve_period(period, period_start, period_end)

    # 2. Resolve instance description
    instance_desc = "all monitored instances"
    if instance_id:
        inst_stmt = select(DBInstance.name).where(DBInstance.id == instance_id)
        inst_result = await session.execute(inst_stmt)
        inst_name = inst_result.scalar()
        instance_desc = f"instance '{inst_name or instance_id}'"

    # 3. Gather data (Spec: FS-AI-005 Section 4.1)
    metric_summary = await _fetch_metric_summary(session, instance_id, p_start, p_end)
    incident_count, incidents_text = await _fetch_incidents(session, instance_id, p_start, p_end)
    ash_summary = await _fetch_ash_summary(session, instance_id, p_start, p_end)
    schema_changes = await _fetch_schema_changes(session, instance_id, p_start, p_end)
    baseline_comparison = await _fetch_baseline_comparison(session, instance_id)

    custom_section = ""
    if custom_prompt:
        custom_section = f"\n=== Additional Focus ===\n{custom_prompt}"

    # 4. Build prompt
    system_msg = _REPORT_SYSTEM_PROMPT.format(language=language)
    user_msg = _REPORT_USER_PROMPT.format(
        report_type=report_type.value,
        instance_desc=instance_desc,
        period_start=p_start.strftime("%Y-%m-%d %H:%M UTC"),
        period_end=p_end.strftime("%Y-%m-%d %H:%M UTC"),
        metric_summary=metric_summary,
        incident_count=incident_count,
        incidents_text=incidents_text,
        ash_summary=ash_summary,
        schema_changes=schema_changes,
        baseline_comparison=baseline_comparison,
        custom_section=custom_section,
    )

    # 5. LLM call
    llm = _get_llm()
    model_name = getattr(llm, "model_name", None) or getattr(llm, "model", "unknown")
    tokens_used = 0

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [SystemMessage(content=system_msg), HumanMessage(content=user_msg)]
        response = await llm.ainvoke(messages)
        raw_text = response.content

        # Token tracking
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens_used = response.usage_metadata.get("total_tokens", 0)

        parsed = _parse_llm_response(raw_text)

    except Exception as exc:
        logger.error("report.llm_failed", error=str(exc), report_id=str(report_id))
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        return ReportGenerateResponse(
            report_id=report_id,
            instance_id=instance_id,
            report_type=report_type,
            period=period,
            title="Report Generation Failed",
            executive_summary=f"LLM analysis failed: {exc}",
            sections=[],
            recommendations=[],
            status="failed",
            format=report_format,
            generated_at=datetime.now(UTC),
            generation_time_ms=elapsed_ms,
            ai_model=str(model_name),
            tokens_used=tokens_used,
            confidence=0.0,
        )

    # 6. Parse response into typed schema
    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    sections = []
    for s in parsed.get("sections", []):
        sections.append(
            ReportSection(
                title=s.get("title", "Untitled"),
                content=s.get("content", ""),
                severity=s.get("severity"),
                metrics=s.get("metrics"),
                chart_data=s.get("chart_data"),
            )
        )

    recommendations = []
    for r in parsed.get("recommendations", []):
        recommendations.append(
            Recommendation(
                priority=r.get("priority", "medium"),
                title=r.get("title", ""),
                description=r.get("description", ""),
                action=r.get("action"),
                confidence=r.get("confidence", 0.5),
            )
        )

    confidence = parsed.get("confidence", 0.5)

    logger.info(
        "report.generated",
        report_id=str(report_id),
        instance_id=str(instance_id),
        sections=len(sections),
        recommendations=len(recommendations),
        confidence=confidence,
        elapsed_ms=elapsed_ms,
        tokens=tokens_used,
    )

    # Spec: FS-ADMIN-004 — AI Decision Log
    try:
        from app.utils.ai_logger import build_ai_details, create_ai_decision_log

        details = build_ai_details(
            ai_model=str(model_name),
            inference_time_ms=elapsed_ms,
            decision="report_generated",
            confidence=confidence,
            total_tokens=tokens_used,
            output_summary={
                "title": parsed.get("title", ""),
                "sections_count": len(sections),
                "recommendations_count": len(recommendations),
            },
        )
        await create_ai_decision_log(
            session,
            resource_type="aigc_report",
            resource_id=str(report_id),
            details=details,
        )
    except Exception:
        logger.debug("report.ai_decision_log_skipped")

    return ReportGenerateResponse(
        report_id=report_id,
        instance_id=instance_id,
        report_type=report_type,
        period=period,
        title=parsed.get("title", "DB Health Report"),
        executive_summary=parsed.get("executive_summary", ""),
        sections=sections,
        recommendations=recommendations,
        status="completed",
        format=report_format,
        generated_at=datetime.now(UTC),
        generation_time_ms=elapsed_ms,
        ai_model=str(model_name),
        tokens_used=tokens_used,
        confidence=confidence,
    )

# Spec: FS-AI-REPORT-001
"""DBA Report Generator — Daily/Weekly/Monthly DB operation reports.

Collects metrics, incidents, slow queries, schema changes, and generates
a Korean-language DBA report with AI analysis summary.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.active_session import ActiveSession
from app.models.incident import Incident
from app.models.metric import MetricSample
from app.models.schema_change import SchemaChange

logger = structlog.get_logger(__name__)

PERIOD_HOURS = {"daily": 24, "weekly": 168, "monthly": 720}


# ---------------------------------------------------------------------------
# Data Collection
# ---------------------------------------------------------------------------


async def _fetch_metrics_summary(session: AsyncSession, instance_id: UUID, since: datetime) -> dict:
    """Aggregate metrics for the period."""
    stmt = select(
        func.avg(MetricSample.metrics["cpu_usage"].as_float()).label("cpu_avg"),
        func.max(MetricSample.metrics["cpu_usage"].as_float()).label("cpu_max"),
        func.avg(MetricSample.metrics["memory_usage"].as_float()).label("mem_avg"),
        func.max(MetricSample.metrics["memory_usage"].as_float()).label("mem_max"),
        func.avg(MetricSample.metrics["active_connections"].as_float()).label("conn_avg"),
        func.max(MetricSample.metrics["active_connections"].as_float()).label("conn_max"),
        func.avg(MetricSample.metrics["tps"].as_float()).label("tps_avg"),
        func.max(MetricSample.metrics["tps"].as_float()).label("tps_max"),
        func.avg(MetricSample.metrics["buffer_hit_ratio"].as_float()).label("bhr_avg"),
    ).where(
        MetricSample.instance_id == instance_id,
        MetricSample.sampled_at >= since,
    )
    row = (await session.execute(stmt)).one_or_none()
    if not row or row.cpu_avg is None:
        return {
            "cpu": {"avg": 0, "max": 0},
            "memory": {"avg": 0, "max": 0},
            "connections": {"avg": 0, "max": 0},
            "tps": {"avg": 0, "max": 0},
            "buffer_hit_ratio": {"avg": 0},
        }
    return {
        "cpu": {"avg": round(float(row.cpu_avg), 1), "max": round(float(row.cpu_max), 1)},
        "memory": {"avg": round(float(row.mem_avg), 1), "max": round(float(row.mem_max), 1)},
        "connections": {"avg": round(float(row.conn_avg)), "max": round(float(row.conn_max))},
        "tps": {"avg": round(float(row.tps_avg)), "max": round(float(row.tps_max))},
        "buffer_hit_ratio": {"avg": round(float(row.bhr_avg), 1)},
    }


async def _fetch_incidents(session: AsyncSession, instance_id: UUID, since: datetime) -> list[dict]:
    """Fetch incidents for the period."""
    stmt = (
        select(Incident)
        .where(Incident.instance_id == instance_id, Incident.detected_at >= since)
        .order_by(Incident.detected_at.desc())
        .limit(50)
    )
    result = await session.execute(stmt)
    incidents = []
    for inc in result.scalars().all():
        incidents.append(
            {
                "severity": inc.severity,
                "title": inc.title,
                "status": inc.status,
                "detected_at": inc.detected_at.isoformat() if inc.detected_at else "",
            }
        )
    return incidents


async def _fetch_slow_queries(pool, limit: int = 10) -> list[dict]:
    """Fetch slow queries from pg_stat_statements (target DB)."""
    if pool is None:
        return []

    sql = """
        SELECT
            queryid,
            LEFT(query, 500) AS query,
            calls,
            round(mean_exec_time::numeric, 2) AS mean_exec_time_ms,
            round(total_exec_time::numeric, 2) AS total_exec_time_ms,
            rows,
            shared_blks_hit,
            shared_blks_read
        FROM pg_stat_statements
        WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
          AND calls > 0
        ORDER BY mean_exec_time DESC
        LIMIT $1
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, limit)
            return [
                {
                    "rank": i + 1,
                    "query_hash": r["queryid"],
                    "query": r["query"],
                    "calls": r["calls"],
                    "mean_exec_time_ms": float(r["mean_exec_time_ms"]),
                    "total_exec_time_ms": float(r["total_exec_time_ms"]),
                    "rows_returned": r["rows"],
                    "shared_blks_hit": r["shared_blks_hit"],
                    "shared_blks_read": r["shared_blks_read"],
                }
                for i, r in enumerate(rows)
            ]
    except Exception as exc:
        logger.warning("dba_report.slow_queries_failed", error=str(exc))
        return []


async def _fetch_schema_changes(
    session: AsyncSession, instance_id: UUID, since: datetime
) -> list[dict]:
    """Fetch DDL changes for the period."""
    stmt = (
        select(SchemaChange)
        .where(SchemaChange.instance_id == instance_id, SchemaChange.detected_at >= since)
        .order_by(SchemaChange.detected_at.desc())
        .limit(20)
    )
    result = await session.execute(stmt)
    return [
        {
            "change_type": sc.change_type,
            "object_name": sc.object_name,
            "detected_at": sc.detected_at.isoformat() if sc.detected_at else "",
        }
        for sc in result.scalars().all()
    ]


async def _fetch_ash_summary(
    session: AsyncSession, instance_id: UUID, since: datetime
) -> dict:
    """Fetch ASH wait event breakdown + top sessions for the period."""
    # Wait event breakdown
    stmt_wait = (
        select(
            ActiveSession.wait_event_type,
            func.count().label("cnt"),
        )
        .where(
            ActiveSession.instance_id == instance_id,
            ActiveSession.sampled_at >= since,
            ActiveSession.wait_event_type.isnot(None),
        )
        .group_by(ActiveSession.wait_event_type)
        .order_by(func.count().desc())
        .limit(10)
    )
    wait_result = await session.execute(stmt_wait)
    wait_breakdown = [
        {"wait_event_type": r.wait_event_type, "count": r.cnt}
        for r in wait_result.all()
    ]

    total_samples = sum(w["count"] for w in wait_breakdown)
    for w in wait_breakdown:
        w["percentage"] = round(w["count"] / max(total_samples, 1) * 100, 1)

    # Top wait events (detail)
    stmt_events = (
        select(
            ActiveSession.wait_event_type,
            ActiveSession.wait_event,
            func.count().label("cnt"),
        )
        .where(
            ActiveSession.instance_id == instance_id,
            ActiveSession.sampled_at >= since,
            ActiveSession.wait_event.isnot(None),
        )
        .group_by(ActiveSession.wait_event_type, ActiveSession.wait_event)
        .order_by(func.count().desc())
        .limit(10)
    )
    event_result = await session.execute(stmt_events)
    top_events = [
        {
            "wait_event_type": r.wait_event_type,
            "wait_event": r.wait_event,
            "count": r.cnt,
        }
        for r in event_result.all()
    ]

    # Active session state breakdown
    stmt_state = (
        select(
            ActiveSession.state,
            func.count().label("cnt"),
        )
        .where(
            ActiveSession.instance_id == instance_id,
            ActiveSession.sampled_at >= since,
        )
        .group_by(ActiveSession.state)
        .order_by(func.count().desc())
    )
    state_result = await session.execute(stmt_state)
    state_breakdown = [
        {"state": r.state, "count": r.cnt}
        for r in state_result.all()
    ]

    return {
        "total_samples": total_samples,
        "wait_breakdown": wait_breakdown,
        "top_events": top_events,
        "state_breakdown": state_breakdown,
    }


# ---------------------------------------------------------------------------
# AI Analysis
# ---------------------------------------------------------------------------


async def _generate_ai_summary(
    metrics: dict,
    incidents: list[dict],
    slow_queries: list[dict],
    schema_changes: list[dict],
    ash_summary: dict,
    period: str,
) -> str:
    """Generate Korean AI analysis summary using LLM."""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        from app.services.llm_provider import LLMProviderManager

        mgr = LLMProviderManager()
        llm = mgr.get_llm(temperature=0.3, max_tokens=1000)

        top_queries = "\n".join(
            f"  #{q['rank']}. {q['query'][:80]}... — {q['mean_exec_time_ms']}ms × {q['calls']}회"
            for q in slow_queries[:5]
        )
        inc_summary = f"Critical {sum(1 for i in incidents if i['severity'] == 'critical')}건, "
        inc_summary += f"Warning {sum(1 for i in incidents if i['severity'] == 'warning')}건"

        # ASH summary for prompt
        ash_wait = "\n".join(
            f"  {w['wait_event_type']}: {w['count']}건 ({w['percentage']}%)"
            for w in ash_summary.get("wait_breakdown", [])[:5]
        )
        ash_states = ", ".join(
            f"{s['state']}={s['count']}"
            for s in ash_summary.get("state_breakdown", [])[:5]
        )
        inc_details = "\n".join(
            f"  [{i['severity'].upper()}] {i['title']}"
            for i in incidents[:5]
        )

        prompt = (
            f"기간: {period} | 인시던트: {len(incidents)}건 ({inc_summary})\n"
            f"CPU: avg {metrics['cpu']['avg']}%, max {metrics['cpu']['max']}%\n"
            f"TPS: avg {metrics['tps']['avg']}, max {metrics['tps']['max']}\n"
            f"커넥션: avg {metrics['connections']['avg']}, max {metrics['connections']['max']}\n"
            f"버퍼히트율: {metrics['buffer_hit_ratio']['avg']}%\n\n"
            f"인시던트 상세:\n{inc_details or '  없음'}\n\n"
            f"ASH Wait Event 분석 (총 {ash_summary.get('total_samples', 0)}건):\n{ash_wait or '  없음'}\n"
            f"세션 상태 분포: {ash_states or '없음'}\n\n"
            f"Slow Query Top 5:\n{top_queries or '  없음'}\n"
            f"스키마 변경: {len(schema_changes)}건\n\n"
            f"위 데이터를 바탕으로 DBA를 위한 핵심 분석 요약을 작성하세요.\n"
            f"포함 내용:\n"
            f"1. 주요 발견사항 (인시던트, Wait Event 이상 포함)\n"
            f"2. ASH 기반 성능 병목 분석\n"
            f"3. 우선 조치 권장사항"
        )

        response = await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "당신은 PostgreSQL DBA 리포트 작성 전문가입니다. "
                        "반드시 한국어로 답변하세요. 간결하고 실용적인 분석을 제공하세요."
                    )
                ),
                HumanMessage(content=prompt),
            ]
        )
        return response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.warning("dba_report.ai_summary_failed", error=str(exc))
        return f"AI 분석 요약 생성 실패: {exc}"


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------


async def generate_dba_report(
    session: AsyncSession,
    instance_id: UUID,
    instance_name: str,
    period: Literal["daily", "weekly", "monthly"] = "daily",
    pool=None,
    slow_query_limit: int = 10,
) -> dict:
    """Generate a comprehensive DBA report.

    Spec: FS-AI-REPORT-001 §3
    """
    hours = PERIOD_HOURS[period]
    since = datetime.utcnow() - timedelta(hours=hours)

    # Collect all data
    metrics = await _fetch_metrics_summary(session, instance_id, since)
    incidents = await _fetch_incidents(session, instance_id, since)
    slow_queries = await _fetch_slow_queries(pool, limit=slow_query_limit)
    schema_changes = await _fetch_schema_changes(session, instance_id, since)
    ash_summary = await _fetch_ash_summary(session, instance_id, since)

    # AI analysis (includes ASH data)
    ai_analysis = await _generate_ai_summary(
        metrics, incidents, slow_queries, schema_changes, ash_summary, period
    )

    # Build report
    report = {
        "instance_id": str(instance_id),
        "instance_name": instance_name,
        "period": period,
        "start": since.isoformat(),
        "end": datetime.utcnow().isoformat(),
        "generated_at": datetime.utcnow().isoformat(),
        "metrics_summary": metrics,
        "incident_count": len(incidents),
        "incidents": incidents[:10],
        "slow_queries": slow_queries,
        "schema_changes_count": len(schema_changes),
        "schema_changes": schema_changes,
        "ash_summary": ash_summary,
        "ai_analysis": ai_analysis,
    }

    logger.info(
        "dba_report.generated",
        instance_id=str(instance_id),
        period=period,
        incidents=len(incidents),
        slow_queries=len(slow_queries),
    )

    return report


# ---------------------------------------------------------------------------
# Slack Formatting
# ---------------------------------------------------------------------------


def format_slack_report(report: dict) -> str:
    """Format DBA report for Slack.

    Spec: FS-AI-REPORT-001 §6
    """
    m = report["metrics_summary"]
    period_label = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}
    p = period_label.get(report["period"], report["period"])

    # Status emoji for metrics
    cpu_icon = "🔴" if m["cpu"]["max"] > 90 else "🟡" if m["cpu"]["max"] > 70 else "🟢"
    conn_icon = "🔴" if m["connections"]["max"] > 180 else "🟢"

    # Incidents summary
    incidents = report.get("incidents", [])
    crit = sum(1 for i in incidents if i["severity"] == "critical")
    warn = sum(1 for i in incidents if i["severity"] == "warning")
    resolved = sum(1 for i in incidents if i["status"] == "resolved")
    inc_total = report["incident_count"]

    # Slow queries top 3
    sq_lines = []
    for q in report.get("slow_queries", [])[:3]:
        sq_lines.append(
            f"  {q['rank']}. `{q['query'][:60]}...` — {q['mean_exec_time_ms']:.0f}ms × {q['calls']}회"
        )
    sq_text = "\n".join(sq_lines) if sq_lines else "  (없음)"

    # Incidents detail (top 5)
    inc_lines = []
    for inc in incidents[:5]:
        sev = inc.get("severity", "").upper()
        sev_icon = {"CRITICAL": "🔴", "WARNING": "🟡", "NOTICE": "🔵"}.get(sev, "⚪")
        inc_lines.append(f"  {sev_icon} [{sev}] {inc.get('title', '')[:60]}")
    inc_text = "\n".join(inc_lines) if inc_lines else "  (없음)"

    # ASH summary
    ash = report.get("ash_summary", {})
    ash_total = ash.get("total_samples", 0)
    ash_lines = []
    for w in ash.get("wait_breakdown", [])[:3]:
        ash_lines.append(f"  {w['wait_event_type']}: {w['count']}건 ({w['percentage']}%)")
    ash_text = "\n".join(ash_lines) if ash_lines else "  (데이터 없음)"

    msg = (
        f"📊 *NeuralDB {p} DBA 리포트* — {report['instance_name']}\n"
        f"기간: {report['start'][:10]} ~ {report['end'][:10]}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 핵심 지표: {cpu_icon} CPU {m['cpu']['avg']}%(max {m['cpu']['max']}%) | "
        f"TPS {m['tps']['avg']:,} | {conn_icon} 커넥션 {m['connections']['avg']}\n"
        f"🚨 인시던트: {inc_total}건 (Critical {crit}, Warning {warn}) | "
        f"해결률 {resolved}/{inc_total} ({round(resolved / max(inc_total, 1) * 100)}%)\n"
        f"{inc_text}\n"
        f"⏱️ ASH 분석 ({ash_total} samples):\n{ash_text}\n"
        f"🐌 Slow Query Top 3:\n{sq_text}\n"
        f"🔄 스키마 변경: {report['schema_changes_count']}건\n"
        f"🤖 AI 요약: {report['ai_analysis'][:300]}"
    )

    return msg

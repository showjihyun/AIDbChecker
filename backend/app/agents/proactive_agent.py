# Spec: FS-DBA-003
"""Proactive DBA Agent — autonomous DB health monitoring.

Runs on Celery Beat schedule:
- Quick Check (30min): KPI thresholds → auto-analyze if anomaly
- Deep Analysis (6h): Slow queries, index, bloat, vacuum
- Morning Report (daily 09:00): 24h summary to Slack

Self-Healing: L3+ instances → auto-execute via ExecutionEngine.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)

# Quick Check thresholds
THRESHOLDS = {
    "cpu_usage": 80.0,
    "connection_pct": 90.0,
    "deadlocks_per_sec": 0.0,
    "replication_lag_sec": 30.0,
    "long_query_sec": 300.0,
}


class ProactiveAgent:
    """Spec: FS-DBA-003 — Proactive DBA Agent."""

    async def quick_check(self, instance_id: UUID, session, pool) -> dict:
        """AC-1/2: 30-min quick health check.

        Checks KPI thresholds. If anomaly, triggers DBA Agent analysis.
        Returns check result with any findings.
        """
        start = time.monotonic()
        findings = []

        try:
            from app.services.kpi_calculator import KPICalculator

            kpis = await KPICalculator.compute_all_kpi(session, instance_id)
        except Exception as exc:
            logger.error("proactive.kpi_failed", error=str(exc))
            return {"status": "error", "error": str(exc)}

        # Check thresholds
        tps = kpis.get("throughput", {}).get("tps", {})
        conn = kpis.get("connection", {}).get("connection_usage_pct", {})
        deadlocks = kpis.get("lock", {}).get("deadlocks_per_sec", {})
        lag = kpis.get("storage", {}).get("replication_lag_sec", {})

        conn_val = conn.get("value")
        if conn_val is not None and conn_val > THRESHOLDS["connection_pct"]:
            findings.append({
                "metric": "connection_usage_pct",
                "value": conn_val,
                "threshold": THRESHOLDS["connection_pct"],
                "action": "analyze",
                "message": f"Connection usage {conn_val}% exceeds {THRESHOLDS['connection_pct']}%",
            })

        deadlock_val = deadlocks.get("value")
        if deadlock_val is not None and deadlock_val > THRESHOLDS["deadlocks_per_sec"]:
            findings.append({
                "metric": "deadlocks_per_sec",
                "value": deadlock_val,
                "threshold": THRESHOLDS["deadlocks_per_sec"],
                "action": "diagnose",
                "message": f"Deadlocks detected: {deadlock_val}/sec",
            })

        lag_val = lag.get("value")
        if lag_val is not None and lag_val > THRESHOLDS["replication_lag_sec"]:
            findings.append({
                "metric": "replication_lag_sec",
                "value": lag_val,
                "threshold": THRESHOLDS["replication_lag_sec"],
                "action": "alert",
                "message": f"Replication lag {lag_val}s exceeds {THRESHOLDS['replication_lag_sec']}s",
            })

        elapsed = int((time.monotonic() - start) * 1000)

        result = {
            "status": "anomaly" if findings else "healthy",
            "instance_id": str(instance_id),
            "findings": findings,
            "check_time_ms": elapsed,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        if findings:
            logger.warning(
                "proactive.anomaly_detected",
                instance_id=str(instance_id),
                findings=len(findings),
            )
        else:
            logger.info(
                "proactive.healthy",
                instance_id=str(instance_id),
                check_time_ms=elapsed,
            )

        return result

    async def deep_analysis(self, instance_id: UUID, session, pool) -> dict:
        """AC-4: 6-hour deep analysis — slow queries, index, bloat.

        Uses DBA Agent tools directly for analysis.
        Returns structured results with suggested actions.
        """
        results = {}

        try:
            from app.agents.tools.db_tools import (
                index_recommendations,
                slow_queries,
                table_bloat,
            )

            if pool:
                results["slow_queries"] = await slow_queries(pool, top_n=10)
                results["index_recommendations"] = await index_recommendations(pool)
                results["table_bloat"] = await table_bloat(pool)
        except Exception as exc:
            logger.error("proactive.deep_analysis_failed", error=str(exc))
            results["error"] = str(exc)

        results["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        results["instance_id"] = str(instance_id)

        return results

    async def morning_report(self, instance_id: UUID, session) -> dict:
        """AC-8: Daily morning report — 24h summary.

        Collects: incidents, metric trends, AI recommendations.
        Does NOT use LLM — pure data aggregation.
        """
        from sqlalchemy import func, select, text

        report = {
            "instance_id": str(instance_id),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": "24h",
        }

        try:
            # Incident count (last 24h)
            from app.models.incident import Incident

            stmt = select(func.count()).where(
                Incident.instance_id == instance_id,
                Incident.detected_at >= text("NOW() - INTERVAL '24 hours'"),
            )
            result = await session.execute(stmt)
            report["incidents_24h"] = result.scalar() or 0

            # Agent actions (last 24h)
            action_result = await session.execute(
                text(
                    "SELECT count(*) FROM agent_actions "
                    "WHERE instance_id = :iid AND created_at >= NOW() - INTERVAL '24 hours'"
                ),
                {"iid": instance_id},
            )
            report["agent_actions_24h"] = action_result.scalar() or 0

        except Exception as exc:
            logger.error("proactive.report_failed", error=str(exc))
            report["error"] = str(exc)

        return report

    def format_slack_alert(self, check_result: dict, instance_name: str) -> str:
        """AC-3: Format check result as Slack message."""
        status_emoji = "🔴" if check_result["status"] == "anomaly" else "🟢"
        lines = [
            f"{status_emoji} [NeuralDB Proactive] {instance_name}",
        ]

        for f in check_result.get("findings", []):
            lines.append(f"  - {f['message']}")

        if not check_result.get("findings"):
            lines.append("  All metrics within normal range.")

        return "\n".join(lines)

    def format_morning_report(self, report: dict, instance_name: str) -> str:
        """AC-9: Format morning report as Slack message."""
        return (
            f"📊 [NeuralDB Daily Report] {instance_name}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Incidents (24h): {report.get('incidents_24h', 0)}\n"
            f"Agent Actions (24h): {report.get('agent_actions_24h', 0)}\n"
            f"Generated: {report.get('generated_at', 'unknown')}"
        )

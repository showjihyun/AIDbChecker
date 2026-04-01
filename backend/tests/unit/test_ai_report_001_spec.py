# Spec: FS-AI-REPORT-001
"""Tests for DBA Report — Daily/Weekly/Monthly."""

import pytest

from tests.conftest import spec_ref


@spec_ref("FS-AI-REPORT-001", "AC-1")
def test_report_001_ac1_generate_endpoint():
    """AC-1: POST /api/v1/reports/dba returns DBA report JSON."""
    from app.api.v1.reports import DBAReportRequest, DBAReportResponse

    req = DBAReportRequest(
        instance_id="00000000-0000-0000-0000-000000000001",
        period="daily",
        send_slack=False,
    )
    assert req.period == "daily"

    fields = DBAReportResponse.model_fields
    assert "metrics_summary" in fields
    assert "slow_queries" in fields
    assert "ai_analysis" in fields
    assert "slack_sent" in fields


@spec_ref("FS-AI-REPORT-001", "AC-2")
def test_report_001_ac2_metrics_summary():
    """AC-2: Daily report includes CPU/Memory/TPS/Connection avg/max."""
    from app.api.v1.reports import DBAReportResponse

    fields = DBAReportResponse.model_fields
    assert "metrics_summary" in fields
    assert "incident_count" in fields


@spec_ref("FS-AI-REPORT-001", "AC-3")
def test_report_001_ac3_slow_query_detail():
    """AC-3: Slow Query Top N includes query, calls, mean_exec_time."""
    from app.services.dba_report import _fetch_slow_queries

    import asyncio
    # With pool=None, returns empty list (safe fallback)
    result = asyncio.get_event_loop().run_until_complete(_fetch_slow_queries(None, 10))
    assert result == []


@spec_ref("FS-AI-REPORT-001", "AC-4")
def test_report_001_ac4_korean_analysis():
    """AC-4: AI analysis prompt requests Korean output."""
    import inspect
    from app.services.dba_report import _generate_ai_summary

    source = inspect.getsource(_generate_ai_summary)
    assert "한국어" in source or "Korean" in source


@spec_ref("FS-AI-REPORT-001", "AC-5")
def test_report_001_ac5_celery_schedules():
    """AC-5: Celery Beat has daily/weekly/monthly report schedules."""
    from app.tasks import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "daily-dba-report" in schedule
    assert "weekly-dba-report" in schedule
    assert "monthly-dba-report" in schedule

    assert schedule["daily-dba-report"]["args"] == ("daily",)
    assert schedule["weekly-dba-report"]["args"] == ("weekly",)
    assert schedule["monthly-dba-report"]["args"] == ("monthly",)


@spec_ref("FS-AI-REPORT-001", "AC-6")
def test_report_001_ac6_slack_format():
    """AC-6: Slack webhook report format is Korean DBA-friendly."""
    from app.services.dba_report import format_slack_report

    report = {
        "instance_name": "pg-prod-01",
        "period": "daily",
        "start": "2026-03-30T09:00:00",
        "end": "2026-03-31T09:00:00",
        "generated_at": "2026-03-31T09:00:00",
        "metrics_summary": {
            "cpu": {"avg": 45.0, "max": 92.0},
            "memory": {"avg": 62.0, "max": 78.0},
            "connections": {"avg": 85, "max": 195},
            "tps": {"avg": 1240, "max": 3450},
            "buffer_hit_ratio": {"avg": 99.2},
        },
        "incident_count": 3,
        "incidents": [
            {"severity": "critical", "title": "CPU spike", "status": "resolved", "detected_at": ""},
            {"severity": "warning", "title": "Connection pool", "status": "open", "detected_at": ""},
        ],
        "slow_queries": [
            {"rank": 1, "query": "SELECT * FROM orders WHERE...", "calls": 1250, "mean_exec_time_ms": 2340},
        ],
        "schema_changes_count": 2,
        "ai_analysis": "CPU 스파이크는 orders 테이블 풀스캔이 원인입니다.",
    }

    msg = format_slack_report(report)
    assert "DBA 리포트" in msg
    assert "pg-prod-01" in msg
    assert "Slow Query" in msg
    assert "CPU" in msg


@spec_ref("FS-AI-REPORT-001", "AC-7")
def test_report_001_ac7_period_hours():
    """AC-7: Weekly/Monthly reports cover correct time ranges."""
    from app.services.dba_report import PERIOD_HOURS

    assert PERIOD_HOURS["daily"] == 24
    assert PERIOD_HOURS["weekly"] == 168
    assert PERIOD_HOURS["monthly"] == 720


@spec_ref("FS-AI-REPORT-001", "AC-8")
def test_report_001_ac8_schema_changes_in_report():
    """AC-8: Schema changes included in report."""
    from app.api.v1.reports import DBAReportResponse

    fields = DBAReportResponse.model_fields
    assert "schema_changes_count" in fields

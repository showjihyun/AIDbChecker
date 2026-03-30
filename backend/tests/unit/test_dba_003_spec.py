# Spec: FS-DBA-003
"""Tests for Proactive DBA Agent — 10 ACs."""

from uuid import uuid4

import pytest

from tests.conftest import spec_ref


@spec_ref("FS-DBA-003", "AC-1")
def test_dba_003_ac1_celery_beat_schedule():
    """FS-DBA-003 AC-1: Quick Check registered in Celery Beat."""
    from app.tasks import celery_app

    beat = celery_app.conf.beat_schedule
    assert "proactive-quick-check" in beat
    assert beat["proactive-quick-check"]["task"] == "proactive_quick_check"


@spec_ref("FS-DBA-003", "AC-2")
def test_dba_003_ac2_quick_check_exists():
    """FS-DBA-003 AC-2: ProactiveAgent.quick_check exists."""
    from app.agents.proactive_agent import ProactiveAgent

    agent = ProactiveAgent()
    assert hasattr(agent, "quick_check")


@spec_ref("FS-DBA-003", "AC-3")
def test_dba_003_ac3_slack_format():
    """FS-DBA-003 AC-3: Slack alert formatting."""
    from app.agents.proactive_agent import ProactiveAgent

    agent = ProactiveAgent()
    result = {
        "status": "anomaly",
        "findings": [{"message": "CPU 92%"}],
    }
    msg = agent.format_slack_alert(result, "pg-prod-01")
    assert "pg-prod-01" in msg
    assert "CPU 92%" in msg


@spec_ref("FS-DBA-003", "AC-4")
def test_dba_003_ac4_deep_analysis_exists():
    """FS-DBA-003 AC-4: Deep analysis method exists."""
    from app.agents.proactive_agent import ProactiveAgent

    agent = ProactiveAgent()
    assert hasattr(agent, "deep_analysis")


@spec_ref("FS-DBA-003", "AC-5")
def test_dba_003_ac5_thresholds_defined():
    """FS-DBA-003 AC-5: Check thresholds are defined."""
    from app.agents.proactive_agent import THRESHOLDS

    assert "cpu_usage" in THRESHOLDS
    assert "connection_pct" in THRESHOLDS
    assert "deadlocks_per_sec" in THRESHOLDS
    assert "replication_lag_sec" in THRESHOLDS


@spec_ref("FS-DBA-003", "AC-6")
def test_dba_003_ac6_celery_task_registered():
    """FS-DBA-003 AC-6: Proactive tasks in Celery include."""
    from app.tasks import celery_app

    includes = celery_app.conf.include or []
    assert "app.tasks.proactive" in includes


@spec_ref("FS-DBA-003", "AC-7")
def test_dba_003_ac7_deep_analysis_schedule():
    """FS-DBA-003 AC-7: Deep analysis in 6-hour schedule."""
    from app.tasks import celery_app

    beat = celery_app.conf.beat_schedule
    assert "proactive-deep-analysis" in beat


@spec_ref("FS-DBA-003", "AC-8")
def test_dba_003_ac8_morning_report_exists():
    """FS-DBA-003 AC-8: Morning report method exists."""
    from app.agents.proactive_agent import ProactiveAgent

    agent = ProactiveAgent()
    assert hasattr(agent, "morning_report")


@spec_ref("FS-DBA-003", "AC-9")
def test_dba_003_ac9_morning_report_format():
    """FS-DBA-003 AC-9: Morning report Slack formatting."""
    from app.agents.proactive_agent import ProactiveAgent

    agent = ProactiveAgent()
    report = {
        "incidents_24h": 2,
        "agent_actions_24h": 5,
        "generated_at": "2026-03-30T09:00:00Z",
    }
    msg = agent.format_morning_report(report, "pg-prod-01")
    assert "pg-prod-01" in msg
    assert "Incidents" in msg
    assert "2" in msg


@spec_ref("FS-DBA-003", "AC-10")
def test_dba_003_ac10_morning_schedule():
    """FS-DBA-003 AC-10: Morning report at 09:00 daily."""
    from app.tasks import celery_app

    beat = celery_app.conf.beat_schedule
    sched = beat["proactive-morning-report"]
    assert sched["task"] == "proactive_morning_report"

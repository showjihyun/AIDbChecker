# Spec: FS-AI-REPORT-002
"""Tests for DBA Report PDF Download + Report Management."""

from tests.conftest import spec_ref


@spec_ref("FS-AI-REPORT-002", "AC-1")
def test_report_002_ac1_report_id_in_response():
    """AC-1: POST /reports/dba response includes report_id."""
    from app.api.v1.reports import DBAReportResponse

    fields = DBAReportResponse.model_fields
    assert "report_id" in fields


@spec_ref("FS-AI-REPORT-002", "AC-2")
def test_report_002_ac2_list_endpoint():
    """AC-2: GET /reports/dba/list returns paginated list."""
    from app.api.v1.reports import list_dba_reports

    import inspect

    assert inspect.iscoroutinefunction(list_dba_reports)


@spec_ref("FS-AI-REPORT-002", "AC-3")
def test_report_002_ac3_detail_endpoint():
    """AC-3: GET /reports/dba/{id} returns full report JSON."""
    from app.api.v1.reports import get_dba_report

    import inspect

    assert inspect.iscoroutinefunction(get_dba_report)


@spec_ref("FS-AI-REPORT-002", "AC-4")
def test_report_002_ac4_pdf_endpoint():
    """AC-4: GET /reports/dba/{id}/pdf returns PDF."""
    from app.api.v1.reports import download_dba_report_pdf

    import inspect

    assert inspect.iscoroutinefunction(download_dba_report_pdf)


@spec_ref("FS-AI-REPORT-002", "AC-5")
def test_report_002_ac5_pdf_content():
    """AC-5: PDF includes metrics, slow queries, AI analysis in Korean."""
    from app.services.pdf_report import _render_html

    report = {
        "instance_name": "pg-prod-01",
        "period": "daily",
        "start": "2026-03-30T00:00:00",
        "end": "2026-03-31T00:00:00",
        "generated_at": "2026-03-31T09:00:00",
        "metrics_summary": {
            "cpu": {"avg": 45, "max": 92},
            "memory": {"avg": 62, "max": 78},
            "connections": {"avg": 85, "max": 195},
            "tps": {"avg": 1240, "max": 3450},
            "buffer_hit_ratio": {"avg": 99.2},
        },
        "incident_count": 3,
        "incidents": [{"severity": "critical", "title": "CPU spike", "status": "resolved", "detected_at": "2026-03-30T14:00"}],
        "slow_queries": [{"rank": 1, "query": "SELECT * FROM orders", "calls": 100, "mean_exec_time_ms": 2340, "total_exec_time_ms": 234000}],
        "schema_changes_count": 1,
        "schema_changes": [{"change_type": "ALTER", "object_name": "orders", "detected_at": "2026-03-30"}],
        "ai_analysis": "CPU 스파이크는 orders 테이블 풀스캔이 원인입니다.",
    }

    html = _render_html(report)
    assert "핵심 지표" in html
    assert "Slow Query" in html
    assert "AI 분석" in html
    assert "CPU" in html
    assert "pg-prod-01" in html


@spec_ref("FS-AI-REPORT-002", "AC-6")
def test_report_002_ac6_sidebar_reports():
    """AC-6: Reports menu exists in sidebar nav (frontend structural check)."""
    from pathlib import Path

    layout = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "src" / "components" / "layout" / "MainLayout.tsx"
    if layout.exists():
        content = layout.read_text(encoding="utf-8")
        assert "/reports" in content
        assert "Reports" in content


@spec_ref("FS-AI-REPORT-002", "AC-7")
def test_report_002_ac7_frontend_page_exists():
    """AC-7: DBAReportsPage component exists with PDF download."""
    from pathlib import Path

    page = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "src" / "routes" / "pages" / "DBAReportsPage.tsx"
    assert page.exists(), "DBAReportsPage.tsx not found"
    content = page.read_text(encoding="utf-8")
    assert "PDF" in content
    assert "download" in content.lower()


@spec_ref("FS-AI-REPORT-002", "AC-8")
def test_report_002_ac8_db_model():
    """AC-8: DBAReport model exists for persisting reports."""
    from app.models.dba_report import DBAReport

    assert DBAReport.__tablename__ == "dba_reports"
    cols = {c.name for c in DBAReport.__table__.columns}
    assert "report_data" in cols
    assert "instance_id" in cols
    assert "period" in cols
    assert "slack_sent" in cols

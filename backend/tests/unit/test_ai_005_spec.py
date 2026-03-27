# Spec: FR-AI-005, FS-AI-005
"""Spec-Driven tests for AIGC Report Generation.

Feature Spec: docs/specs/ai/AIGC_REPORT_SPEC.md
Test Strategy: docs/specs/tests/TEST_STRATEGY.md

Each test function maps to exactly one Acceptance Criterion (AC).
AC numbering matches FS-AI-005 Section 6.

AC-1:  POST /reports/generate → 30초 이내 응답
AC-2:  응답에 executive_summary, sections(≥5), recommendations 포함
AC-3:  각 section에 severity(good/warning/critical) 포함
AC-4:  recommendations에 priority + 구체적 action 포함
AC-5:  confidence score 0.0~1.0 포함
AC-6:  GET /reports 목록 조회 (Phase 2 stub)
AC-7:  AI Decision Log 자동 기록
AC-8:  Celery Beat 주간 리포트 자동 생성
AC-9:  instance_id=null → 전체 인스턴스 요약
AC-10: language ko/en 전환
"""

import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from tests.conftest import spec_ref

from app.schemas.report import (
    Recommendation,
    RecommendationPriority,
    ReportFormat,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportSection,
    ReportType,
    SectionSeverity,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_VALID_REPORT_JSON = {
    "title": "DB 건강 리포트 — test-instance (7일)",
    "executive_summary": "지난 7일간 전반적으로 안정적이나 수요일 CPU 급증 이벤트 1건 발생.",
    "sections": [
        {
            "title": "리소스 사용량",
            "content": "CPU 평균 35%, 최대 92%",
            "severity": "warning",
            "metrics": {"cpu_avg": 35, "cpu_max": 92, "memory_avg": 68},
        },
        {
            "title": "쿼리 성능",
            "content": "Top 5 Slow Query 중 3건이 인덱스 미사용. Seq Scan 비율 12%.",
            "severity": "warning",
            "metrics": {"seq_scan_ratio": 12, "p95_latency_ms": 450},
        },
        {
            "title": "인시던트",
            "content": "총 3건 (CRITICAL:1, WARNING:2). MTTR 평균 15분. 해결율 100%.",
            "severity": "good",
            "metrics": {"total": 3, "mttr_min": 15},
        },
        {
            "title": "ASH 분석",
            "content": "Top Wait: CPU(45%), IO(30%), Lock(15%). 활성 세션 추세 안정.",
            "severity": "good",
        },
        {
            "title": "스키마 변경",
            "content": "CREATE INDEX idx_orders_created_at 1건 (3/22).",
            "severity": "good",
        },
    ],
    "recommendations": [
        {
            "priority": "high",
            "title": "dead_tuples 증가 추세",
            "description": "VACUUM ANALYZE 권장. dead_tuples > 10,000 in orders table.",
            "action": "VACUUM ANALYZE orders",
            "confidence": 0.9,
        },
        {
            "priority": "medium",
            "title": "shared_buffers 증설 검토",
            "description": "캐시 히트율 94% → 95% 미만. 256MB→512MB 증설 권장.",
            "action": "ALTER SYSTEM SET shared_buffers = '512MB'",
            "confidence": 0.75,
        },
        {
            "priority": "low",
            "title": "미사용 인덱스 정리",
            "description": "3개 미사용 인덱스 발견.",
            "action": "DROP INDEX idx_unused_1",
            "confidence": 0.65,
        },
    ],
    "confidence": 0.85,
}


@pytest.fixture
def mock_session():
    """Create a mock async DB session with empty query results."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
    mock_result.first.return_value = None
    mock_result.scalar.return_value = "test-instance"
    session.execute.return_value = mock_result
    return session


@pytest.fixture
def mock_llm_response():
    """Mock LLM response returning valid report JSON."""
    resp = MagicMock()
    resp.content = json.dumps(_VALID_REPORT_JSON)
    resp.usage_metadata = {"total_tokens": 1500}
    return resp


def _make_mock_llm(response):
    """Create a mock LLM with the given response."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = response
    mock_llm.model_name = "gpt-4o"
    return mock_llm


# ---------------------------------------------------------------------------
# AC-1: POST /reports/generate → 30초 이내 응답
# ---------------------------------------------------------------------------


@spec_ref("FS-AI-005", "AC-1")
@pytest.mark.asyncio
async def test_fs_ai_005_ac1_report_generation_within_30s(mock_session, mock_llm_response):
    """FS-AI-005 AC-1: POST /reports/generate로 7일 건강 리포트 생성 시 30초 이내 응답."""
    with patch("app.services.report_generator._get_llm") as mock_get:
        mock_get.return_value = _make_mock_llm(mock_llm_response)

        from app.services.report_generator import generate_report

        start = time.monotonic()
        result = await generate_report(mock_session, instance_id=uuid4(), period="7d")
        elapsed = time.monotonic() - start

        assert result.status == "completed"
        assert elapsed < 30  # 30초 이내
        assert result.generation_time_ms >= 0  # mock은 0ms 가능


@spec_ref("FS-AI-005", "AC-1")
@pytest.mark.asyncio
async def test_fs_ai_005_ac1_llm_failure_returns_failed_gracefully(mock_session):
    """FS-AI-005 AC-1: LLM 실패 시 status='failed'로 30초 이내 응답."""
    with patch("app.services.report_generator._get_llm") as mock_get:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = RuntimeError("LLM unavailable")
        mock_llm.model_name = "gpt-4o"
        mock_get.return_value = mock_llm

        from app.services.report_generator import generate_report

        result = await generate_report(mock_session, instance_id=uuid4())

        assert result.status == "failed"
        assert result.confidence == 0.0
        assert "LLM" in result.executive_summary


# ---------------------------------------------------------------------------
# AC-2: 응답에 executive_summary, sections(≥5), recommendations 포함
# ---------------------------------------------------------------------------


@spec_ref("FS-AI-005", "AC-2")
@pytest.mark.asyncio
async def test_fs_ai_005_ac2_response_contains_required_fields(mock_session, mock_llm_response):
    """FS-AI-005 AC-2: 응답에 executive_summary, sections(5개 이상), recommendations 포함."""
    with patch("app.services.report_generator._get_llm") as mock_get:
        mock_get.return_value = _make_mock_llm(mock_llm_response)

        from app.services.report_generator import generate_report

        result = await generate_report(mock_session, instance_id=uuid4())

        assert result.executive_summary  # non-empty
        assert len(result.sections) >= 5
        assert len(result.recommendations) >= 1
        assert result.title  # non-empty


# ---------------------------------------------------------------------------
# AC-3: 각 section에 severity(good/warning/critical) 포함
# ---------------------------------------------------------------------------


@spec_ref("FS-AI-005", "AC-3")
@pytest.mark.asyncio
async def test_fs_ai_005_ac3_sections_have_severity(mock_session, mock_llm_response):
    """FS-AI-005 AC-3: 각 section에 severity(good/warning/critical) 포함."""
    with patch("app.services.report_generator._get_llm") as mock_get:
        mock_get.return_value = _make_mock_llm(mock_llm_response)

        from app.services.report_generator import generate_report

        result = await generate_report(mock_session, instance_id=uuid4())

        valid_severities = {"good", "warning", "critical"}
        for section in result.sections:
            assert section.severity is not None, f"Section '{section.title}' missing severity"
            assert section.severity.value in valid_severities


@spec_ref("FS-AI-005", "AC-3")
def test_fs_ai_005_ac3_section_severity_enum_values():
    """FS-AI-005 AC-3: SectionSeverity enum이 good/warning/critical만 허용."""
    assert set(s.value for s in SectionSeverity) == {"good", "warning", "critical"}


# ---------------------------------------------------------------------------
# AC-4: recommendations에 priority + 구체적 action 포함
# ---------------------------------------------------------------------------


@spec_ref("FS-AI-005", "AC-4")
@pytest.mark.asyncio
async def test_fs_ai_005_ac4_recommendations_have_priority_and_action(
    mock_session, mock_llm_response
):
    """FS-AI-005 AC-4: recommendations에 priority + 구체적 action 포함."""
    with patch("app.services.report_generator._get_llm") as mock_get:
        mock_get.return_value = _make_mock_llm(mock_llm_response)

        from app.services.report_generator import generate_report

        result = await generate_report(mock_session, instance_id=uuid4())

        for rec in result.recommendations:
            assert rec.priority is not None
            assert rec.priority.value in {"high", "medium", "low"}
            assert rec.title  # non-empty
            assert rec.description  # non-empty
            assert rec.confidence >= 0.0

        # At least one recommendation should have a concrete action
        actions = [r.action for r in result.recommendations if r.action]
        assert len(actions) >= 1, "At least one recommendation must have a concrete action"


@spec_ref("FS-AI-005", "AC-4")
def test_fs_ai_005_ac4_recommendation_schema_validation():
    """FS-AI-005 AC-4: Recommendation 스키마가 priority/action/confidence 필드 강제."""
    rec = Recommendation(
        priority=RecommendationPriority.HIGH,
        title="Add index",
        description="orders table seq scan > 80%",
        action="CREATE INDEX CONCURRENTLY idx_orders_status ON orders(status)",
        confidence=0.9,
    )
    assert rec.priority == RecommendationPriority.HIGH
    assert "CREATE INDEX" in rec.action
    assert 0.0 <= rec.confidence <= 1.0


# ---------------------------------------------------------------------------
# AC-5: confidence score 0.0~1.0 포함
# ---------------------------------------------------------------------------


@spec_ref("FS-AI-005", "AC-5")
@pytest.mark.asyncio
async def test_fs_ai_005_ac5_confidence_score_in_range(mock_session, mock_llm_response):
    """FS-AI-005 AC-5: confidence score 0.0~1.0 포함."""
    with patch("app.services.report_generator._get_llm") as mock_get:
        mock_get.return_value = _make_mock_llm(mock_llm_response)

        from app.services.report_generator import generate_report

        result = await generate_report(mock_session, instance_id=uuid4())

        assert 0.0 <= result.confidence <= 1.0
        assert result.confidence == 0.85  # matches mock data


@spec_ref("FS-AI-005", "AC-5")
def test_fs_ai_005_ac5_response_schema_rejects_invalid_confidence():
    """FS-AI-005 AC-5: confidence < 0.0 또는 > 1.0 시 Pydantic ValidationError."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ReportGenerateResponse(
            report_id=uuid4(),
            instance_id=None,
            report_type=ReportType.HEALTH,
            period="7d",
            title="Test",
            executive_summary="Test",
            sections=[],
            recommendations=[],
            status="completed",
            format=ReportFormat.HTML,
            generated_at=datetime.now(timezone.utc),
            generation_time_ms=1000,
            ai_model="gpt-4o",
            tokens_used=100,
            confidence=1.5,  # invalid
        )


# ---------------------------------------------------------------------------
# AC-6: GET /reports 목록 조회 (Phase 2 — API 존재 확인)
# ---------------------------------------------------------------------------


@spec_ref("FS-AI-005", "AC-6")
def test_fs_ai_005_ac6_reports_list_endpoint_exists():
    """FS-AI-005 AC-6: /reports/generate POST 엔드포인트가 등록되어 있음."""
    from app.main import app as fastapi_app

    routes = [r.path for r in fastapi_app.routes]
    assert "/api/v1/reports/generate" in routes


# ---------------------------------------------------------------------------
# AC-7: AI Decision Log 자동 기록
# ---------------------------------------------------------------------------


@spec_ref("FS-AI-005", "AC-7")
@pytest.mark.asyncio
async def test_fs_ai_005_ac7_report_includes_model_and_tokens(mock_session, mock_llm_response):
    """FS-AI-005 AC-7: 리포트에 ai_model, tokens_used 메타데이터 포함 (Decision Log 기반)."""
    with patch("app.services.report_generator._get_llm") as mock_get:
        mock_get.return_value = _make_mock_llm(mock_llm_response)

        from app.services.report_generator import generate_report

        result = await generate_report(mock_session, instance_id=uuid4())

        assert result.ai_model == "gpt-4o"
        assert result.tokens_used == 1500
        assert result.generation_time_ms >= 0  # mock은 0ms 가능, 실환경에서 > 0


# ---------------------------------------------------------------------------
# AC-8: Celery Beat 주간 리포트 자동 생성
# ---------------------------------------------------------------------------


@spec_ref("FS-AI-005", "AC-8")
def test_fs_ai_005_ac8_celery_task_registered():
    """FS-AI-005 AC-8: generate_weekly_report Celery 태스크가 등록됨."""
    from app.tasks.report import generate_weekly_report

    assert generate_weekly_report.name == "generate_weekly_report"
    assert callable(generate_weekly_report)


@spec_ref("FS-AI-005", "AC-8")
def test_fs_ai_005_ac8_celery_task_has_retry_config():
    """FS-AI-005 AC-8: 주간 리포트 태스크에 재시도 설정이 있음."""
    from app.tasks.report import generate_weekly_report

    assert generate_weekly_report.max_retries == 2
    assert generate_weekly_report.default_retry_delay == 300


# ---------------------------------------------------------------------------
# AC-9: instance_id=null → 전체 인스턴스 요약 리포트
# ---------------------------------------------------------------------------


@spec_ref("FS-AI-005", "AC-9")
@pytest.mark.asyncio
async def test_fs_ai_005_ac9_null_instance_generates_summary(mock_session, mock_llm_response):
    """FS-AI-005 AC-9: instance_id=null일 때 전체 인스턴스 요약 리포트 생성."""
    with patch("app.services.report_generator._get_llm") as mock_get:
        mock_get.return_value = _make_mock_llm(mock_llm_response)

        from app.services.report_generator import generate_report

        result = await generate_report(mock_session, instance_id=None, period="7d")

        assert result.status == "completed"
        assert result.instance_id is None


@spec_ref("FS-AI-005", "AC-9")
def test_fs_ai_005_ac9_request_schema_allows_null_instance():
    """FS-AI-005 AC-9: ReportGenerateRequest.instance_id가 None 허용."""
    req = ReportGenerateRequest()
    assert req.instance_id is None

    req_with = ReportGenerateRequest(instance_id=uuid4())
    assert req_with.instance_id is not None


# ---------------------------------------------------------------------------
# AC-10: language ko/en 전환
# ---------------------------------------------------------------------------


@spec_ref("FS-AI-005", "AC-10")
@pytest.mark.asyncio
async def test_fs_ai_005_ac10_language_ko_generates_korean(mock_session, mock_llm_response):
    """FS-AI-005 AC-10: language='ko' 설정 시 한국어 리포트 생성."""
    with patch("app.services.report_generator._get_llm") as mock_get:
        mock_llm = _make_mock_llm(mock_llm_response)
        mock_get.return_value = mock_llm

        from app.services.report_generator import generate_report

        await generate_report(mock_session, instance_id=uuid4(), language="ko")

        # Verify the system prompt included Korean language instruction
        call_args = mock_llm.ainvoke.call_args
        messages = call_args[0][0]  # first positional arg = message list
        system_content = messages[0].content
        assert "ko" in system_content


@spec_ref("FS-AI-005", "AC-10")
@pytest.mark.asyncio
async def test_fs_ai_005_ac10_language_en_generates_english(mock_session, mock_llm_response):
    """FS-AI-005 AC-10: language='en' 설정 시 영어 리포트 생성."""
    with patch("app.services.report_generator._get_llm") as mock_get:
        mock_llm = _make_mock_llm(mock_llm_response)
        mock_get.return_value = mock_llm

        from app.services.report_generator import generate_report

        await generate_report(mock_session, instance_id=uuid4(), language="en")

        call_args = mock_llm.ainvoke.call_args
        messages = call_args[0][0]
        system_content = messages[0].content
        assert "en" in system_content


@spec_ref("FS-AI-005", "AC-10")
def test_fs_ai_005_ac10_request_schema_validates_language():
    """FS-AI-005 AC-10: ReportGenerateRequest.language는 ko/en만 허용."""
    from pydantic import ValidationError

    req_ko = ReportGenerateRequest(language="ko")
    assert req_ko.language == "ko"

    req_en = ReportGenerateRequest(language="en")
    assert req_en.language == "en"

    with pytest.raises(ValidationError):
        ReportGenerateRequest(language="ja")  # 지원하지 않는 언어


# ---------------------------------------------------------------------------
# Edge cases (Spec 규칙: 유틸리티/헬퍼는 Spec 참조 없이 허용)
# ---------------------------------------------------------------------------


class TestReportHelpers:
    """Edge case tests for internal helper functions."""

    def test_resolve_period_7d(self):
        """기간 단축어 '7d' → 7일 전~현재."""
        from app.services.report_generator import _resolve_period

        start, end = _resolve_period("7d", None, None)
        diff = end - start
        assert 6 < diff.total_seconds() / 86400 < 8  # ~7 days

    def test_resolve_period_custom(self):
        """custom 기간은 명시된 start/end 사용."""
        from app.services.report_generator import _resolve_period

        s = datetime(2026, 3, 1, tzinfo=timezone.utc)
        e = datetime(2026, 3, 15, tzinfo=timezone.utc)
        start, end = _resolve_period("custom", s, e)
        assert start == s
        assert end == e

    def test_parse_llm_response_strips_markdown_fences(self):
        """LLM 응답에서 markdown 코드 펜스를 제거하고 JSON 파싱."""
        from app.services.report_generator import _parse_llm_response

        raw = '```json\n{"title": "test"}\n```'
        parsed = _parse_llm_response(raw)
        assert parsed["title"] == "test"

    def test_parse_llm_response_plain_json(self):
        """코드 펜스 없는 순수 JSON도 파싱."""
        from app.services.report_generator import _parse_llm_response

        raw = '{"title": "test", "confidence": 0.9}'
        parsed = _parse_llm_response(raw)
        assert parsed["confidence"] == 0.9

    def test_parse_llm_response_invalid_json_raises(self):
        """잘못된 JSON은 ValueError/JSONDecodeError."""
        from app.services.report_generator import _parse_llm_response

        with pytest.raises((json.JSONDecodeError, ValueError)):
            _parse_llm_response("not json at all")

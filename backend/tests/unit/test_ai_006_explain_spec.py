# Spec: FR-AI-006
"""Spec-Driven tests for EXPLAIN 자연어 해석.

Feature Spec: FR-AI-006 (NL2SQL_SPEC extension)
Test Strategy: docs/specs/tests/TEST_STRATEGY.md

AC Coverage (derived from FR-AI-006 PRD description):
  AC-1: POST /nl2sql/explain → summary + bottlenecks + suggestions
  AC-2: EXPLAIN 결과에 plain-language summary 포함
  AC-3: 병목 지점 (>20% cost) 식별
  AC-4: 개선 방안 (CREATE INDEX 등) 제안
  AC-5: confidence score 포함
  AC-6: 읽기 전용 쿼리만 허용 (SELECT only)
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from tests.conftest import spec_ref

try:
    from app.schemas.nl2sql import ExplainRequest, ExplainResponse, ExplainBottleneck
except ImportError:
    pytest.skip("EXPLAIN schemas not implemented yet (Phase 2)", allow_module_level=True)


# ---------------------------------------------------------------------------
# AC-1: POST /nl2sql/explain endpoint
# ---------------------------------------------------------------------------


@spec_ref("FR-AI-006", "AC-1")
def test_fr_ai_006_ac1_endpoint_registered():
    """FR-AI-006 AC-1: /nl2sql/explain POST 엔드포인트 등록됨."""
    from app.main import app as fastapi_app

    routes = [r.path for r in fastapi_app.routes]
    assert "/api/v1/nl2sql/explain" in routes


@spec_ref("FR-AI-006", "AC-1")
def test_fr_ai_006_ac1_request_schema():
    """FR-AI-006 AC-1: ExplainRequest에 sql, instance_id 필수."""
    req = ExplainRequest(sql="SELECT * FROM users", instance_id=uuid4())
    assert req.sql == "SELECT * FROM users"
    assert req.instance_id is not None


@spec_ref("FR-AI-006", "AC-1")
def test_fr_ai_006_ac1_response_schema():
    """FR-AI-006 AC-1: ExplainResponse에 필수 필드 존재."""
    resp = ExplainResponse(
        sql="SELECT 1",
        plan_json={},
        summary="Simple constant scan",
        bottlenecks=[],
        optimization_suggestions=[],
        total_cost=0.01,
        execution_time_ms=50,
        ai_model="gpt-4o",
        confidence=0.9,
    )
    assert resp.summary
    assert resp.confidence >= 0.0


# ---------------------------------------------------------------------------
# AC-2: Plain-language summary
# ---------------------------------------------------------------------------


@spec_ref("FR-AI-006", "AC-2")
@pytest.mark.asyncio
async def test_fr_ai_006_ac2_summary_from_llm():
    """FR-AI-006 AC-2: LLM이 plain-language summary 생성."""
    llm_response = json.dumps({
        "summary": "This query scans the orders table sequentially, which is slow for large datasets.",
        "bottlenecks": [
            {
                "node_type": "Seq Scan",
                "table": "orders",
                "cost_pct": 95.0,
                "issue": "Full table scan on 10M rows",
                "suggestion": "CREATE INDEX on orders(created_at)",
            }
        ],
        "optimization_suggestions": [
            "CREATE INDEX CONCURRENTLY idx_orders_created ON orders(created_at)"
        ],
        "confidence": 0.87,
    })

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = ([{"Plan": {"Total Cost": 45000.0}}],)
    mock_session.execute.return_value = mock_result

    with patch("app.services.nl2sql._get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = llm_response
        mock_llm.ainvoke.return_value = mock_resp
        mock_get_llm.return_value = mock_llm

        from app.services.nl2sql import explain_query

        result = await explain_query(mock_session, "SELECT * FROM orders WHERE created_at > '2026-01-01'")

    assert "summary" in result
    assert len(result["summary"]) > 10


# ---------------------------------------------------------------------------
# AC-3: Bottleneck identification
# ---------------------------------------------------------------------------


@spec_ref("FR-AI-006", "AC-3")
def test_fr_ai_006_ac3_bottleneck_schema():
    """FR-AI-006 AC-3: ExplainBottleneck 스키마 유효."""
    bn = ExplainBottleneck(
        node_type="Seq Scan",
        table="orders",
        cost_pct=85.2,
        issue="Full table scan",
        suggestion="CREATE INDEX",
    )
    assert bn.cost_pct == 85.2
    assert bn.node_type == "Seq Scan"


# ---------------------------------------------------------------------------
# AC-4: Optimization suggestions
# ---------------------------------------------------------------------------


@spec_ref("FR-AI-006", "AC-4")
def test_fr_ai_006_ac4_suggestions_in_response():
    """FR-AI-006 AC-4: ExplainResponse에 optimization_suggestions 리스트."""
    resp = ExplainResponse(
        sql="SELECT 1",
        plan_json={},
        summary="Test",
        bottlenecks=[],
        optimization_suggestions=["CREATE INDEX", "VACUUM ANALYZE"],
        total_cost=100.0,
        execution_time_ms=50,
        ai_model="gpt-4o",
        confidence=0.8,
    )
    assert len(resp.optimization_suggestions) == 2


# ---------------------------------------------------------------------------
# AC-5: Confidence score
# ---------------------------------------------------------------------------


@spec_ref("FR-AI-006", "AC-5")
def test_fr_ai_006_ac5_confidence_range():
    """FR-AI-006 AC-5: confidence 0.0~1.0."""
    from pydantic import ValidationError

    # Valid
    resp = ExplainResponse(
        sql="SELECT 1",
        plan_json={},
        summary="Test",
        total_cost=1.0,
        execution_time_ms=10,
        ai_model="test",
        confidence=0.85,
    )
    assert 0.0 <= resp.confidence <= 1.0

    # Invalid
    with pytest.raises(ValidationError):
        ExplainResponse(
            sql="SELECT 1",
            plan_json={},
            summary="Test",
            total_cost=1.0,
            execution_time_ms=10,
            ai_model="test",
            confidence=1.5,
        )


# ---------------------------------------------------------------------------
# AC-6: Read-only enforcement
# ---------------------------------------------------------------------------


@spec_ref("FR-AI-006", "AC-6")
@pytest.mark.asyncio
async def test_fr_ai_006_ac6_write_sql_rejected():
    """FR-AI-006 AC-6: INSERT/UPDATE/DELETE SQL → ValueError."""
    mock_session = AsyncMock()

    from app.services.nl2sql import explain_query

    with pytest.raises((ValueError, RuntimeError)):
        await explain_query(mock_session, "DELETE FROM users WHERE id = 1")

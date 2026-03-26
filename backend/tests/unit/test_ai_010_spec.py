# Spec: FS-AI-010
"""Tests for FS-AI-010 Acceptance Criteria (MTL Lite RCA).

Covers MTL 4-Head prediction, confidence calculation, reasoning chain,
evidence links, LLM failure fallback, and RAG prompt integration.

IMPORTANT: Do NOT delete the @spec_ref decorator -- it enables AC tracking in CI.
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# Imports from production code under test
# ---------------------------------------------------------------------------
from app.services.mtl_lite import (
    _compute_overall_confidence,
    _build_evidence_links,
    _parse_llm_response,
    _MTL_USER_PROMPT,
    _MTL_FALLBACK,
    predict,
)
from app.schemas.mtl import (
    AnomalyType,
    SeverityLevel,
    MTLPredictResponse,
)


# ---------------------------------------------------------------------------
# Helpers: build a valid LLM JSON response
# ---------------------------------------------------------------------------
def _make_llm_json(
    anomaly_type="query_performance_degradation",
    root_cause="Slow sequential scan on orders table due to missing index",
    severity="WARNING",
    severity_score=0.7,
    anomaly_confidence=0.85,
    root_cause_confidence=0.82,
    actions=None,
    reasoning=None,
):
    """Build a valid MTL LLM response dict."""
    if actions is None:
        actions = [
            {
                "action": "CREATE INDEX CONCURRENTLY idx_orders_date ON orders(created_at);",
                "description": "Add missing index on orders.created_at",
                "confidence": 0.9,
                "risk": "LOW",
            },
            {
                "action": "ANALYZE orders;",
                "description": "Update planner statistics",
                "confidence": 0.95,
                "risk": "LOW",
            },
        ]
    if reasoning is None:
        reasoning = [
            "Step 1: Observed CPU spike correlated with sequential scan on orders table",
            "Step 2: Hypothesized missing index on frequently filtered column created_at",
            "Step 3: Confirmed via pg_stat_user_tables showing high seq_scan count",
            "Step 4: Concluded that adding an index will reduce CPU and query latency",
        ]
    return {
        "anomaly_type": anomaly_type,
        "anomaly_confidence": anomaly_confidence,
        "root_cause": root_cause,
        "root_cause_detail": {
            "component": "index",
            "identifier": "orders.created_at",
            "evidence": "seq_scan=125000, idx_scan=0",
        },
        "root_cause_confidence": root_cause_confidence,
        "severity": severity,
        "severity_score": severity_score,
        "suggested_actions": actions,
        "confidence": 0.85,
        "reasoning_chain": reasoning,
    }


def _mock_llm_response(json_dict):
    """Create a mock LangChain response with .content = JSON string."""
    resp = MagicMock()
    resp.content = json.dumps(json_dict)
    resp.response_metadata = {"token_usage": {"total_tokens": 500}}
    return resp


# ---------------------------------------------------------------------------
# AC-1: MTL predict returns 4 heads
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-010", "AC-1")
async def test_fs_ai_010_ac1_mtl_predict_returns_4_heads():
    """FS-AI-010 AC-1: POST /api/v1/mtl/predict가 4개 Head 결과를 동시에 반환"""
    incident_id = uuid4()
    instance_id = uuid4()
    llm_json = _make_llm_json()
    mock_response = _mock_llm_response(llm_json)

    with patch("app.services.mtl_lite._get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_llm.return_value = mock_llm

        result = await predict(
            incident_id=incident_id,
            instance_id=instance_id,
            metrics_snapshot="CPU: 92%, TPS: 500",
            ash_summary="10 active sessions, 3 waiting on Lock",
            rag_results="No similar past incidents found.",
            detected_at=datetime.now(timezone.utc),
        )

    # Head 1: Anomaly classification
    assert result.anomaly_type == AnomalyType.QUERY_PERFORMANCE
    assert 0.0 <= result.anomaly_confidence <= 1.0

    # Head 2: Root cause
    assert result.root_cause is not None
    assert len(result.root_cause) > 0
    assert result.root_cause_detail is not None
    assert 0.0 <= result.root_cause_confidence <= 1.0

    # Head 3: Severity
    assert result.severity in SeverityLevel
    assert 0.0 <= result.severity_score <= 1.0

    # Head 4: Suggested actions
    assert len(result.suggested_actions) >= 1
    for action in result.suggested_actions:
        assert action.action is not None
        assert 0.0 <= action.confidence <= 1.0


# ---------------------------------------------------------------------------
# AC-2: Confidence is weighted average across 4 heads
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-010", "AC-2")
async def test_fs_ai_010_ac2_confidence_weighted_average():
    """FS-AI-010 AC-2: Confidence Score가 4개 Head의 가중 평균으로 계산됨"""
    # Weights: anomaly=0.25, root_cause=0.35, severity=0.15, action=0.25
    prediction = {
        "anomaly_confidence": 0.8,
        "root_cause_confidence": 0.9,
        "severity_score": 0.7,
        "suggested_actions": [
            {"confidence": 0.85},
            {"confidence": 0.95},
        ],
    }

    result = _compute_overall_confidence(prediction)
    # Expected: 0.25*0.8 + 0.35*0.9 + 0.15*0.7 + 0.25*mean(0.85,0.95)
    # = 0.20 + 0.315 + 0.105 + 0.25*0.9
    # = 0.20 + 0.315 + 0.105 + 0.225
    # = 0.845
    assert result == pytest.approx(0.845, abs=0.001)

    # Edge case: no actions -> action_confidence = 0
    pred_no_actions = {
        "anomaly_confidence": 1.0,
        "root_cause_confidence": 1.0,
        "severity_score": 1.0,
        "suggested_actions": [],
    }
    result2 = _compute_overall_confidence(pred_no_actions)
    # 0.25*1.0 + 0.35*1.0 + 0.15*1.0 + 0.25*0.0 = 0.75
    assert result2 == pytest.approx(0.75, abs=0.001)

    # Edge case: all zeros
    pred_zero = {
        "anomaly_confidence": 0.0,
        "root_cause_confidence": 0.0,
        "severity_score": 0.0,
        "suggested_actions": [],
    }
    assert _compute_overall_confidence(pred_zero) == 0.0

    # Result should be clamped to [0.0, 1.0]
    assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# AC-3: Reasoning chain has min 3 steps
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-010", "AC-3")
async def test_fs_ai_010_ac3_reasoning_chain_3():
    """FS-AI-010 AC-3: Reasoning Chain이 최소 3단계 이상의 논리적 추론 과정을 포함"""
    incident_id = uuid4()
    instance_id = uuid4()
    llm_json = _make_llm_json(
        reasoning=[
            "Step 1: Observed CPU spike at 92%",
            "Step 2: Correlated with sequential scan on orders table",
            "Step 3: Missing index on orders.created_at confirmed",
            "Step 4: Recommend CREATE INDEX CONCURRENTLY",
        ]
    )
    mock_response = _mock_llm_response(llm_json)

    with patch("app.services.mtl_lite._get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_llm.return_value = mock_llm

        result = await predict(
            incident_id=incident_id,
            instance_id=instance_id,
            metrics_snapshot="CPU: 92%",
            ash_summary="",
            rag_results="",
        )

    assert len(result.reasoning_chain) >= 3
    # Each step should be a non-empty string
    for step in result.reasoning_chain:
        assert isinstance(step, str)
        assert len(step) > 0


# ---------------------------------------------------------------------------
# AC-4: Evidence links are valid API endpoints
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-010", "AC-4")
async def test_fs_ai_010_ac4_evidence_links_api():
    """FS-AI-010 AC-4: Evidence Links가 유효한 API 엔드포인트를 가리키며 접근 가능"""
    instance_id = uuid4()
    incident_id = uuid4()
    detected_at = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)

    links = _build_evidence_links(instance_id, incident_id, detected_at)

    # Should return at least 4 links (metrics, ash, wait-breakdown, incident)
    assert len(links) >= 4

    # Each link must be a valid API path
    for link in links:
        assert link.startswith("/api/v1/")

    # Verify specific endpoint patterns
    metrics_link = [l for l in links if "/metrics?" in l]
    assert len(metrics_link) >= 1

    ash_link = [l for l in links if "/ash?" in l]
    assert len(ash_link) >= 1

    incident_link = [l for l in links if f"/incidents/{incident_id}" in l]
    assert len(incident_link) >= 1

    # Verify time range parameters are included
    for link in links:
        if "?" in link:
            assert "from=" in link
            assert "to=" in link


# ---------------------------------------------------------------------------
# AC-5: LLM failure results in graceful degradation (fallback)
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-010", "AC-5")
async def test_fs_ai_010_ac5_llm_failure_graceful_degradation():
    """FS-AI-010 AC-5: LLM 호출 실패 시 graceful degradation (fallback 응답)"""
    incident_id = uuid4()
    instance_id = uuid4()

    with patch("app.services.mtl_lite._get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        # Simulate LLM call failure
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM service unavailable"))
        mock_get_llm.return_value = mock_llm

        result = await predict(
            incident_id=incident_id,
            instance_id=instance_id,
            metrics_snapshot="CPU: 50%",
            ash_summary="",
            rag_results="",
        )

    # Should return a valid response, not raise an exception
    assert isinstance(result, MTLPredictResponse)

    # Fallback values per _MTL_FALLBACK
    assert result.anomaly_type == AnomalyType.UNKNOWN
    assert result.anomaly_confidence == 0.0
    assert result.root_cause_confidence == 0.0
    assert "failed" in result.root_cause.lower() or "manual" in result.root_cause.lower()
    assert result.severity == SeverityLevel.NOTICE
    assert len(result.suggested_actions) == 0

    # Fallback confidence should be very low (severity_score=0.5 contributes
    # 0.15 * 0.5 = 0.075 to the weighted average, all other heads are 0)
    expected_fallback_conf = _compute_overall_confidence(_MTL_FALLBACK)
    assert result.confidence == pytest.approx(expected_fallback_conf, abs=0.001)
    assert result.confidence < 0.1  # Very low confidence indicates degradation

    # Evidence links should still be generated
    assert len(result.evidence_links) >= 1


# ---------------------------------------------------------------------------
# AC-6: RAG results are included in the MTL prompt
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-010", "AC-6")
async def test_fs_ai_010_ac6_rag_rca():
    """FS-AI-010 AC-6: RAG 검색 결과가 프롬프트에 포함되어 RCA 정확도 향상에 기여"""
    # Verify the prompt template contains the RAG results placeholder
    assert "{rag_results}" in _MTL_USER_PROMPT

    # Verify RAG content is actually embedded in the prompt
    rag_text = "Similar Incident #1: CPU spike due to missing index on users table"
    metrics_text = "CPU: 90%"
    ash_text = "5 active sessions"

    formatted = _MTL_USER_PROMPT.format(
        metrics_snapshot=metrics_text,
        ash_summary=ash_text,
        rag_results=rag_text,
    )
    assert rag_text in formatted
    assert metrics_text in formatted
    assert ash_text in formatted

    # Verify that when we call predict, the RAG content reaches the LLM
    incident_id = uuid4()
    instance_id = uuid4()
    llm_json = _make_llm_json()
    mock_response = _mock_llm_response(llm_json)
    captured_messages = []

    with patch("app.services.mtl_lite._get_llm") as mock_get_llm:
        mock_llm = AsyncMock()

        async def capture_invoke(messages):
            captured_messages.extend(messages)
            return mock_response

        mock_llm.ainvoke = capture_invoke
        mock_get_llm.return_value = mock_llm

        await predict(
            incident_id=incident_id,
            instance_id=instance_id,
            metrics_snapshot=metrics_text,
            ash_summary=ash_text,
            rag_results=rag_text,
        )

    # The user message (second message) should contain the RAG text
    assert len(captured_messages) >= 2
    user_msg = captured_messages[1]
    assert rag_text in user_msg.content


# ---------------------------------------------------------------------------
# AC-7: Feedback saves (Integration)
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-010", "AC-7")
async def test_fs_ai_010_ac7():
    """FS-AI-010 AC-7: 운영자 피드백(thumbs up/down) 저장 및 주간 정확도 집계 가능"""
    pytest.skip("Integration test -- requires live DB + API endpoint")


# ---------------------------------------------------------------------------
# AC-8: Incident to prediction under 30s (Integration)
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-010", "AC-8")
async def test_fs_ai_010_ac8_mtl_30_cloud_llm():
    """FS-AI-010 AC-8: 인시던트 발생부터 MTL 예측 완료까지 30초 이내 (Cloud LLM 기준)"""
    pytest.skip("Integration test -- requires live LLM service")


# ---------------------------------------------------------------------------
# AC-9: Prediction schema contract (unit) + DB persistence (integration)
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-010", "AC-9")
async def test_fs_ai_010_ac9_mtl_predictions():
    """FS-AI-010 AC-9: MTLPredictResponse covers all mtl_predictions table columns.

    Validates the schema contract: the Pydantic response model has all fields
    required by the mtl_predictions table (per MTL_RCA_SPEC.md Section 2.2).

    Table columns:
      id, incident_id, instance_id,
      anomaly_type, anomaly_confidence,
      root_cause, root_cause_detail,
      severity, severity_score,
      suggested_actions,
      confidence, reasoning_chain, evidence_links,
      model_version, inference_time_ms, tokens_used,
      feedback_correct, feedback_comment,
      created_at
    """
    fields = MTLPredictResponse.model_fields

    # DB column -> Pydantic field mapping
    required_db_columns = {
        "prediction_id": "prediction_id",  # maps to id in DB
        "incident_id": "incident_id",
        # instance_id is not in response (it's in the request context)
        "anomaly_type": "anomaly_type",
        "anomaly_confidence": "anomaly_confidence",
        "root_cause": "root_cause",
        "root_cause_detail": "root_cause_detail",  # JSONB in DB
        "severity": "severity",
        "severity_score": "severity_score",
        "suggested_actions": "suggested_actions",  # JSONB in DB
        "confidence": "confidence",
        "reasoning_chain": "reasoning_chain",  # JSONB in DB
        "evidence_links": "evidence_links",  # JSONB in DB
        "model_version": "model_version",
        "inference_time_ms": "inference_time_ms",
        "tokens_used": "tokens_used",
    }

    for db_col, pydantic_field in required_db_columns.items():
        assert pydantic_field in fields, (
            f"MTLPredictResponse missing field '{pydantic_field}' "
            f"required by mtl_predictions.{db_col}"
        )

    # Verify a fully populated response can be constructed
    response = MTLPredictResponse(
        prediction_id=uuid4(),
        incident_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        anomaly_type=AnomalyType.QUERY_PERFORMANCE,
        anomaly_confidence=0.85,
        root_cause="Missing index on orders.created_at",
        root_cause_confidence=0.80,
        severity=SeverityLevel.WARNING,
        severity_score=0.7,
        suggested_actions=[],
        confidence=0.82,
        reasoning_chain=["Step 1", "Step 2", "Step 3"],
        evidence_links=["/api/v1/instances/test/metrics"],
        model_version="mtl-lite-v1",
        inference_time_ms=150,
        tokens_used=500,
    )

    # All fields that would be persisted to DB are non-None
    assert response.prediction_id is not None
    assert response.incident_id is not None
    assert response.anomaly_type is not None
    assert response.confidence is not None
    assert response.model_version is not None
    assert response.inference_time_ms is not None
    assert response.tokens_used is not None

    # Verify the response can be serialized to dict (simulating DB insert)
    data = response.model_dump()
    assert isinstance(data["anomaly_type"], str)
    assert isinstance(data["suggested_actions"], list)
    assert isinstance(data["reasoning_chain"], list)
    assert isinstance(data["evidence_links"], list)

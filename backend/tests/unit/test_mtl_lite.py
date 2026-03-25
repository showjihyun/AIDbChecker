# Spec: FR-AI-010, FR-AI-011, FS-AI-010
"""Unit tests for MTL Lite RCA — confidence computation and graceful fallback.

Tests the _compute_overall_confidence pure function and the predict function
with mocked LLM to verify fallback behavior on failure.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.schemas.mtl import AnomalyType, SeverityLevel
from app.services.mtl_lite import _compute_overall_confidence, predict


class TestComputeOverallConfidence:
    """Tests for _compute_overall_confidence — pure math, no mocks."""

    def test_compute_overall_confidence_weighted_average(self) -> None:
        """Confidence is weighted: anomaly=0.25, root_cause=0.35,
        severity=0.15, action=0.25.
        Spec: FS-AI-010 Section 3.3
        """
        prediction = {
            "anomaly_confidence": 0.9,
            "root_cause_confidence": 0.8,
            "severity_score": 0.7,
            "suggested_actions": [
                {"confidence": 0.85},
                {"confidence": 0.75},
            ],
        }

        result = _compute_overall_confidence(prediction)

        # Expected:
        # anomaly: 0.25 * 0.9 = 0.225
        # root_cause: 0.35 * 0.8 = 0.28
        # severity: 0.15 * 0.7 = 0.105
        # action: 0.25 * mean(0.85, 0.75) = 0.25 * 0.80 = 0.20
        # total = 0.225 + 0.28 + 0.105 + 0.20 = 0.81
        assert result == 0.81

    def test_compute_overall_confidence_zero_actions(self) -> None:
        """When no suggested actions exist, action_confidence is 0.0."""
        prediction = {
            "anomaly_confidence": 0.5,
            "root_cause_confidence": 0.5,
            "severity_score": 0.5,
            "suggested_actions": [],
        }

        result = _compute_overall_confidence(prediction)

        # anomaly: 0.25 * 0.5 = 0.125
        # root_cause: 0.35 * 0.5 = 0.175
        # severity: 0.15 * 0.5 = 0.075
        # action: 0.25 * 0.0 = 0.0
        # total = 0.375
        assert result == 0.375

    def test_compute_overall_confidence_all_zeros(self) -> None:
        """All zero confidences produce 0.0 overall."""
        prediction = {
            "anomaly_confidence": 0.0,
            "root_cause_confidence": 0.0,
            "severity_score": 0.0,
            "suggested_actions": [],
        }

        result = _compute_overall_confidence(prediction)
        assert result == 0.0

    def test_compute_overall_confidence_clamped_to_1(self) -> None:
        """Result is clamped to [0.0, 1.0] even if inputs sum > 1.0."""
        prediction = {
            "anomaly_confidence": 1.0,
            "root_cause_confidence": 1.0,
            "severity_score": 1.0,
            "suggested_actions": [{"confidence": 1.0}],
        }

        result = _compute_overall_confidence(prediction)
        assert result == 1.0


class TestPredictGracefulFallback:
    """Tests for predict function falling back on LLM failure."""

    @pytest.mark.asyncio
    async def test_predict_graceful_fallback(self) -> None:
        """When LLM call fails, predict returns a valid fallback response
        with anomaly_type=unknown and a low confidence score.

        Spec: FS-AI-010 Section 3.6 -- fallback has severity_score=0.5
        so overall confidence = 0.15 * 0.5 = 0.075 (all other heads are 0).
        """
        incident_id = uuid4()
        instance_id = uuid4()
        detected = datetime(2026, 3, 25, 10, 0, 0, tzinfo=timezone.utc)

        # Mock _get_llm to return an LLM that raises on invoke
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM service unavailable"))

        with patch("app.services.mtl_lite._get_llm", return_value=mock_llm):
            result = await predict(
                incident_id=incident_id,
                instance_id=instance_id,
                metrics_snapshot="cpu=95%, memory=80%",
                ash_summary="5 active sessions",
                rag_results="No similar past incidents found.",
                detected_at=detected,
            )

        # Verify fallback values
        assert result.anomaly_type == AnomalyType.UNKNOWN
        # Fallback: anomaly_conf=0, root_cause_conf=0, severity_score=0.5, no actions
        # Overall = 0.25*0 + 0.35*0 + 0.15*0.5 + 0.25*0 = 0.075
        assert result.confidence == 0.075
        assert result.root_cause == "AI analysis failed. Manual investigation required."
        assert result.severity == SeverityLevel.NOTICE
        assert result.incident_id == incident_id
        assert result.prediction_id is not None
        assert result.inference_time_ms >= 0
        assert result.model_version == "mtl-lite-v1"
        assert len(result.reasoning_chain) >= 1
        assert len(result.evidence_links) >= 1

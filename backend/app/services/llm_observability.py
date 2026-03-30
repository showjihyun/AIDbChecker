# Spec: FS-AI-013
"""LLM Observability Service — in-memory MVP tracking for LLM calls.

Tracks token usage, latency, cost, hallucination rate, and model drift
for all LLM pipeline calls within NeuralDB.

MVP: In-memory storage (no DB table). Phase 2 will persist to `llm_metrics`.
"""

from __future__ import annotations

import statistics
from collections import deque
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import structlog

from app.schemas.llm_observability import (
    LLMCallRecord,
    LLMObservabilitySummary,
    ModelDriftResult,
)

logger = structlog.get_logger(__name__)

# Spec: FR-AI-013 Section 4.3 — model pricing (approximate)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-5.4": {"input": 0.000015, "output": 0.00006},
    "gpt-4o": {"input": 0.00001, "output": 0.00003},
    "gpt-4o-mini": {"input": 0.00000015, "output": 0.0000006},
    "claude-opus-4-6": {"input": 0.000015, "output": 0.000075},
    "claude-sonnet-4-6": {"input": 0.000003, "output": 0.000015},
    "gemini-3.1-pro": {"input": 0.000007, "output": 0.000021},
    "gemini-2.0-flash": {"input": 0.0000001, "output": 0.0000004},
    "gemini-1.5-pro": {"input": 0.00000125, "output": 0.000005},
    "mistral:7b": {"input": 0.0, "output": 0.0},
    "qwen2.5:14b": {"input": 0.0, "output": 0.0},
}

# Default pricing for unknown models
_DEFAULT_PRICING = {"input": 0.00001, "output": 0.00003}

_MAX_RECORDS = 10_000


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate approximate cost for an LLM call.

    Spec: FR-AI-013 Section 4.3
    """
    pricing = MODEL_PRICING.get(model, _DEFAULT_PRICING)
    return prompt_tokens * pricing["input"] + completion_tokens * pricing["output"]


class LLMObservabilityService:
    """In-memory LLM observability tracker.

    Spec: FS-AI-013 — stores LLMCallRecords in a bounded FIFO deque (max 10k).
    """

    def __init__(self) -> None:
        self._records: deque[LLMCallRecord] = deque(maxlen=_MAX_RECORDS)

    def record_llm_call(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        cost: float | None = None,
        has_hallucination: bool = False,
        is_correct: bool | None = None,
        timestamp: datetime | None = None,
    ) -> LLMCallRecord:
        """Record a single LLM call.

        Spec: FS-AI-013 AC-1
        """
        if cost is None:
            cost = estimate_cost(model, prompt_tokens, completion_tokens)

        record = LLMCallRecord(
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            cost=cost,
            has_hallucination=has_hallucination,
            is_correct=is_correct,
            timestamp=timestamp or datetime.now(UTC),
        )
        self._records.append(record)
        logger.debug(
            "llm_observability.recorded",
            provider=provider,
            model=model,
            tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
        )
        return record

    def _filter_records(
        self,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> list[LLMCallRecord]:
        """Filter records by time range."""
        results = list(self._records)
        if from_ts:
            results = [r for r in results if r.timestamp >= from_ts]
        if to_ts:
            results = [r for r in results if r.timestamp <= to_ts]
        return results

    def get_summary(
        self,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> LLMObservabilitySummary:
        """Aggregate LLM call metrics for the given period.

        Spec: FS-AI-013 AC-2
        """
        records = self._filter_records(from_ts, to_ts)

        if not records:
            return LLMObservabilitySummary(
                total_calls=0,
                total_tokens=0,
                avg_latency_ms=0.0,
                total_cost=0.0,
                hallucination_rate=0.0,
                period_from=from_ts,
                period_to=to_ts,
            )

        total_tokens = sum(r.prompt_tokens + r.completion_tokens for r in records)
        avg_latency = statistics.mean(r.latency_ms for r in records)
        total_cost = sum(r.cost for r in records)
        hallucination_count = sum(1 for r in records if r.has_hallucination)
        hallucination_rate = hallucination_count / len(records)

        return LLMObservabilitySummary(
            total_calls=len(records),
            total_tokens=total_tokens,
            avg_latency_ms=round(avg_latency, 2),
            total_cost=round(total_cost, 6),
            hallucination_rate=round(hallucination_rate, 4),
            period_from=from_ts,
            period_to=to_ts,
        )

    def check_daily_budget(self, daily_limit: int = 500_000) -> bool:
        """Check if daily token budget is exceeded.

        Spec: FS-AI-013 AC-4

        Returns True if budget is exceeded.
        """
        now = datetime.now(UTC)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_records = self._filter_records(from_ts=day_start, to_ts=now)
        total_tokens = sum(r.prompt_tokens + r.completion_tokens for r in today_records)
        exceeded = total_tokens >= daily_limit
        if exceeded:
            logger.warning(
                "llm_observability.daily_budget_exceeded",
                total_tokens=total_tokens,
                daily_limit=daily_limit,
            )
        return exceeded

    def check_weekly_accuracy(self, threshold: float = 0.7) -> bool:
        """Check if weekly RCA accuracy is below threshold.

        Spec: FS-AI-013 AC-5

        Returns True if accuracy is below threshold (alert needed).
        """
        now = datetime.now(UTC)
        week_start = now - timedelta(days=7)
        records = self._filter_records(from_ts=week_start, to_ts=now)

        # Only consider records with feedback
        feedback_records = [r for r in records if r.is_correct is not None]
        if not feedback_records:
            return False  # No feedback yet, no alert

        correct_count = sum(1 for r in feedback_records if r.is_correct)
        accuracy = correct_count / len(feedback_records)
        below_threshold = accuracy < threshold

        if below_threshold:
            logger.warning(
                "llm_observability.weekly_accuracy_low",
                accuracy=round(accuracy, 4),
                threshold=threshold,
                feedback_count=len(feedback_records),
            )
        return below_threshold

    def detect_model_drift(self, window_hours: int = 24) -> ModelDriftResult:
        """Detect model drift by comparing recent vs historical latency/token patterns.

        Spec: FS-AI-013 AC-7

        Uses a simple approach: compare avg latency and avg tokens of the recent
        window against the full historical baseline. Drift score is the normalized
        deviation.
        """
        now = datetime.now(UTC)
        recent_start = now - timedelta(hours=window_hours)

        all_records = list(self._records)
        recent_records = [r for r in all_records if r.timestamp >= recent_start]
        historical_records = [r for r in all_records if r.timestamp < recent_start]

        if len(recent_records) < 2 or len(historical_records) < 2:
            return ModelDriftResult(
                drift_score=0.0,
                is_drifting=False,
                details="Insufficient data for drift detection.",
            )

        # Compare avg latency
        recent_latency = statistics.mean(r.latency_ms for r in recent_records)
        hist_latency = statistics.mean(r.latency_ms for r in historical_records)

        # Compare avg total tokens
        recent_tokens = statistics.mean(
            r.prompt_tokens + r.completion_tokens for r in recent_records
        )
        hist_tokens = statistics.mean(
            r.prompt_tokens + r.completion_tokens for r in historical_records
        )

        # Normalized deviation (0~1 scale, clamped)
        latency_drift = abs(recent_latency - hist_latency) / max(hist_latency, 1.0)
        token_drift = abs(recent_tokens - hist_tokens) / max(hist_tokens, 1.0)

        # Weighted drift score
        drift_score = round(min(0.6 * latency_drift + 0.4 * token_drift, 1.0), 4)
        is_drifting = drift_score > 0.3  # Spec threshold

        details = (
            f"Latency: recent={recent_latency:.0f}ms vs hist={hist_latency:.0f}ms "
            f"(delta={latency_drift:.2%}). "
            f"Tokens: recent={recent_tokens:.0f} vs hist={hist_tokens:.0f} "
            f"(delta={token_drift:.2%})."
        )

        if is_drifting:
            logger.warning(
                "llm_observability.model_drift_detected",
                drift_score=drift_score,
                details=details,
            )

        return ModelDriftResult(
            drift_score=drift_score,
            is_drifting=is_drifting,
            details=details,
        )

    @property
    def record_count(self) -> int:
        """Number of records currently stored."""
        return len(self._records)

    def clear(self) -> None:
        """Clear all records (for testing)."""
        self._records.clear()


# Spec: FS-AI-013 — singleton pattern
@lru_cache(maxsize=1)
def get_observability_service() -> LLMObservabilityService:
    """Return the singleton LLMObservabilityService instance."""
    return LLMObservabilityService()

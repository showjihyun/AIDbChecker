# Spec: FS-AI-013
"""Pydantic schemas for LLM Observability service."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class LLMCallRecord(BaseModel):
    """Single LLM call record stored in-memory."""

    provider: str  # "openai" | "ollama" | "anthropic" | "google"
    model: str  # "gpt-4o" | "mistral:7b"
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    cost: float  # USD
    has_hallucination: bool = False
    is_correct: bool | None = None  # operator feedback
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LLMObservabilitySummary(BaseModel):
    """Aggregated LLM observability summary for a time period."""

    total_calls: int
    total_tokens: int  # prompt + completion
    avg_latency_ms: float
    total_cost: float
    hallucination_rate: float  # 0.0~1.0
    period_from: datetime | None = None
    period_to: datetime | None = None


class ModelDriftResult(BaseModel):
    """Model drift detection result."""

    drift_score: float  # 0.0~1.0
    is_drifting: bool
    details: str

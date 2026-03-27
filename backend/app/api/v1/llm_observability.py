# Spec: FS-AI-013
"""LLM Observability API routes.

Provides endpoints for querying LLM pipeline metrics:
- GET /api/v1/llm-observability/summary — aggregated period summary
- GET /api/v1/llm-observability/drift — model drift detection
- POST /api/v1/llm-observability/record — manual record (testing/integration)
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.schemas.llm_observability import (
    LLMObservabilitySummary,
    ModelDriftResult,
)
from app.services.llm_observability import get_observability_service

router = APIRouter(prefix="/llm-observability", tags=["llm-observability"])


class RecordLLMCallRequest(BaseModel):
    """Request body for manually recording an LLM call."""

    provider: str = "openai"
    model: str = "gpt-4o"
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    cost: float | None = None
    has_hallucination: bool = False
    is_correct: bool | None = None


class RecordLLMCallResponse(BaseModel):
    """Response after recording an LLM call."""

    status: str = "recorded"
    total_records: int


@router.get("/summary", response_model=LLMObservabilitySummary)
async def get_summary(
    from_ts: datetime | None = Query(None, alias="from"),
    to_ts: datetime | None = Query(None, alias="to"),
) -> LLMObservabilitySummary:
    """Get aggregated LLM observability summary for a time period.

    Spec: FS-AI-013 AC-2
    """
    svc = get_observability_service()
    return svc.get_summary(from_ts=from_ts, to_ts=to_ts)


@router.get("/drift", response_model=ModelDriftResult)
async def get_drift(
    window_hours: int = Query(24, ge=1, le=168),
) -> ModelDriftResult:
    """Detect model drift within the specified window.

    Spec: FS-AI-013 AC-7
    """
    svc = get_observability_service()
    return svc.detect_model_drift(window_hours=window_hours)


@router.post("/record", response_model=RecordLLMCallResponse)
async def record_call(body: RecordLLMCallRequest) -> RecordLLMCallResponse:
    """Manually record an LLM call (for testing and integration).

    Spec: FS-AI-013 AC-1
    """
    svc = get_observability_service()
    svc.record_llm_call(
        provider=body.provider,
        model=body.model,
        prompt_tokens=body.prompt_tokens,
        completion_tokens=body.completion_tokens,
        latency_ms=body.latency_ms,
        cost=body.cost,
        has_hallucination=body.has_hallucination,
        is_correct=body.is_correct,
    )
    return RecordLLMCallResponse(status="recorded", total_records=svc.record_count)

# Spec: FS-AI-TUNE-001
"""Pydantic v2 schemas for DB Performance Tuning Agent API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TuningAction(BaseModel):
    """A single recommended tuning action.

    Spec: FS-AI-TUNE-001 Section 4.1
    """

    action_type: Literal[
        "CREATE_INDEX", "VACUUM", "ALTER_SYSTEM",
        "KILL_SESSION", "REWRITE_QUERY", "OTHER",
    ]
    description: str
    sql: str | None = None
    risk_level: Literal["low", "medium", "high"] = "medium"
    estimated_impact: str = ""


class TuningRequest(BaseModel):
    """Request body for POST /api/v1/tuning/analyze.

    Spec: FS-AI-TUNE-001 Section 4.1
    """

    instance_id: UUID
    question: str = Field(..., min_length=3, max_length=2000)
    max_iterations: int = Field(default=5, ge=1, le=10)


class TuningResponse(BaseModel):
    """Response from the tuning agent analysis.

    Spec: FS-AI-TUNE-001 Section 4.1
    """

    instance_id: UUID
    question: str
    analysis: str
    actions: list[TuningAction] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    iterations: int
    model_used: str
    duration_ms: int


class TuningHistoryItem(BaseModel):
    """A single item in the tuning history list.

    Spec: FS-AI-TUNE-001 Section 4.2
    """

    instance_id: UUID
    question: str
    analysis: str
    actions: list[TuningAction] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    model_used: str
    duration_ms: int
    created_at: datetime

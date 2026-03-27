# Spec: FS-DBA-002
"""Pydantic schemas for the unified DBA Agent API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class DBARequest(BaseModel):
    """Spec: FS-DBA-002 §3.2 — unified DBA Agent request."""

    question: str = Field(..., min_length=2, max_length=2000)
    instance_id: UUID
    session_id: UUID | None = Field(
        default=None,
        description="Existing session ID to continue. None starts a new session.",
    )


class ActionSummary(BaseModel):
    """Spec: FS-DBA-002 §3.2 — executable action in response."""

    action_id: UUID | None = None
    action_type: str
    sql: str
    risk_level: str
    status: str  # suggested | pending | executed
    description: str


class DBAResponse(BaseModel):
    """Spec: FS-DBA-002 §3.2 — unified DBA Agent response."""

    session_id: UUID
    intent: str  # analyze | diagnose | execute | query | status
    answer: str
    data: dict | None = None
    actions: list[ActionSummary] | None = None
    model: str = ""
    processing_time_ms: int = 0

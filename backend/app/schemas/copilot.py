# Spec: FS-AI-012
"""Pydantic v2 schemas for DB Copilot (Tree-of-Thought) API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BranchScore(BaseModel):
    """Scoring result for a single ToT branch.

    Spec: FS-AI-012 Section 2.3
    """

    branch_name: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    evidence_strength: float = Field(..., ge=0.0, le=1.0)
    action_confidence: float = Field(..., ge=0.0, le=1.0)
    risk_penalty: float = Field(..., ge=0.0, le=0.5)

    @property
    def final_score(self) -> float:
        """Spec: FS-AI-012 Section 2.3 — weighted score minus risk penalty."""
        base = (
            self.relevance_score * 0.4
            + self.evidence_strength * 0.3
            + self.action_confidence * 0.3
        )
        return round(max(base - self.risk_penalty, 0.0), 3)


class BranchScoreOut(BranchScore):
    """Serializable BranchScore that includes computed final_score."""

    final_score_value: float = Field(
        ..., alias="final_score", description="Computed final score"
    )

    model_config = {"populate_by_name": True}


class CopilotDiagnoseRequest(BaseModel):
    """Request body for POST /api/v1/copilot/diagnose.

    Spec: FS-AI-012 Section 3.1
    """

    instance_id: UUID
    incident_id: UUID | None = None
    max_branches: int = Field(default=4, ge=2, le=8)
    auto_execute: bool = False


class CopilotDiagnoseResponse(BaseModel):
    """Response from Copilot ToT diagnosis.

    Spec: FS-AI-012 Section 3.1
    """

    session_id: UUID
    instance_id: UUID
    branches_explored: int
    selected_branch: str
    branch_scores: list[dict]

    # Lightweight diagnosis summary (reuses MTL output fields)
    anomaly_type: str
    root_cause: str
    severity_score: float = Field(..., ge=0.0, le=1.0)
    suggested_actions: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning_chain: list[str] = Field(default_factory=list)

    # Copilot meta
    total_inference_time_ms: int
    total_tokens_used: int
    autonomy_level_applied: int
    execution_status: str  # recommended | awaiting_approval | executed | blocked


class CopilotSessionItem(BaseModel):
    """A single item in the copilot session history.

    Spec: FS-AI-012 Section 3.2
    """

    session_id: UUID
    instance_id: UUID
    incident_id: UUID | None = None
    branches_explored: int
    selected_branch: str
    confidence: float
    execution_status: str
    autonomy_level_applied: int
    created_at: datetime

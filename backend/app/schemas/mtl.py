# Spec: FR-AI-010, FR-AI-011, FS-AI-010
"""Pydantic v2 schemas for MTL Lite RCA API operations."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class AnomalyType(StrEnum):
    """Anomaly classification types from MTL Head 1."""

    QUERY_PERFORMANCE = "query_performance_degradation"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    LOCK_CONTENTION = "lock_contention"
    REPLICATION_LAG = "replication_lag"
    CONNECTION_SATURATION = "connection_saturation"
    VACUUM_BLOAT = "vacuum_bloat"
    SCHEMA_REGRESSION = "schema_regression"
    SECURITY_ANOMALY = "security_anomaly"
    UNKNOWN = "unknown"


class SeverityLevel(StrEnum):
    """Severity levels from MTL Head 3."""

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    NOTICE = "NOTICE"
    INFO = "INFO"


class ActionRisk(StrEnum):
    """Risk level for suggested actions."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SuggestedAction(BaseModel):
    """A single recommended remediation action from MTL Head 4."""

    action: str = Field(..., description="Executable SQL or config command")
    description: str = Field(..., description="What this does and why")
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk: ActionRisk = ActionRisk.LOW


class RootCauseDetail(BaseModel):
    """Structured root cause information from MTL Head 2."""

    component: str = Field(..., description="query|table|index|parameter|connection|replication")
    identifier: str = Field(..., description="Specific query hash / table name / param name")
    evidence: str = Field(..., description="Key metric or log entry")


class MTLPredictRequest(BaseModel):
    """Request schema for MTL prediction."""

    incident_id: UUID
    instance_id: UUID
    include_reasoning: bool = Field(default=True, description="Include reasoning chain")


class MTLPredictResponse(BaseModel):
    """Response schema for MTL 4-Head prediction result."""

    prediction_id: UUID
    incident_id: UUID
    timestamp: datetime

    # Head 1: Anomaly Classification
    anomaly_type: AnomalyType
    anomaly_confidence: float = Field(..., ge=0.0, le=1.0)

    # Head 2: Root Cause
    root_cause: str
    root_cause_detail: RootCauseDetail | None = None
    root_cause_confidence: float = Field(..., ge=0.0, le=1.0)

    # Head 3: Severity
    severity: SeverityLevel
    severity_score: float = Field(..., ge=0.0, le=1.0)

    # Head 4: Suggested Actions
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)

    # Explainable AI (FS-AI-011)
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    reasoning_chain: list[str] = Field(default_factory=list)
    evidence_links: list[str] = Field(default_factory=list)

    # Meta
    model_version: str
    inference_time_ms: int
    tokens_used: int | None = None

    # Spec: FS-AI-TRACE-001 — ReAct reasoning trace
    trace: dict | None = Field(None, description="ReAct trace (collapsed by default in UI)")

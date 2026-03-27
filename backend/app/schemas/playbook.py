# Spec: FS-AUTO-003 (Lite), DM-001
"""Pydantic v2 schemas for Playbook Lite API operations."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PlaybookTriggerType(StrEnum):
    METRIC_THRESHOLD = "metric_threshold"
    ANOMALY_DETECTION = "anomaly_detection"
    MANUAL = "manual"


class ExecutionStatus(StrEnum):
    BLOCKED = "blocked"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


# --- Playbook info (read-only, loaded from YAML) ---


class PlaybookTrigger(BaseModel):
    type: PlaybookTriggerType
    metric: str | None = None
    condition: str | None = None
    threshold: float | None = None
    duration: str | None = None
    cooldown: str | None = None
    min_confidence: float = 0.5


class PlaybookStep(BaseModel):
    name: str
    type: str = "sql"
    query: str
    timeout: str = "10s"
    save_as: str | None = None
    requires_approval: bool = False


class PlaybookMetadata(BaseModel):
    name: str
    version: str
    description: str
    author: str = "builtin"
    tags: list[str] = []
    min_autonomy_level: int = Field(..., ge=0, le=4)  # Phase 3: L3/L4 개방
    target_db_types: list[str] = ["postgresql"]
    risk_level: RiskLevel


class PlaybookSummary(BaseModel):
    """GET /playbooks list item."""

    name: str
    version: str
    description: str
    risk_level: RiskLevel
    min_autonomy_level: int
    tags: list[str]
    trigger_type: PlaybookTriggerType
    steps_count: int


class PlaybookDetail(BaseModel):
    """GET /playbooks/{name} detail."""

    metadata: PlaybookMetadata
    trigger: PlaybookTrigger
    steps: list[PlaybookStep]
    yaml_content: str


# --- Execution ---


class PlaybookExecuteRequest(BaseModel):
    """POST /playbooks/{name}/execute"""

    instance_id: UUID
    confidence_score: float = Field(0.8, ge=0.0, le=1.0)
    dry_run: bool = False


class StepResult(BaseModel):
    step_name: str
    status: str  # success | failed | skipped
    result: dict | None = None
    error: str | None = None
    duration_ms: int = 0


class PlaybookExecuteResponse(BaseModel):
    """Execution result."""

    execution_id: UUID
    playbook_name: str
    instance_id: UUID
    status: ExecutionStatus
    reason: str | None = None
    steps: list[StepResult] = []
    started_at: datetime
    completed_at: datetime | None = None
    total_duration_ms: int = 0


# --- History ---


class ExecutionHistoryItem(BaseModel):
    execution_id: UUID
    playbook_name: str
    instance_id: UUID
    status: ExecutionStatus
    autonomy_level: int
    confidence_score: float
    started_at: datetime
    completed_at: datetime | None
    total_duration_ms: int


class PlaybookApproveRequest(BaseModel):
    """POST /playbooks/{name}/approve/{log_id}"""

    approved: bool = True
    comment: str | None = None

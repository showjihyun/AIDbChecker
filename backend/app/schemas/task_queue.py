# Spec: FS-AUTO-004, DM-001
"""Pydantic v2 schemas for Task Queue API operations."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task state machine states. Spec: FS-AUTO-004 Section 3."""

    QUEUED = "queued"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    ESCALATED = "escalated"


class TaskTrigger(str, Enum):
    MANUAL = "manual"
    AUTO = "auto"


# --- Request ---


class TaskCreateRequest(BaseModel):
    """POST /tasks — create a new playbook execution task."""

    playbook_name: str = Field(..., description="Built-in Playbook name")
    instance_id: UUID = Field(..., description="Target DB instance")
    trigger: TaskTrigger = TaskTrigger.MANUAL
    confidence_score: float = Field(0.8, ge=0.0, le=1.0)
    params: dict | None = Field(None, description="Playbook parameter overrides")


class TaskApproveRequest(BaseModel):
    """POST /tasks/{id}/approve"""

    comment: str | None = None


class TaskRejectRequest(BaseModel):
    """POST /tasks/{id}/reject"""

    reason: str | None = None


# --- Response ---


class TaskStepLog(BaseModel):
    step_name: str
    status: str
    result: dict | None = None
    error: str | None = None
    duration_ms: int = 0


class TaskResponse(BaseModel):
    """Single task detail."""

    id: UUID
    playbook_name: str
    instance_id: UUID
    trigger: TaskTrigger
    status: TaskStatus
    autonomy_level: int
    confidence_score: float | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_by: UUID | None = None
    execution_log: list[TaskStepLog] = []


class TaskListResponse(BaseModel):
    """GET /tasks list."""

    items: list[TaskResponse]
    total: int

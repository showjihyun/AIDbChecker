# Spec: FS-AUTO-004
"""Spec-Driven tests for Task Queue service (Playbook Task lifecycle).

Feature Spec: docs/specs/services/TASK_QUEUE_SPEC.md
PRD Reference: FR-AUTO-003, FR-AUTO-004
ACs: AC-1 through AC-6

NOTE: The Task Queue service does not exist yet. These tests validate:
  - Expected Pydantic schema contracts (request/response shapes)
  - Status transition logic
  - Conflict detection rules
  - Timeout/cancellation logic

All tests use schema validation and pure logic -- no DB or service calls.
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, Field, ValidationError

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# Expected schemas for the Task Queue API contract (not yet implemented)
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    """Spec: FS-AUTO-004 -- Task lifecycle states."""
    QUEUED = "queued"
    PENDING_APPROVAL = "pending_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CreateTaskRequest(BaseModel):
    """Expected request schema for POST /api/v1/tasks."""
    instance_id: UUID
    playbook_id: UUID
    autonomy_level: int = Field(ge=0, le=4)
    parameters: dict = Field(default_factory=dict)


class CreateTaskResponse(BaseModel):
    """Expected response schema for POST /api/v1/tasks."""
    id: UUID
    instance_id: UUID
    playbook_id: UUID
    status: TaskStatus
    created_at: datetime


class TaskResponse(BaseModel):
    """Expected response schema for GET /api/v1/tasks/{id}."""
    id: UUID
    instance_id: UUID
    playbook_id: UUID
    status: TaskStatus
    autonomy_level: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict | None = None
    error: str | None = None


class TaskListResponse(BaseModel):
    """Expected response for GET /api/v1/tasks."""
    items: list[TaskResponse]
    total: int


# ---------------------------------------------------------------------------
# Task lifecycle logic (pure functions for testing expected behavior)
# ---------------------------------------------------------------------------

def determine_initial_status(autonomy_level: int) -> TaskStatus:
    """Spec: FS-AUTO-004 AC-1/AC-2 -- initial status depends on autonomy level."""
    if autonomy_level <= 1:
        return TaskStatus.PENDING_APPROVAL
    return TaskStatus.QUEUED


def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
    """Valid task status transitions."""
    allowed = {
        TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
        TaskStatus.PENDING_APPROVAL: {TaskStatus.QUEUED, TaskStatus.CANCELLED},
        TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
        TaskStatus.COMPLETED: set(),  # terminal
        TaskStatus.FAILED: set(),  # terminal
        TaskStatus.CANCELLED: set(),  # terminal
    }
    return target in allowed.get(current, set())


def check_conflict(
    existing_tasks: list[dict],
    new_instance_id: UUID,
) -> bool:
    """Spec: FS-AUTO-004 AC-4 -- reject if active task exists for same instance."""
    active_statuses = {TaskStatus.QUEUED, TaskStatus.PENDING_APPROVAL, TaskStatus.RUNNING}
    for task in existing_tasks:
        if (
            task["instance_id"] == new_instance_id
            and TaskStatus(task["status"]) in active_statuses
        ):
            return True  # conflict
    return False


def should_auto_cancel(task: dict, now: datetime) -> bool:
    """Spec: FS-AUTO-004 AC-5 -- cancel if pending_approval > 30 minutes."""
    if TaskStatus(task["status"]) != TaskStatus.PENDING_APPROVAL:
        return False
    created = task["created_at"]
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    return (now - created) > timedelta(minutes=30)


# ---------------------------------------------------------------------------
# AC-1: POST /api/v1/tasks -> status: "queued"
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-004", "AC-1")
def test_fs_auto_004_ac1_create_task_request_schema():
    """CreateTaskRequest validates required fields."""
    req = CreateTaskRequest(
        instance_id=uuid4(),
        playbook_id=uuid4(),
        autonomy_level=2,
    )
    assert req.autonomy_level == 2
    assert req.parameters == {}


@spec_ref("FS-AUTO-004", "AC-1")
def test_fs_auto_004_ac1_create_task_response_has_status():
    """CreateTaskResponse includes status field."""
    resp = CreateTaskResponse(
        id=uuid4(),
        instance_id=uuid4(),
        playbook_id=uuid4(),
        status=TaskStatus.QUEUED,
        created_at=datetime.now(timezone.utc),
    )
    assert resp.status == TaskStatus.QUEUED


@spec_ref("FS-AUTO-004", "AC-1")
def test_fs_auto_004_ac1_l2_initial_status_is_queued():
    """Autonomy L2+ creates task with status='queued'."""
    for level in [2, 3, 4]:
        status = determine_initial_status(level)
        assert status == TaskStatus.QUEUED, f"L{level} should start as 'queued'"


@spec_ref("FS-AUTO-004", "AC-1")
def test_fs_auto_004_ac1_create_request_rejects_invalid_autonomy():
    """CreateTaskRequest rejects autonomy_level outside 0-4."""
    with pytest.raises(ValidationError):
        CreateTaskRequest(
            instance_id=uuid4(),
            playbook_id=uuid4(),
            autonomy_level=5,
        )
    with pytest.raises(ValidationError):
        CreateTaskRequest(
            instance_id=uuid4(),
            playbook_id=uuid4(),
            autonomy_level=-1,
        )


# ---------------------------------------------------------------------------
# AC-2: Autonomy L1 -> pending_approval + WebSocket notification
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-004", "AC-2")
def test_fs_auto_004_ac2_l0_initial_status_pending_approval():
    """L0 creates task with status='pending_approval'."""
    assert determine_initial_status(0) == TaskStatus.PENDING_APPROVAL


@spec_ref("FS-AUTO-004", "AC-2")
def test_fs_auto_004_ac2_l1_initial_status_pending_approval():
    """L1 creates task with status='pending_approval'."""
    assert determine_initial_status(1) == TaskStatus.PENDING_APPROVAL


@spec_ref("FS-AUTO-004", "AC-2")
def test_fs_auto_004_ac2_pending_approval_is_valid_status():
    """TaskStatus enum includes PENDING_APPROVAL."""
    assert TaskStatus.PENDING_APPROVAL.value == "pending_approval"


@spec_ref("FS-AUTO-004", "AC-2")
def test_fs_auto_004_ac2_task_response_schema_accepts_pending():
    """TaskResponse can represent a task in pending_approval status."""
    resp = TaskResponse(
        id=uuid4(),
        instance_id=uuid4(),
        playbook_id=uuid4(),
        status=TaskStatus.PENDING_APPROVAL,
        autonomy_level=1,
        created_at=datetime.now(timezone.utc),
    )
    assert resp.status == TaskStatus.PENDING_APPROVAL
    assert resp.started_at is None


# ---------------------------------------------------------------------------
# AC-3: Approval -> execution -> completed/failed
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-004", "AC-3")
def test_fs_auto_004_ac3_pending_can_transition_to_queued():
    """pending_approval -> queued (after admin approval)."""
    assert can_transition(TaskStatus.PENDING_APPROVAL, TaskStatus.QUEUED)


@spec_ref("FS-AUTO-004", "AC-3")
def test_fs_auto_004_ac3_queued_can_transition_to_running():
    """queued -> running (worker picks up task)."""
    assert can_transition(TaskStatus.QUEUED, TaskStatus.RUNNING)


@spec_ref("FS-AUTO-004", "AC-3")
def test_fs_auto_004_ac3_running_can_complete():
    """running -> completed (successful execution)."""
    assert can_transition(TaskStatus.RUNNING, TaskStatus.COMPLETED)


@spec_ref("FS-AUTO-004", "AC-3")
def test_fs_auto_004_ac3_running_can_fail():
    """running -> failed (execution error)."""
    assert can_transition(TaskStatus.RUNNING, TaskStatus.FAILED)


@spec_ref("FS-AUTO-004", "AC-3")
def test_fs_auto_004_ac3_completed_is_terminal():
    """completed is a terminal state -- no further transitions."""
    for target in TaskStatus:
        if target != TaskStatus.COMPLETED:
            assert not can_transition(TaskStatus.COMPLETED, target)


@spec_ref("FS-AUTO-004", "AC-3")
def test_fs_auto_004_ac3_failed_is_terminal():
    """failed is a terminal state -- no further transitions."""
    for target in TaskStatus:
        if target != TaskStatus.FAILED:
            assert not can_transition(TaskStatus.FAILED, target)


# ---------------------------------------------------------------------------
# AC-4: Same instance concurrent task rejected (409 Conflict)
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-004", "AC-4")
def test_fs_auto_004_ac4_conflict_when_queued_task_exists():
    """Conflict detected when a queued task exists for the same instance."""
    instance_id = uuid4()
    existing = [
        {"instance_id": instance_id, "status": "queued"},
    ]
    assert check_conflict(existing, instance_id) is True


@spec_ref("FS-AUTO-004", "AC-4")
def test_fs_auto_004_ac4_conflict_when_running_task_exists():
    """Conflict detected when a running task exists for the same instance."""
    instance_id = uuid4()
    existing = [
        {"instance_id": instance_id, "status": "running"},
    ]
    assert check_conflict(existing, instance_id) is True


@spec_ref("FS-AUTO-004", "AC-4")
def test_fs_auto_004_ac4_conflict_when_pending_approval_exists():
    """Conflict detected when a pending_approval task exists."""
    instance_id = uuid4()
    existing = [
        {"instance_id": instance_id, "status": "pending_approval"},
    ]
    assert check_conflict(existing, instance_id) is True


@spec_ref("FS-AUTO-004", "AC-4")
def test_fs_auto_004_ac4_no_conflict_when_completed():
    """No conflict when only completed tasks exist for the instance."""
    instance_id = uuid4()
    existing = [
        {"instance_id": instance_id, "status": "completed"},
    ]
    assert check_conflict(existing, instance_id) is False


@spec_ref("FS-AUTO-004", "AC-4")
def test_fs_auto_004_ac4_no_conflict_different_instance():
    """No conflict when active task belongs to a different instance."""
    existing = [
        {"instance_id": uuid4(), "status": "queued"},
    ]
    assert check_conflict(existing, uuid4()) is False


# ---------------------------------------------------------------------------
# AC-5: Approval timeout 30 min -> auto-cancelled
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-004", "AC-5")
def test_fs_auto_004_ac5_cancel_after_30_minutes():
    """Task pending_approval > 30 min is auto-cancelled."""
    now = datetime.now(timezone.utc)
    task = {
        "status": "pending_approval",
        "created_at": now - timedelta(minutes=31),
    }
    assert should_auto_cancel(task, now) is True


@spec_ref("FS-AUTO-004", "AC-5")
def test_fs_auto_004_ac5_not_cancelled_within_30_minutes():
    """Task pending_approval < 30 min is not cancelled."""
    now = datetime.now(timezone.utc)
    task = {
        "status": "pending_approval",
        "created_at": now - timedelta(minutes=29),
    }
    assert should_auto_cancel(task, now) is False


@spec_ref("FS-AUTO-004", "AC-5")
def test_fs_auto_004_ac5_boundary_exactly_30_minutes():
    """Task at exactly 30 min is not cancelled (> 30 required)."""
    now = datetime.now(timezone.utc)
    task = {
        "status": "pending_approval",
        "created_at": now - timedelta(minutes=30),
    }
    assert should_auto_cancel(task, now) is False


@spec_ref("FS-AUTO-004", "AC-5")
def test_fs_auto_004_ac5_non_pending_tasks_not_cancelled():
    """Only pending_approval tasks are subject to timeout cancellation."""
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=2)

    for status in ["queued", "running", "completed", "failed"]:
        task = {"status": status, "created_at": old_time}
        assert should_auto_cancel(task, now) is False, (
            f"Status '{status}' should not be auto-cancelled"
        )


@spec_ref("FS-AUTO-004", "AC-5")
def test_fs_auto_004_ac5_pending_can_transition_to_cancelled():
    """pending_approval -> cancelled is a valid transition."""
    assert can_transition(TaskStatus.PENDING_APPROVAL, TaskStatus.CANCELLED)


# ---------------------------------------------------------------------------
# AC-6: GET /api/v1/tasks with status filter
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-004", "AC-6")
def test_fs_auto_004_ac6_task_list_response_schema():
    """TaskListResponse has items and total fields."""
    resp = TaskListResponse(items=[], total=0)
    assert resp.total == 0
    assert resp.items == []


@spec_ref("FS-AUTO-004", "AC-6")
def test_fs_auto_004_ac6_task_status_enum_values():
    """TaskStatus enum has all expected values for filtering."""
    expected = {"queued", "pending_approval", "running", "completed", "failed", "cancelled"}
    actual = {s.value for s in TaskStatus}
    assert expected == actual


@spec_ref("FS-AUTO-004", "AC-6")
def test_fs_auto_004_ac6_filter_by_status_logic():
    """Status filter selects only matching tasks from a list."""
    tasks = [
        {"id": uuid4(), "status": "queued"},
        {"id": uuid4(), "status": "running"},
        {"id": uuid4(), "status": "completed"},
        {"id": uuid4(), "status": "queued"},
    ]

    queued_tasks = [t for t in tasks if t["status"] == "queued"]
    assert len(queued_tasks) == 2

    running_tasks = [t for t in tasks if t["status"] == "running"]
    assert len(running_tasks) == 1


@spec_ref("FS-AUTO-004", "AC-6")
def test_fs_auto_004_ac6_task_response_includes_all_fields():
    """TaskResponse schema has all fields needed for list display."""
    resp = TaskResponse(
        id=uuid4(),
        instance_id=uuid4(),
        playbook_id=uuid4(),
        status=TaskStatus.COMPLETED,
        autonomy_level=2,
        created_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        result={"actions_executed": 1, "success": True},
        error=None,
    )
    fields = resp.model_fields
    assert "status" in fields
    assert "instance_id" in fields
    assert "result" in fields

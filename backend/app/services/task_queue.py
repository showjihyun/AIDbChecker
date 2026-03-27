# Spec: FS-AUTO-004, FS-AUTO-002, FS-AUTO-003
"""Task Queue Service — manages playbook execution tasks with approval workflow.

In-memory task store for Phase 2. Phase 3 migrates to remediation_logs table.

Features:
- Task creation with Autonomy Gate (L0 reject, L1/L2 pending_approval)
- Concurrency control (1 per instance, 3 global)
- Approval/rejection workflow
- 30-minute approval timeout → auto cancel
- Status filter queries
"""

import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import structlog

from app.schemas.task_queue import (
    TaskResponse,
    TaskStatus,
    TaskStepLog,
    TaskTrigger,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Spec: FS-AUTO-004 Section 6 — concurrency limits
# ---------------------------------------------------------------------------
MAX_CONCURRENT_PER_INSTANCE = 1
MAX_CONCURRENT_GLOBAL = 3
APPROVAL_TIMEOUT_MINUTES = 30

# In-memory store (Phase 2). Phase 3 → remediation_logs table.
_task_store: dict[UUID, TaskResponse] = {}


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def list_tasks(
    *,
    status_filter: TaskStatus | None = None,
    instance_id: UUID | None = None,
    limit: int = 50,
) -> list[TaskResponse]:
    """List tasks with optional filters. Spec: FS-AUTO-004 AC-6."""
    tasks = list(_task_store.values())

    if status_filter:
        tasks = [t for t in tasks if t.status == status_filter]
    if instance_id:
        tasks = [t for t in tasks if t.instance_id == instance_id]

    tasks.sort(key=lambda t: t.created_at, reverse=True)
    return tasks[:limit]


def get_task(task_id: UUID) -> TaskResponse | None:
    """Get single task by ID."""
    return _task_store.get(task_id)


# ---------------------------------------------------------------------------
# Concurrency check
# ---------------------------------------------------------------------------


def _check_concurrency(instance_id: UUID) -> str | None:
    """Check concurrency limits. Returns error message or None.

    Spec: FS-AUTO-004 AC-4, Section 6.
    """
    active_statuses = {
        TaskStatus.QUEUED,
        TaskStatus.PENDING_APPROVAL,
        TaskStatus.APPROVED,
        TaskStatus.RUNNING,
    }

    # Per-instance limit
    instance_active = [
        t for t in _task_store.values()
        if t.instance_id == instance_id and t.status in active_statuses
    ]
    if len(instance_active) >= MAX_CONCURRENT_PER_INSTANCE:
        return f"Instance {instance_id} already has an active task"

    # Global limit
    global_active = [
        t for t in _task_store.values()
        if t.status in active_statuses
    ]
    if len(global_active) >= MAX_CONCURRENT_GLOBAL:
        return "Global concurrent task limit reached (max 3)"

    return None


# ---------------------------------------------------------------------------
# Task creation
# ---------------------------------------------------------------------------


def create_task(
    *,
    playbook_name: str,
    instance_id: UUID,
    trigger: TaskTrigger = TaskTrigger.MANUAL,
    autonomy_level: int,
    confidence_score: float = 0.8,
    created_by: UUID | None = None,
) -> tuple[TaskResponse | None, str | None]:
    """Create a new task. Returns (task, error).

    Spec: FS-AUTO-004 AC-1, AC-2, AC-4.
    """
    # Concurrency check
    conflict = _check_concurrency(instance_id)
    if conflict:
        return None, conflict

    task_id = uuid4()
    now = datetime.now(UTC)

    # Determine initial status based on autonomy level
    # Spec: FS-AUTO-004 Section 5
    if autonomy_level == 0:
        initial_status = TaskStatus.REJECTED
        reason = "L0: monitoring only"
    else:
        # L1 and L2 both go to pending_approval
        initial_status = TaskStatus.PENDING_APPROVAL

    task = TaskResponse(
        id=task_id,
        playbook_name=playbook_name,
        instance_id=instance_id,
        trigger=trigger,
        status=initial_status,
        autonomy_level=autonomy_level,
        confidence_score=confidence_score,
        created_at=now,
        created_by=created_by,
    )

    _task_store[task_id] = task

    logger.info(
        "task.created",
        task_id=str(task_id),
        playbook=playbook_name,
        instance=str(instance_id),
        status=initial_status.value,
        autonomy=autonomy_level,
    )

    return task, None


# ---------------------------------------------------------------------------
# Approval workflow
# ---------------------------------------------------------------------------


def approve_task(task_id: UUID) -> tuple[TaskResponse | None, str | None]:
    """Approve a pending task → run playbook. Spec: FS-AUTO-004 AC-3."""
    task = _task_store.get(task_id)
    if not task:
        return None, "Task not found"

    if task.status != TaskStatus.PENDING_APPROVAL:
        return None, f"Task is '{task.status.value}', not pending_approval"

    # Transition: pending_approval → approved → running → completed
    task.status = TaskStatus.RUNNING
    task.started_at = datetime.now(UTC)

    # Execute playbook (simplified — delegates to playbook_executor)
    try:
        # Mark steps as completed (real execution in Phase 3 integration)
        task.execution_log = [
            TaskStepLog(step_name="approved_execution", status="success", duration_ms=0)
        ]
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC)

    except Exception as exc:
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now(UTC)
        task.execution_log = [
            TaskStepLog(step_name="execution", status="failed", error=str(exc))
        ]
        return task, None

    logger.info("task.approved_and_completed", task_id=str(task_id))
    return task, None


def reject_task(task_id: UUID, reason: str | None = None) -> tuple[TaskResponse | None, str | None]:
    """Reject a pending task. Spec: FS-AUTO-004 AC-3."""
    task = _task_store.get(task_id)
    if not task:
        return None, "Task not found"

    if task.status != TaskStatus.PENDING_APPROVAL:
        return None, f"Task is '{task.status.value}', not pending_approval"

    task.status = TaskStatus.REJECTED
    task.completed_at = datetime.now(UTC)
    logger.info("task.rejected", task_id=str(task_id), reason=reason)
    return task, None


def cancel_task(task_id: UUID) -> tuple[TaskResponse | None, str | None]:
    """Cancel a queued or pending task. Spec: FS-AUTO-004 AC-5."""
    task = _task_store.get(task_id)
    if not task:
        return None, "Task not found"

    cancellable = {TaskStatus.QUEUED, TaskStatus.PENDING_APPROVAL}
    if task.status not in cancellable:
        return None, f"Task is '{task.status.value}', cannot cancel"

    task.status = TaskStatus.CANCELLED
    task.completed_at = datetime.now(UTC)
    logger.info("task.cancelled", task_id=str(task_id))
    return task, None


# ---------------------------------------------------------------------------
# Timeout enforcement
# ---------------------------------------------------------------------------


def expire_stale_tasks() -> int:
    """Cancel pending_approval tasks older than 30 minutes.

    Spec: FS-AUTO-004 AC-5.
    Should be called periodically (e.g., Celery Beat every minute).
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=APPROVAL_TIMEOUT_MINUTES)
    expired = 0

    for task in _task_store.values():
        if task.status == TaskStatus.PENDING_APPROVAL and task.created_at < cutoff:
            task.status = TaskStatus.CANCELLED
            task.completed_at = now
            expired += 1
            logger.info("task.expired", task_id=str(task.id))

    return expired


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def clear_store():
    """Clear in-memory store (for testing)."""
    _task_store.clear()

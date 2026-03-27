# Spec: FS-AUTO-004
"""Task Queue API — create, list, approve, reject, cancel playbook tasks.

POST /tasks           — Create task (Playbook + instance)
GET  /tasks           — List tasks (status/instance filter)
GET  /tasks/{id}      — Task detail
POST /tasks/{id}/approve — Approve pending task
POST /tasks/{id}/reject  — Reject pending task
POST /tasks/{id}/cancel  — Cancel queued/pending task
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.task_queue import (
    TaskApproveRequest,
    TaskCreateRequest,
    TaskListResponse,
    TaskRejectRequest,
    TaskResponse,
    TaskStatus,
)
from app.services import task_queue

logger = structlog.get_logger(__name__)

router = APIRouter()


# Spec: FS-AUTO-004 AC-1
@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin", "db_admin"))],
    summary="Create a playbook execution task",
)
async def create_task(
    body: TaskCreateRequest,
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    """Create a task for playbook execution with Autonomy Gate.

    - L0 → immediately rejected
    - L1/L2 → pending_approval
    - Concurrency: 1 per instance, 3 global
    """
    # Fetch autonomy level from DB
    autonomy_level = 0
    try:
        from sqlalchemy import select

        from app.db.session import AsyncSessionLocal
        from app.models.db_instance import DBInstance

        async with AsyncSessionLocal() as session:
            stmt = select(DBInstance.autonomy_level).where(
                DBInstance.id == body.instance_id
            )
            result = await session.execute(stmt)
            level = result.scalar()
            if level is not None:
                autonomy_level = level
    except Exception:
        logger.warning("task.autonomy_lookup_failed", instance=str(body.instance_id))

    task, error = task_queue.create_task(
        playbook_name=body.playbook_name,
        instance_id=body.instance_id,
        trigger=body.trigger,
        autonomy_level=autonomy_level,
        confidence_score=body.confidence_score,
        created_by=current_user.id,
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error,
        )

    return task


# Spec: FS-AUTO-004 AC-6
@router.get(
    "/tasks",
    response_model=TaskListResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="List tasks with optional filters",
)
async def list_tasks(
    task_status: TaskStatus | None = Query(None, alias="status"),
    instance_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> TaskListResponse:
    """List playbook tasks. Filter by status and/or instance."""
    tasks = task_queue.list_tasks(
        status_filter=task_status,
        instance_id=instance_id,
        limit=limit,
    )
    return TaskListResponse(items=tasks, total=len(tasks))


# Spec: FS-AUTO-004 AC-3
@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Get task detail",
)
async def get_task(task_id: UUID) -> TaskResponse:
    """Get a single task with execution logs."""
    task = task_queue.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return task


# Spec: FS-AUTO-004 AC-3
@router.post(
    "/tasks/{task_id}/approve",
    response_model=TaskResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin"))],
    summary="Approve a pending task",
)
async def approve_task(
    task_id: UUID,
    body: TaskApproveRequest | None = None,
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    """Approve a pending_approval task → execute playbook."""
    task, error = task_queue.approve_task(task_id)
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )
    logger.info("task.approved_via_api", task_id=str(task_id), user=current_user.email)
    return task


# Spec: FS-AUTO-004 AC-3
@router.post(
    "/tasks/{task_id}/reject",
    response_model=TaskResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin"))],
    summary="Reject a pending task",
)
async def reject_task(
    task_id: UUID,
    body: TaskRejectRequest | None = None,
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    """Reject a pending_approval task."""
    reason = body.reason if body else None
    task, error = task_queue.reject_task(task_id, reason)
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )
    return task


# Spec: FS-AUTO-004 AC-5
@router.post(
    "/tasks/{task_id}/cancel",
    response_model=TaskResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Cancel a queued or pending task",
)
async def cancel_task(task_id: UUID) -> TaskResponse:
    """Cancel a task in queued or pending_approval state."""
    task, error = task_queue.cancel_task(task_id)
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )
    return task

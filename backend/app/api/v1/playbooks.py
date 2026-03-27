# Spec: FS-AUTO-003 (Lite)
"""Playbook Lite API — list, detail, execute, and approve built-in playbooks.

GET  /playbooks              — List all 7 built-in playbooks
GET  /playbooks/{name}       — Get playbook detail with YAML
POST /playbooks/{name}/execute — Execute a playbook on an instance
GET  /playbooks/{name}/history — Execution history (stub)
POST /playbooks/{name}/approve/{log_id} — Approve pending execution (stub)
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.playbook import (
    PlaybookDetail,
    PlaybookExecuteRequest,
    PlaybookExecuteResponse,
    PlaybookSummary,
)
from app.services import playbook_executor

logger = structlog.get_logger(__name__)

router = APIRouter()


# Spec: FS-AUTO-003 AC-1, AC-2
@router.get(
    "/playbooks",
    response_model=list[PlaybookSummary],
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="List all built-in playbooks",
)
async def list_playbooks() -> list[PlaybookSummary]:
    """Return all 7 built-in playbook summaries."""
    return playbook_executor.list_playbooks()


# Spec: FS-AUTO-003 AC-2
@router.get(
    "/playbooks/{name}",
    response_model=PlaybookDetail,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Get playbook detail with YAML content",
)
async def get_playbook(name: str) -> PlaybookDetail:
    """Get a single built-in playbook by name, including raw YAML."""
    pb = playbook_executor.get_playbook(name)
    if not pb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Playbook '{name}' not found. "
            "Use GET /playbooks to see available playbooks.",
        )
    return pb


# Spec: FS-AUTO-003 AC-3, AC-4, AC-5
@router.post(
    "/playbooks/{name}/execute",
    response_model=PlaybookExecuteResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin"))],
    summary="Execute a built-in playbook on an instance",
)
async def execute_playbook(
    name: str,
    body: PlaybookExecuteRequest,
    current_user: User = Depends(get_current_user),
) -> PlaybookExecuteResponse:
    """Execute a built-in playbook with Autonomy + Confidence gates.

    - Confidence < min_confidence → blocked
    - Autonomy L0 → blocked (monitoring only)
    - Autonomy L1 + requires L2 → pending_approval
    - Autonomy L2 → execute after approval
    - dry_run=true → simulate without SQL execution
    """
    # Fetch instance autonomy level
    # For now, use a default. In production, query db_instances table.
    from sqlalchemy import select
    from app.api.deps import get_session
    from app.models.db_instance import DBInstance

    # Simplified: we need the instance's autonomy level
    # In a real implementation, inject session via Depends
    autonomy_level = 0  # default safe

    try:
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            stmt = select(DBInstance.autonomy_level).where(
                DBInstance.id == body.instance_id
            )
            result = await session.execute(stmt)
            level = result.scalar()
            if level is not None:
                autonomy_level = level
    except Exception:
        logger.warning("playbook.autonomy_lookup_failed", instance_id=str(body.instance_id))

    logger.info(
        "playbook.execute_requested",
        playbook=name,
        instance_id=str(body.instance_id),
        autonomy_level=autonomy_level,
        confidence=body.confidence_score,
        dry_run=body.dry_run,
        user=current_user.email,
    )

    result = await playbook_executor.execute_playbook(
        playbook_name=name,
        instance_id=body.instance_id,
        autonomy_level=autonomy_level,
        confidence_score=body.confidence_score,
        dry_run=body.dry_run,
    )

    return result

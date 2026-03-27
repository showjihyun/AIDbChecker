# Spec: FS-AUTO-003 (Lite + Phase 3 Custom)
"""Playbook API — list, detail, execute built-in + custom playbooks.

GET  /playbooks              — List all playbooks (built-in + custom)
GET  /playbooks/{name}       — Get playbook detail with YAML
POST /playbooks/{name}/execute — Execute a playbook on an instance
POST /playbooks              — Create custom playbook (Phase 3)
PUT  /playbooks/{name}       — Update custom playbook (Phase 3)
DELETE /playbooks/{name}     — Delete custom playbook (Phase 3)
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

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
            detail=f"Playbook '{name}' not found. Use GET /playbooks to see available playbooks.",
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

    from app.models.db_instance import DBInstance

    # Simplified: we need the instance's autonomy level
    # In a real implementation, inject session via Depends
    autonomy_level = 0  # default safe

    try:
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            stmt = select(DBInstance.autonomy_level).where(DBInstance.id == body.instance_id)
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


# ---------------------------------------------------------------------------
# Phase 3: Custom Playbook CRUD
# Spec: FS-AUTO-003 Phase 3
# ---------------------------------------------------------------------------


class CustomPlaybookRequest(BaseModel):
    yaml_content: str = Field(..., min_length=10, description="Full YAML content")


class CustomPlaybookResponse(BaseModel):
    name: str
    status: str


@router.post(
    "/playbooks",
    response_model=CustomPlaybookResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin", "db_admin"))],
    summary="Create a custom playbook (Phase 3)",
)
async def create_custom_playbook(
    body: CustomPlaybookRequest,
) -> CustomPlaybookResponse:
    """Upload a custom playbook YAML."""
    name, error = playbook_executor.create_custom_playbook(body.yaml_content)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    return CustomPlaybookResponse(name=name, status="created")


@router.put(
    "/playbooks/{name}",
    response_model=CustomPlaybookResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin"))],
    summary="Update a custom playbook (Phase 3)",
)
async def update_custom_playbook(
    name: str,
    body: CustomPlaybookRequest,
) -> CustomPlaybookResponse:
    """Update an existing custom playbook YAML."""
    ok, error = playbook_executor.update_custom_playbook(name, body.yaml_content)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    return CustomPlaybookResponse(name=name, status="updated")


@router.delete(
    "/playbooks/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("super_admin", "db_admin"))],
    summary="Delete a custom playbook (Phase 3)",
)
async def delete_custom_playbook(name: str):
    """Delete a custom playbook."""
    ok, error = playbook_executor.delete_custom_playbook(name)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

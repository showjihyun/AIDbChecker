# Spec: FS-AI-012
"""Copilot API — Tree-of-Thought DB diagnosis.

POST /api/v1/copilot/diagnose — run ToT diagnosis
GET  /api/v1/copilot/sessions — session history (in-memory for MVP)

Spec: FS-AI-012 Section 3.1
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.copilot_agent import DBCopilotAgent
from app.api.deps import get_session, require_role
from app.models.db_instance import DBInstance
from app.schemas.copilot import (
    CopilotDiagnoseRequest,
    CopilotDiagnoseResponse,
    CopilotSessionItem,
)
from app.services.llm_provider import get_llm_manager

logger = structlog.get_logger(__name__)

router = APIRouter()

# Spec: FS-AI-012 Section 3.2 — in-memory session store for MVP
_sessions: list[CopilotSessionItem] = []
_MAX_SESSIONS = 100


# ---------------------------------------------------------------------------
# POST /api/v1/copilot/diagnose
# ---------------------------------------------------------------------------


@router.post(
    "/copilot/diagnose",
    response_model=CopilotDiagnoseResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin"))],
    summary="Run Tree-of-Thought DB diagnosis",
    description=(
        "Explores multiple diagnostic branches using Tree-of-Thought reasoning, "
        "scores each branch, and returns the best diagnosis path. "
        "Spec: FS-AI-012"
    ),
)
async def diagnose_copilot(
    body: CopilotDiagnoseRequest,
    session: AsyncSession = Depends(get_session),
) -> CopilotDiagnoseResponse:
    """Run Copilot ToT diagnosis on a target DB instance.

    Spec: FS-AI-012 Section 3.1
    """
    # 1. Resolve instance
    stmt = select(DBInstance).where(
        DBInstance.id == body.instance_id,
        DBInstance.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    instance = result.scalar_one_or_none()

    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance {body.instance_id} not found. Verify the ID is correct.",
        )

    # 2. Get LLM
    try:
        llm = get_llm_manager().get_llm(
            temperature=0.1,
            max_tokens=2000,
            request_timeout=60,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No LLM provider available: {exc}",
        )

    # 3. Run Copilot agent
    agent = DBCopilotAgent(llm=llm)
    response = await agent.diagnose(
        instance_id=body.instance_id,
        incident_id=body.incident_id,
        max_branches=body.max_branches,
        autonomy_level=instance.autonomy_level,
        auto_execute=body.auto_execute,
    )

    # 4. Store session in history
    _sessions.append(
        CopilotSessionItem(
            session_id=response.session_id,
            instance_id=response.instance_id,
            incident_id=body.incident_id,
            branches_explored=response.branches_explored,
            selected_branch=response.selected_branch,
            confidence=response.confidence,
            execution_status=response.execution_status,
            autonomy_level_applied=response.autonomy_level_applied,
            created_at=datetime.now(UTC),
        )
    )
    while len(_sessions) > _MAX_SESSIONS:
        _sessions.pop(0)

    return response


# ---------------------------------------------------------------------------
# GET /api/v1/copilot/sessions
# ---------------------------------------------------------------------------


@router.get(
    "/copilot/sessions",
    response_model=list[CopilotSessionItem],
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Get Copilot session history",
    description="Returns past Copilot diagnoses stored in memory (MVP). Spec: FS-AI-012 AC-6",
)
async def get_copilot_sessions(
    instance_id: UUID | None = Query(default=None, description="Filter by instance"),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[CopilotSessionItem]:
    """Return copilot session history.

    Spec: FS-AI-012 Section 3.2
    """
    items = _sessions
    if instance_id is not None:
        items = [s for s in items if s.instance_id == instance_id]
    return list(reversed(items[-limit:]))

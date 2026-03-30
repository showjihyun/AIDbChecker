# Spec: FS-DBA-002
"""Unified DBA Agent API — single endpoint for all DBA operations."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session, require_role
from app.models.user import User
from app.schemas.dba import DBARequest, DBAResponse

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post(
    "/dba/ask",
    response_model=DBAResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Ask the DBA Agent",
    description="Unified DBA Agent interface. Routes to Tuning, Copilot, "
    "Execution, NL2SQL, or Health based on intent classification.",
)
async def ask_dba(
    body: DBARequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DBAResponse:
    """Spec: FS-DBA-002 AC-1 — POST /api/v1/dba/ask."""
    from sqlalchemy import select

    from app.agents.dba_agent import DBAAgent
    from app.models.db_instance import DBInstance

    # Verify instance exists
    stmt = select(DBInstance).where(
        DBInstance.id == body.instance_id,
        DBInstance.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DB instance {body.instance_id} not found.",
        )

    # Get target DB pool
    pool = None
    try:
        import asyncpg

        from app.utils.dsn import build_target_dsn

        dsn = build_target_dsn(instance)
        pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=2,
            command_timeout=10,
            server_settings={"statement_timeout": "10000"},
        )
    except Exception as exc:
        logger.warning(
            "dba.pool_failed",
            instance_id=str(body.instance_id),
            error=str(exc),
        )

    try:
        agent = DBAAgent()
        response = await agent.ask(
            question=body.question,
            instance_id=body.instance_id,
            session=session,
            pool=pool,
            autonomy_level=instance.autonomy_level,
            user_id=str(current_user.id),
            user_role=current_user.role,
        )
        return response
    finally:
        if pool:
            await pool.close()


class FeedbackRequest(BaseModel):
    """AC-20: DBA Agent feedback."""

    session_id: str
    message_id: str | None = None
    feedback: str  # "positive" | "negative"
    question: str | None = None
    intent: str | None = None


@router.post(
    "/dba/feedback",
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Submit feedback on DBA Agent response",
)
async def submit_feedback(
    body: FeedbackRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """AC-19/20: Record user feedback on DBA Agent answers."""
    try:
        from app.utils.ai_logger import create_ai_decision_log

        await create_ai_decision_log(
            session,
            resource_type="dba_feedback",
            user_id=str(current_user.id),
            details={
                "session_id": body.session_id,
                "message_id": body.message_id,
                "feedback": body.feedback,
                "question": body.question,
                "intent": body.intent,
            },
        )
        await session.commit()
    except Exception as exc:
        logger.warning("dba.feedback_failed", error=str(exc))

    return {"status": "recorded", "feedback": body.feedback}

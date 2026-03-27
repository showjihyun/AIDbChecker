# Spec: FS-AI-TUNE-001
"""Tuning Agent API — ReAct-based DB performance analysis.

POST /api/v1/tuning/analyze — run the tuning agent on a target DB instance
GET  /api/v1/tuning/history — retrieve past analysis results (in-memory for MVP)

The agent creates a read-only asyncpg pool to the target DB, uses 7 diagnostic
tools, and returns structured recommendations.  Pool caching follows the same
pattern as the KPI endpoint (_kpi_adapter_cache in kpi.py).
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tuning_agent import DBTuningAgent
from app.api.deps import get_session, require_role
from app.models.db_instance import DBInstance
from app.schemas.tuning import TuningHistoryItem, TuningRequest, TuningResponse
from app.services.llm_provider import get_llm_manager
from app.utils.dsn import build_target_dsn

logger = structlog.get_logger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Pool cache — same pattern as kpi.py:_kpi_adapter_cache
# ---------------------------------------------------------------------------
_tuning_pool_cache: dict[UUID, tuple[asyncpg.Pool, str]] = {}

# Spec: FS-AI-TUNE-001 Section 4.2 — in-memory history for MVP (no new table)
_history: list[TuningHistoryItem] = []
_MAX_HISTORY = 100


async def _get_tuning_pool(instance: DBInstance) -> asyncpg.Pool:
    """Get or create a cached asyncpg pool for tuning analysis.

    Spec: FS-AI-TUNE-001 Section 5 — read-only, statement_timeout=5s
    """
    dsn = build_target_dsn(instance)

    if instance.id in _tuning_pool_cache:
        cached_pool, cached_dsn = _tuning_pool_cache[instance.id]
        if cached_dsn == dsn and not cached_pool._closed:
            return cached_pool
        # DSN changed or pool closed — clean up
        with contextlib.suppress(Exception):
            cached_pool.terminate()
        del _tuning_pool_cache[instance.id]

    pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=2,
        command_timeout=10,
        server_settings={
            "statement_timeout": "5000",
            "default_transaction_read_only": "on",
        },
    )
    _tuning_pool_cache[instance.id] = (pool, dsn)
    return pool


# ---------------------------------------------------------------------------
# POST /api/v1/tuning/analyze
# ---------------------------------------------------------------------------


@router.post(
    "/tuning/analyze",
    response_model=TuningResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin"))],
    summary="Run DB performance tuning analysis",
    description=(
        "Uses a LangChain ReAct agent with 7 PostgreSQL diagnostic tools "
        "to analyse the target DB and recommend tuning actions.  "
        "All queries are read-only with a 5-second timeout."
    ),
)
async def analyze_tuning(
    body: TuningRequest,
    session: AsyncSession = Depends(get_session),
) -> TuningResponse:
    """Run the tuning agent on a target DB instance.

    Spec: FS-AI-TUNE-001 Section 4.1
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

    if instance.db_type != "postgresql":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Tuning agent currently supports PostgreSQL only. "
                f"Instance '{instance.name}' is '{instance.db_type}'."
            ),
        )

    # 2. Get target DB pool (read-only)
    try:
        pool = await _get_tuning_pool(instance)
    except (asyncpg.PostgresError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to target DB: {exc}",
        )

    # 3. Get LLM via LLMProviderManager
    # Spec: FS-AI-TUNE-001 AC-7 — uses LLMProviderManager
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

    # 4. Run agent
    agent = DBTuningAgent(llm=llm, pool=pool)
    response = await agent.analyze(
        question=body.question,
        instance_id=body.instance_id,
        max_iterations=body.max_iterations,
    )

    # 5. Store in history
    _history.append(
        TuningHistoryItem(
            instance_id=response.instance_id,
            question=response.question,
            analysis=response.analysis,
            actions=response.actions,
            tools_used=response.tools_used,
            model_used=response.model_used,
            duration_ms=response.duration_ms,
            created_at=datetime.now(UTC),
        )
    )
    # Cap history size
    while len(_history) > _MAX_HISTORY:
        _history.pop(0)

    return response


# ---------------------------------------------------------------------------
# GET /api/v1/tuning/history
# ---------------------------------------------------------------------------


@router.get(
    "/tuning/history",
    response_model=list[TuningHistoryItem],
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Get tuning analysis history",
    description="Returns past tuning analyses stored in memory (MVP — no persistent table).",
)
async def get_tuning_history(
    instance_id: UUID | None = Query(default=None, description="Filter by instance"),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[TuningHistoryItem]:
    """Return tuning analysis history.

    Spec: FS-AI-TUNE-001 Section 4.2
    """
    items = _history
    if instance_id is not None:
        items = [h for h in items if h.instance_id == instance_id]
    # Return most recent first
    return list(reversed(items[-limit:]))

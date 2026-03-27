# Spec: DM-001, MVP-DASH-003
"""ASH API — Active Session History queries, heatmap, wait-event breakdown."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.active_session import ActiveSession
from app.models.db_instance import DBInstance
from app.schemas.ash import (
    ASHHeatmapResponse,
    ASHSessionListResponse,
    ASHSessionResponse,
    ASHWaitBreakdownResponse,
    HeatmapBucket,
    WaitBreakdownItem,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get(
    "/instances/{instance_id}/ash",
    response_model=ASHSessionListResponse,
)
async def get_ash_sessions(
    instance_id: UUID,
    from_ts: datetime | None = Query(default=None, description="Start time (inclusive)"),
    to_ts: datetime | None = Query(default=None, description="End time (exclusive)"),
    state: str | None = Query(default=None, description="Filter by session state"),
    cursor: str | None = Query(default=None, description="Cursor: sampled_at ISO string"),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> ASHSessionListResponse:
    """Query active session samples with time range and cursor pagination."""
    await _verify_instance(session, instance_id)

    stmt = (
        select(ActiveSession)
        .where(ActiveSession.instance_id == instance_id)
        .order_by(desc(ActiveSession.sampled_at))
    )

    if from_ts is not None:
        stmt = stmt.where(ActiveSession.sampled_at >= from_ts)
    if to_ts is not None:
        stmt = stmt.where(ActiveSession.sampled_at < to_ts)
    if state is not None:
        stmt = stmt.where(ActiveSession.state == state)
    if cursor is not None:
        cursor_dt = datetime.fromisoformat(cursor)
        stmt = stmt.where(ActiveSession.sampled_at < cursor_dt)

    stmt = stmt.limit(limit + 1)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]

    next_cursor = None
    if has_more and items:
        next_cursor = items[-1].sampled_at.isoformat()

    return ASHSessionListResponse(
        items=[
            ASHSessionResponse(
                id=s.id,
                instance_id=s.instance_id,
                sampled_at=s.sampled_at,
                pid=s.pid,
                query=s.query,
                query_hash=s.query_hash,
                state=s.state,
                wait_event_type=s.wait_event_type,
                wait_event=s.wait_event,
                backend_type=s.backend_type,
                client_addr=s.client_addr,
                application_name=s.application_name,
                query_start=s.query_start,
                duration_ms=s.duration_ms,
            )
            for s in items
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get(
    "/instances/{instance_id}/ash/heatmap",
    response_model=ASHHeatmapResponse,
)
async def get_ash_heatmap(
    instance_id: UUID,
    from_ts: datetime | None = Query(default=None),
    to_ts: datetime | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ASHHeatmapResponse:
    """ASH heatmap — aggregate sessions by wait_event_type in 10-second buckets.

    Uses date_trunc + modular arithmetic for 10-second bucketing
    (no TimescaleDB time_bucket — Spec: ADR-002).
    """
    await _verify_instance(session, instance_id)

    # Default: last 10 minutes
    if to_ts is None:
        to_ts = datetime.now(UTC)
    if from_ts is None:
        from_ts = to_ts - timedelta(minutes=10)

    # Spec: ADR-002 — use date_trunc + modular arithmetic, NOT time_bucket
    from sqlalchemy import literal_column  # noqa: E402 — needed here for label() support

    bucket_expr = literal_column(
        "date_trunc('second', sampled_at) "
        "- (EXTRACT(SECOND FROM sampled_at)::int % 10) * INTERVAL '1 second'"
    )

    stmt = (
        select(
            bucket_expr.label("bucket_start"),
            func.coalesce(ActiveSession.wait_event_type, literal_column("'CPU'")).label(
                "wait_event_type"
            ),
            func.count().label("cnt"),
        )
        .where(
            ActiveSession.instance_id == instance_id,
            ActiveSession.sampled_at >= from_ts,
            ActiveSession.sampled_at < to_ts,
        )
        .group_by(literal_column("1"), literal_column("2"))
        .order_by(literal_column("1"))
    )

    result = await session.execute(stmt)
    rows = result.all()

    buckets = [
        HeatmapBucket(
            bucket_start=row.bucket_start,
            wait_event_type=row.wait_event_type,
            count=row.cnt,
        )
        for row in rows
    ]

    return ASHHeatmapResponse(
        instance_id=instance_id,
        buckets=buckets,
        bucket_interval_seconds=10,
    )


@router.get(
    "/instances/{instance_id}/ash/wait-breakdown",
    response_model=ASHWaitBreakdownResponse,
)
async def get_wait_breakdown(
    instance_id: UUID,
    from_ts: datetime | None = Query(default=None),
    to_ts: datetime | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ASHWaitBreakdownResponse:
    """Wait event type breakdown — count and percentage distribution."""
    await _verify_instance(session, instance_id)

    if to_ts is None:
        to_ts = datetime.now(UTC)
    if from_ts is None:
        from_ts = to_ts - timedelta(minutes=10)

    stmt = (
        select(
            func.coalesce(ActiveSession.wait_event_type, "CPU").label("wait_event_type"),
            func.count().label("cnt"),
        )
        .where(
            ActiveSession.instance_id == instance_id,
            ActiveSession.sampled_at >= from_ts,
            ActiveSession.sampled_at < to_ts,
        )
        .group_by(text("wait_event_type"))
        .order_by(desc("cnt"))
    )

    result = await session.execute(stmt)
    rows = result.all()

    total_samples = sum(row.cnt for row in rows)
    breakdown = [
        WaitBreakdownItem(
            wait_event_type=row.wait_event_type,
            count=row.cnt,
            percentage=round((row.cnt / total_samples) * 100, 2) if total_samples > 0 else 0.0,
        )
        for row in rows
    ]

    return ASHWaitBreakdownResponse(
        instance_id=instance_id,
        total_samples=total_samples,
        breakdown=breakdown,
    )


async def _verify_instance(session: AsyncSession, instance_id: UUID) -> None:
    """Raise 404 if the instance does not exist or is deleted."""
    stmt = select(DBInstance.id).where(
        DBInstance.id == instance_id,
        DBInstance.deleted_at.is_(None),
    )
    exists = (await session.execute(stmt)).scalar_one_or_none()
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance {instance_id} not found. Verify the ID is correct.",
        )

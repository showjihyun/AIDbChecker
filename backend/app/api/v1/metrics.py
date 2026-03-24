# Spec: DM-001, MVP-COLLECT-001
"""Metrics API — query metric_samples with time range and cursor pagination."""

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.metric import MetricSample
from app.models.db_instance import DBInstance
from app.schemas.metric import (
    MetricLatestResponse,
    MetricListResponse,
    MetricResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get(
    "/instances/{instance_id}/metrics",
    response_model=MetricListResponse,
)
async def get_metrics(
    instance_id: UUID,
    from_ts: datetime | None = Query(default=None, description="Start time (inclusive)"),
    to_ts: datetime | None = Query(default=None, description="End time (exclusive)"),
    category: str | None = Query(default=None, pattern=r"^(hot|warm|cold)$"),
    cursor: str | None = Query(default=None, description="Cursor: sampled_at ISO string"),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> MetricListResponse:
    """Query metric samples with time range and cursor-based pagination.

    Cursor pagination: pass the `next_cursor` from a previous response
    to fetch the next page. Results are ordered by sampled_at DESC.
    """
    # Verify instance exists
    await _verify_instance(session, instance_id)

    # Spec: DM-001 — cursor-based pagination (no OFFSET)
    stmt = (
        select(MetricSample)
        .where(MetricSample.instance_id == instance_id)
        .order_by(desc(MetricSample.sampled_at))
    )

    if from_ts is not None:
        stmt = stmt.where(MetricSample.sampled_at >= from_ts)
    if to_ts is not None:
        stmt = stmt.where(MetricSample.sampled_at < to_ts)
    if category is not None:
        stmt = stmt.where(MetricSample.category == category)
    if cursor is not None:
        cursor_dt = datetime.fromisoformat(cursor)
        stmt = stmt.where(MetricSample.sampled_at < cursor_dt)

    # Fetch limit+1 to detect has_more
    stmt = stmt.limit(limit + 1)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]

    next_cursor = None
    if has_more and items:
        next_cursor = items[-1].sampled_at.isoformat()

    return MetricListResponse(
        items=[
            MetricResponse(
                id=m.id,
                instance_id=m.instance_id,
                sampled_at=m.sampled_at,
                category=m.category,
                metrics=m.metrics,
            )
            for m in items
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get(
    "/instances/{instance_id}/metrics/latest",
    response_model=MetricLatestResponse,
)
async def get_latest_metrics(
    instance_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> MetricLatestResponse:
    """Get the latest metric snapshot per category for an instance."""
    await _verify_instance(session, instance_id)

    result = MetricLatestResponse(instance_id=instance_id)

    for category in ("hot", "warm", "cold"):
        stmt = (
            select(MetricSample)
            .where(
                MetricSample.instance_id == instance_id,
                MetricSample.category == category,
            )
            .order_by(desc(MetricSample.sampled_at))
            .limit(1)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is not None:
            resp = MetricResponse(
                id=row.id,
                instance_id=row.instance_id,
                sampled_at=row.sampled_at,
                category=row.category,
                metrics=row.metrics,
            )
            setattr(result, category, resp)

    return result


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

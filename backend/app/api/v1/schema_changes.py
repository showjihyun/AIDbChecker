# Spec: FS-SCHEMA-001, MVP-SCHEMA-002
"""Schema Changes API — list detected DDL changes for a monitored instance."""

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.db_instance import DBInstance
from app.models.schema_change import SchemaChange
from app.schemas.schema_change import SchemaChangeListResponse, SchemaChangeResponse

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get(
    "/instances/{instance_id}/schema-changes",
    response_model=SchemaChangeListResponse,
)
async def list_schema_changes(
    instance_id: UUID,
    from_ts: datetime | None = Query(default=None, description="Start time (inclusive)"),
    to_ts: datetime | None = Query(default=None, description="End time (exclusive)"),
    change_type: str | None = Query(default=None, description="Filter: CREATE/ALTER/DROP"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> SchemaChangeListResponse:
    """List schema changes for a specific DB instance, ordered by detected_at DESC.

    Spec: FS-SCHEMA-001 §3 — GET /api/v1/instances/{id}/schema-changes
    """
    # Verify instance exists
    inst_stmt = select(DBInstance.id).where(
        DBInstance.id == instance_id,
        DBInstance.deleted_at.is_(None),
    )
    exists = (await session.execute(inst_stmt)).scalar_one_or_none()
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance {instance_id} not found. Verify the ID is correct.",
        )

    # Build query
    stmt = (
        select(SchemaChange)
        .where(SchemaChange.instance_id == instance_id)
        .order_by(desc(SchemaChange.detected_at))
    )

    count_stmt = (
        select(func.count())
        .select_from(SchemaChange)
        .where(SchemaChange.instance_id == instance_id)
    )

    # Optional filters
    if from_ts is not None:
        stmt = stmt.where(SchemaChange.detected_at >= from_ts)
        count_stmt = count_stmt.where(SchemaChange.detected_at >= from_ts)
    if to_ts is not None:
        stmt = stmt.where(SchemaChange.detected_at < to_ts)
        count_stmt = count_stmt.where(SchemaChange.detected_at < to_ts)
    if change_type is not None:
        stmt = stmt.where(SchemaChange.change_type == change_type.upper())
        count_stmt = count_stmt.where(SchemaChange.change_type == change_type.upper())

    # Pagination
    stmt = stmt.offset(offset).limit(limit)

    total = (await session.execute(count_stmt)).scalar_one()
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    return SchemaChangeListResponse(
        items=[
            SchemaChangeResponse(
                id=row.id,
                instance_id=row.instance_id,
                change_type=row.change_type,
                object_type=row.object_type,
                object_name=row.object_name,
                ddl_command=row.ddl_command,
                before_state=row.before_state,
                after_state=row.after_state,
                executed_by=row.executed_by,
                detected_at=row.detected_at,
                created_at=row.created_at,
            )
            for row in rows
        ],
        total=total,
    )

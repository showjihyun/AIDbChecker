# Spec: FS-ADMIN-003
"""Audit log query endpoint -- super_admin only."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_role
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogListResponse, AuditLogResponse

router = APIRouter()


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    dependencies=[Depends(require_role("super_admin"))],
)
async def list_audit_logs(
    session: AsyncSession = Depends(get_session),
    user_id: UUID | None = Query(default=None, description="Filter by actor user ID"),
    resource_type: str | None = Query(default=None, description="Filter by resource type"),
    from_ts: datetime | None = Query(default=None, description="Start of time range (inclusive)"),
    to_ts: datetime | None = Query(default=None, description="End of time range (inclusive)"),
    limit: int = Query(default=50, ge=1, le=500, description="Max results to return"),
) -> AuditLogListResponse:
    """List audit logs with optional filters. Requires super_admin role.

    Spec: FS-ADMIN-003 Section 2.4
    """
    # Build WHERE conditions
    conditions = []
    if user_id is not None:
        conditions.append(AuditLog.user_id == user_id)
    if resource_type is not None:
        conditions.append(AuditLog.resource_type == resource_type)
    if from_ts is not None:
        conditions.append(AuditLog.created_at >= from_ts)
    if to_ts is not None:
        conditions.append(AuditLog.created_at <= to_ts)

    # Count query
    count_stmt = select(func.count()).select_from(AuditLog)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = (await session.execute(count_stmt)).scalar_one()

    # Data query -- newest first
    data_stmt = (
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    if conditions:
        data_stmt = data_stmt.where(*conditions)

    result = await session.execute(data_stmt)
    logs = list(result.scalars().all())

    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
    )

# Spec: FS-DASH-004
"""Incident list, detail, and status update API."""

from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_role
from app.db.session import get_session
from app.models.incident import Incident
from app.schemas.incident import (
    IncidentListResponse,
    IncidentResponse,
    IncidentStatusUpdate,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


def _to_response(incident: Incident) -> IncidentResponse:
    """Convert ORM model to response schema, including joined instance_name."""
    instance_name: str | None = None
    if incident.instance is not None:
        instance_name = incident.instance.name

    return IncidentResponse(
        id=incident.id,
        instance_id=incident.instance_id,
        instance_name=instance_name,
        severity=incident.severity,
        status=incident.status,
        title=incident.title,
        description=incident.description,
        source=incident.source,
        metric_type=incident.metric_type,
        metric_value=incident.metric_value,
        baseline_value=incident.baseline_value,
        detected_at=incident.detected_at,
        acknowledged_at=incident.acknowledged_at,
        resolved_at=incident.resolved_at,
    )


# Spec: FS-DASH-004 — AC-1: severity/status filter
@router.get("/incidents", response_model=IncidentListResponse)
async def list_incidents(
    severity: str | None = Query(
        default=None,
        description="Filter by severity: critical, warning, notice, info",
    ),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status: open, acknowledged, in_progress, resolved, closed",
    ),
    instance_id: UUID | None = Query(default=None, description="Filter by DB instance ID"),
    limit: int = Query(default=50, ge=1, le=200, description="Max items to return"),
    cursor: str | None = Query(
        default=None, description="Cursor for pagination (detected_at ISO string)"
    ),
    session: AsyncSession = Depends(get_session),
) -> IncidentListResponse:
    """List incidents with optional filters and cursor-based pagination."""
    # Spec: FS-DASH-004 — join db_instances for instance_name
    stmt = select(Incident).options(selectinload(Incident.instance))

    # Apply filters
    if severity is not None:
        stmt = stmt.where(Incident.severity == severity)
    if status_filter is not None:
        stmt = stmt.where(Incident.status == status_filter)
    if instance_id is not None:
        stmt = stmt.where(Incident.instance_id == instance_id)

    # Count before pagination
    count_stmt = select(func.count()).select_from(Incident)
    if severity is not None:
        count_stmt = count_stmt.where(Incident.severity == severity)
    if status_filter is not None:
        count_stmt = count_stmt.where(Incident.status == status_filter)
    if instance_id is not None:
        count_stmt = count_stmt.where(Incident.instance_id == instance_id)
    total = (await session.execute(count_stmt)).scalar_one()

    # Cursor-based pagination (descending by detected_at)
    if cursor is not None:
        cursor_dt = datetime.fromisoformat(cursor)
        stmt = stmt.where(Incident.detected_at < cursor_dt)

    stmt = stmt.order_by(Incident.detected_at.desc()).limit(limit)

    result = await session.execute(stmt)
    incidents = list(result.scalars().all())

    return IncidentListResponse(
        items=[_to_response(i) for i in incidents],
        total=total,
    )


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> IncidentResponse:
    """Get a single incident by ID."""
    incident = await _get_incident_or_404(session, incident_id)
    return _to_response(incident)


# Spec: FS-DASH-004 — AC-3: status update (ACK / Resolve)
@router.put(
    "/incidents/{incident_id}/status",
    response_model=IncidentResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
)
async def update_incident_status(
    incident_id: UUID,
    body: IncidentStatusUpdate,
    session: AsyncSession = Depends(get_session),
) -> IncidentResponse:
    """Update an incident's status and set corresponding timestamps."""
    incident = await _get_incident_or_404(session, incident_id)
    now = datetime.now(UTC)

    # Validate status transition
    _validate_transition(incident.status, body.status)

    incident.status = body.status

    if body.status == "acknowledged" and incident.acknowledged_at is None:
        incident.acknowledged_at = now
    elif body.status == "resolved":
        incident.resolved_at = now

    await session.commit()
    await session.refresh(incident, attribute_names=["instance"])

    logger.info(
        "incident.status_updated",
        incident_id=str(incident.id),
        new_status=body.status,
    )
    return _to_response(incident)


# Valid status transitions
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"acknowledged", "in_progress", "resolved"},
    "acknowledged": {"in_progress", "resolved"},
    "in_progress": {"resolved"},
    "resolved": {"closed"},
}


def _validate_transition(current: str, target: str) -> None:
    """Raise 422 if the status transition is not allowed."""
    allowed = _VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition from '{current}' to '{target}'. "
                f"Allowed transitions: {', '.join(sorted(allowed)) or 'none'}."
            ),
        )


async def _get_incident_or_404(session: AsyncSession, incident_id: UUID) -> Incident:
    """Fetch an incident with its instance relationship or raise 404."""
    stmt = (
        select(Incident).options(selectinload(Incident.instance)).where(Incident.id == incident_id)
    )
    result = await session.execute(stmt)
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found. Verify the ID is correct.",
        )
    return incident

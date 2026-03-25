# Spec: FS-DASH-004, DM-001
"""Pydantic v2 schemas for incident API operations."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class IncidentResponse(BaseModel):
    """Response schema for a single incident."""

    id: UUID
    instance_id: UUID | None
    instance_name: str | None = None
    severity: str
    status: str
    title: str
    description: str | None = None
    source: str
    metric_type: str | None = None
    metric_value: float | None = None
    baseline_value: float | None = None
    detected_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class IncidentListResponse(BaseModel):
    """Response schema for paginated incident listing."""

    items: list[IncidentResponse]
    total: int


class IncidentStatusUpdate(BaseModel):
    """Request schema for updating incident status."""

    status: Literal["acknowledged", "in_progress", "resolved"] = Field(
        ..., description="Target status: acknowledged, in_progress, or resolved"
    )

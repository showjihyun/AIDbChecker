# Spec: DM-001, MVP-DASH-003
"""Pydantic v2 schemas for ASH (Active Session History) API responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ASHSessionResponse(BaseModel):
    """Single active session sample."""

    id: UUID
    instance_id: UUID
    sampled_at: datetime
    pid: int
    query: str | None = None
    query_hash: int | None = None
    state: str
    wait_event_type: str | None = None
    wait_event: str | None = None
    backend_type: str | None = None
    client_addr: str | None = None
    application_name: str | None = None
    query_start: datetime | None = None
    duration_ms: float | None = None

    model_config = {"from_attributes": True}


class ASHSessionListResponse(BaseModel):
    """Paginated ASH session list."""

    items: list[ASHSessionResponse]
    next_cursor: str | None = None
    has_more: bool = False


class HeatmapBucket(BaseModel):
    """Single heatmap cell — count of sessions per wait_event_type per time bucket."""

    bucket_start: datetime
    wait_event_type: str
    count: int


class ASHHeatmapResponse(BaseModel):
    """ASH heatmap data grouped by wait_event_type and 10-second time buckets."""

    instance_id: UUID
    buckets: list[HeatmapBucket]
    bucket_interval_seconds: int = 10


class WaitBreakdownItem(BaseModel):
    """Wait event type breakdown with count and percentage."""

    wait_event_type: str
    count: int
    percentage: float = Field(ge=0.0, le=100.0)


class ASHWaitBreakdownResponse(BaseModel):
    """Wait event type distribution for the given time range."""

    instance_id: UUID
    total_samples: int
    breakdown: list[WaitBreakdownItem]

# Spec: DM-001, MVP-COLLECT-001
"""Pydantic v2 schemas for metric API responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MetricResponse(BaseModel):
    """Single metric sample in API response."""

    id: UUID
    instance_id: UUID
    sampled_at: datetime
    category: str
    metrics: dict

    model_config = {"from_attributes": True}


class MetricListResponse(BaseModel):
    """Paginated metric samples response with cursor-based pagination."""

    items: list[MetricResponse]
    next_cursor: str | None = Field(
        default=None, description="Cursor for next page (sampled_at ISO string)"
    )
    has_more: bool = False


class MetricLatestResponse(BaseModel):
    """Latest metric snapshot for an instance."""

    instance_id: UUID
    hot: MetricResponse | None = None
    warm: MetricResponse | None = None
    cold: MetricResponse | None = None

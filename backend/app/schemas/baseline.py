# Spec: MVP-AI-001, DM-001
"""Pydantic v2 schemas for baseline API operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BaselineResponse(BaseModel):
    """Response schema for a single baseline record."""

    id: UUID
    instance_id: UUID
    metric_type: str
    time_bucket: str
    normal_min: float
    normal_max: float
    mean: float
    stddev: float
    model_type: str
    model_params: dict
    training_samples: int
    last_trained_at: datetime
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BaselineListResponse(BaseModel):
    """Response schema for listing baselines."""

    items: list[BaselineResponse]
    total: int


class BaselineRetrainResponse(BaseModel):
    """Response schema for manual retrain trigger."""

    message: str
    instance_id: UUID
    task_id: str | None = None

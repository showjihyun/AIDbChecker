# Spec: FS-SCHEMA-001, DM-001
"""Pydantic v2 schemas for schema change detection API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SchemaChangeResponse(BaseModel):
    """Response schema for a single schema change event."""

    id: UUID
    instance_id: UUID
    change_type: str
    object_type: str
    object_name: str
    ddl_command: str | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    executed_by: str | None = None
    detected_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class SchemaChangeListResponse(BaseModel):
    """Response schema for paginated schema change listing."""

    items: list[SchemaChangeResponse]
    total: int

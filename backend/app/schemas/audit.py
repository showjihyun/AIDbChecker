# Spec: FS-ADMIN-003
"""Pydantic v2 schemas for Audit Log query responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """Single audit log entry returned by the list endpoint."""

    id: UUID
    user_id: UUID | None = None
    action: str
    resource_type: str
    resource_id: UUID | None = None
    details: dict
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Paginated audit log listing."""

    items: list[AuditLogResponse]
    total: int

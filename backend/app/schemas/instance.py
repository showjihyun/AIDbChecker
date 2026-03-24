# Spec: DM-001, MVP-DASH-001
"""Pydantic v2 schemas for DB instance CRUD operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class InstanceCreate(BaseModel):
    """Request schema for creating a new monitored DB instance."""

    name: str = Field(..., max_length=255, description="Unique display name")
    db_type: str = Field(
        ..., pattern=r"^(postgresql|mysql|mssql)$", description="Database type"
    )
    host: str = Field(..., max_length=255, description="Host address")
    port: int = Field(default=5432, ge=1, le=65535, description="Port number")
    database_name: str = Field(..., max_length=255, description="Database name")
    cluster_id: str | None = Field(
        default=None, max_length=100, description="Cluster group identifier"
    )
    environment: str = Field(
        ...,
        pattern=r"^(production|staging|development)$",
        description="Deployment environment",
    )
    connection_config: dict = Field(
        default_factory=dict,
        description="Connection settings (SSL, pool, credentials — encrypted at rest)",
    )
    metadata_extra: dict = Field(
        default_factory=dict,
        description="Tags, labels, and other metadata",
    )


class InstanceUpdate(BaseModel):
    """Request schema for updating a monitored DB instance. All fields optional."""

    name: str | None = Field(default=None, max_length=255)
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    database_name: str | None = Field(default=None, max_length=255)
    cluster_id: str | None = None
    environment: str | None = Field(
        default=None, pattern=r"^(production|staging|development)$"
    )
    connection_config: dict | None = None
    is_active: bool | None = None
    autonomy_level: int | None = Field(default=None, ge=0, le=4)
    metadata_extra: dict | None = None


class InstanceResponse(BaseModel):
    """Response schema for a single DB instance."""

    id: UUID
    name: str
    db_type: str
    host: str
    port: int
    database_name: str
    cluster_id: str | None
    environment: str
    is_active: bool
    autonomy_level: int
    metadata_extra: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InstanceListResponse(BaseModel):
    """Response schema for paginated instance listing."""

    items: list[InstanceResponse]
    total: int


class ConnectionTestResponse(BaseModel):
    """Response schema for connection test result."""

    success: bool
    message: str

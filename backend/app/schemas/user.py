# Spec: DM-001, MVP-ADMIN-001, MVP-ADMIN-002
"""Pydantic v2 schemas for User CRUD operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """Request schema for creating a new user."""

    email: str = Field(
        ...,
        max_length=255,
        pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        description="Unique email address",
    )
    name: str = Field(..., max_length=255, description="Display name")
    password: str = Field(
        ..., min_length=8, max_length=128, description="Plain-text password (will be hashed)"
    )
    role: str = Field(
        default="viewer",
        pattern=r"^(super_admin|db_admin|operator|viewer|api_user)$",
        description="RBAC role",
    )


class UserUpdate(BaseModel):
    """Request schema for updating a user. All fields optional."""

    name: str | None = Field(default=None, max_length=255)
    role: str | None = Field(
        default=None,
        pattern=r"^(super_admin|db_admin|operator|viewer|api_user)$",
    )
    is_active: bool | None = None
    password: str | None = Field(
        default=None, min_length=8, max_length=128, description="New password (will be hashed)"
    )


class UserResponse(BaseModel):
    """Response schema for a single user (excludes sensitive fields)."""

    id: UUID
    email: str
    name: str
    role: str
    auth_provider: str
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Response schema for paginated user listing."""

    items: list[UserResponse]
    total: int

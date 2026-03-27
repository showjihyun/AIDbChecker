# Spec: API-ERR-001
"""Standardized error response schemas."""

from pydantic import BaseModel, Field


class FieldError(BaseModel):
    """Validation error for a specific field."""

    field: str
    message: str
    code: str = "invalid"


class ErrorResponse(BaseModel):
    """Standard error response format.

    Spec: API-ERR-001 Section 1.
    All API errors MUST return this format.
    """

    error_code: str = Field(..., description="Machine-readable code (e.g., INSTANCE_NOT_FOUND)")
    message: str = Field(..., description="Human-readable message")
    detail: str | None = Field(None, description="Additional context")
    field_errors: list[FieldError] | None = Field(None, description="Validation errors (422)")
    request_id: str | None = Field(None, description="Tracking UUID")

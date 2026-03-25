# Spec: FR-AI-003, MVP-AI-004
"""Pydantic v2 schemas for NL2SQL API operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NL2SQLQueryRequest(BaseModel):
    """Request schema for natural language to SQL conversion."""

    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language question about the database",
    )
    instance_id: UUID = Field(
        ..., description="Target DB instance to query against"
    )


class NL2SQLQueryResponse(BaseModel):
    """Response schema for NL2SQL query execution."""

    sql: str = Field(..., description="Generated SQL query")
    result_rows: list[list] = Field(
        default_factory=list, description="Query result rows"
    )
    result_columns: list[str] = Field(
        default_factory=list, description="Column names"
    )
    execution_time_ms: int = Field(
        ..., description="SQL execution time in milliseconds"
    )
    ai_model: str = Field(..., description="LLM model used for generation")
    warning: str | None = Field(
        default=None, description="Warning message if any"
    )

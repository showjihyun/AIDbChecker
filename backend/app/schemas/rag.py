# Spec: FR-AI-002, FS-AI-RAG-001
"""Pydantic v2 schemas for Lightweight RAG API operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RAGSearchRequest(BaseModel):
    """Request schema for similarity search."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Search text (incident description or natural language)",
    )
    instance_id: UUID | None = Field(default=None, description="Limit search to specific instance")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of results")
    min_similarity: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum cosine similarity"
    )


class RAGSearchResult(BaseModel):
    """Single RAG search result."""

    incident_id: UUID
    similarity: float = Field(..., ge=0.0, le=1.0)
    summary: str
    root_cause: str | None = None
    resolution: str | None = None
    created_at: datetime


class RAGSearchResponse(BaseModel):
    """Response schema for RAG similarity search."""

    results: list[RAGSearchResult]
    search_time_ms: int
    embedding_model: str


class RAGStatusResponse(BaseModel):
    """Response schema for RAG embedding status."""

    total_documents: int
    total_incidents_embedded: int
    last_embedding_at: datetime | None
    embedding_model: str
    vector_dimensions: int

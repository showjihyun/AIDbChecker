# Spec: FS-AI-NL2SQL-001
"""Pydantic v2 schemas for Graph API operations (NL2GraphRAG Phase 2)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# --- Request Schemas ---

class GraphBuildRequest(BaseModel):
    """Request to build a Schema Knowledge Graph for an instance."""

    instance_id: UUID = Field(
        ..., description="Target DB instance to extract schema from"
    )


class GraphMetricRequest(BaseModel):
    """Request to add a business metric node to the graph."""

    instance_id: UUID = Field(
        ..., description="Target DB instance"
    )
    name: str = Field(
        ..., min_length=1, max_length=255,
        description="Metric name (e.g. 'avg_query_time')",
    )
    description: str = Field(
        ..., min_length=1,
        description="Metric description for embedding",
    )
    source_columns: list[str] = Field(
        ..., min_length=1,
        description="Source columns in 'table.column' format (e.g. ['active_sessions.duration_ms'])",
    )


class GraphConceptRequest(BaseModel):
    """Request to add a business concept node to the graph."""

    instance_id: UUID = Field(
        ..., description="Target DB instance"
    )
    name: str = Field(
        ..., min_length=1, max_length=255,
        description="Concept name (e.g. 'slow_query')",
    )
    description: str = Field(
        ..., min_length=1,
        description="Concept description for embedding",
    )
    related_metrics: list[str] = Field(
        ..., min_length=1,
        description="Related metric names (e.g. ['avg_query_time'])",
    )


# --- Response Schemas ---

class GraphBuildResponse(BaseModel):
    """Response after building a Schema Knowledge Graph."""

    instance_id: UUID
    nodes_created: int
    edges_created: int
    build_time_ms: int


class GraphNodeResponse(BaseModel):
    """Response schema for a single graph node."""

    id: UUID
    node_type: str
    name: str
    description: str | None = None
    metadata: dict = Field(default_factory=dict)
    instance_id: UUID | None = None
    created_at: datetime


class GraphNodeListResponse(BaseModel):
    """Response schema for listing graph nodes."""

    nodes: list[GraphNodeResponse]
    total: int


class GraphMetricResponse(BaseModel):
    """Response after adding a business metric."""

    node_id: UUID
    name: str
    edges_created: int


class GraphConceptResponse(BaseModel):
    """Response after adding a business concept."""

    node_id: UUID
    name: str
    edges_created: int

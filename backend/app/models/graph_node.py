# Spec: FS-AI-NL2SQL-001
"""GraphNode model -- Schema Knowledge Graph node for NL2GraphRAG.

Stores table, column, metric, and business concept nodes with pgvector
embeddings for similarity search. Used by GraphRAGRetriever to find
relevant schema elements for a natural language query.

Phase 2 of NL2GraphRAG: Schema Knowledge Graph.
"""

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin


class GraphNode(Base, UUIDMixin):
    """Knowledge Graph node representing a schema element or business concept.

    Spec: FS-AI-NL2SQL-001 Section 3.1 -- node types:
      - table:   DB table from information_schema
      - column:  DB column from information_schema
      - metric:  Business metric (manually defined)
      - concept: Business concept (manually defined)
    """

    __tablename__ = "graph_nodes"

    node_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="table / column / metric / concept",
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    metadata_extra: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}",
        comment="Extra metadata (data_type for columns, schema for tables, etc.)",
    )
    embedding = mapped_column(
        Vector(384), nullable=True,
        comment="sentence-transformers embedding (384 dim, all-MiniLM-L6-v2)",
    )
    instance_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("db_instances.id", ondelete="CASCADE"), nullable=True,
        comment="Target DB instance this node belongs to (null for global concepts)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    # --- Relationships ---
    instance: Mapped["DBInstance"] = relationship(  # noqa: F821
        lazy="selectin",
    )
    outgoing_edges: Mapped[list["GraphEdge"]] = relationship(  # noqa: F821
        foreign_keys="GraphEdge.source_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[list["GraphEdge"]] = relationship(  # noqa: F821
        foreign_keys="GraphEdge.target_id",
        back_populates="target",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_graph_nodes_type", "node_type"),
        Index("idx_graph_nodes_instance", "instance_id"),
        # HNSW index on embedding created in migration:
        # CREATE INDEX idx_graph_nodes_embedding
        #     ON graph_nodes USING hnsw (embedding vector_cosine_ops)
        #     WITH (m = 16, ef_construction = 64);
    )

    def __repr__(self) -> str:
        return f"<GraphNode {self.node_type}:{self.name}>"

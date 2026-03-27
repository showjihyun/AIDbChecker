# Spec: FS-AI-NL2SQL-001
"""GraphEdge model -- Schema Knowledge Graph edge for NL2GraphRAG.

Stores relationships between GraphNode entities: HAS_COLUMN, FOREIGN_KEY,
METRIC_SOURCE, and CONCEPT_MAP edges. Used by GraphRAGRetriever to
discover join paths and related schema elements.

Phase 2 of NL2GraphRAG: Schema Knowledge Graph.
"""

from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin


class GraphEdge(Base, UUIDMixin):
    """Knowledge Graph edge representing a relationship between nodes.

    Spec: FS-AI-NL2SQL-001 Section 3.2 -- edge types:
      - has_column:     table -> column
      - foreign_key:    column -> column (FK relationship)
      - metric_source:  metric -> column (metric derives from column)
      - concept_map:    concept -> metric (business concept maps to metric)
    """

    __tablename__ = "graph_edges"

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id: Mapped[UUID] = mapped_column(
        ForeignKey("graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    edge_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="has_column / foreign_key / metric_source / concept_map",
    )
    metadata_extra: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Extra edge metadata (constraint_name for FK, etc.)",
    )

    # --- Relationships ---
    source: Mapped["GraphNode"] = relationship(  # noqa: F821
        foreign_keys=[source_id],
        back_populates="outgoing_edges",
    )
    target: Mapped["GraphNode"] = relationship(  # noqa: F821
        foreign_keys=[target_id],
        back_populates="incoming_edges",
    )

    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "edge_type", name="uq_graph_edges_src_tgt_type"),
        Index("idx_graph_edges_source", "source_id"),
        Index("idx_graph_edges_target", "target_id"),
    )

    def __repr__(self) -> str:
        return f"<GraphEdge {self.edge_type}: {self.source_id} -> {self.target_id}>"

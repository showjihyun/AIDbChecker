from __future__ import annotations
# Spec: DM-001
"""Incident model — detected anomalies and failures."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Incident(Base, UUIDMixin, TimestampMixin):
    """Detected anomaly or failure event for a monitored DB instance.

    Incidents are never deleted — only closed (status='closed').
    Lifecycle: open -> acknowledged -> in_progress -> resolved -> closed.
    """

    __tablename__ = "incidents"

    instance_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("db_instances.id", ondelete="SET NULL"), nullable=True
    )
    severity: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="critical / warning / notice / info",
    )
    status: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
        server_default="open",
        comment="open / acknowledged / in_progress / resolved / closed",
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="ai_baseline / threshold / manual / schema_change",
    )
    metric_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, default=None, server_default="{}"
    )

    # --- Relationships ---
    instance: Mapped["DBInstance | None"] = relationship(  # noqa: F821
        back_populates="incidents"
    )
    resolver: Mapped["User | None"] = relationship(  # noqa: F821
        foreign_keys=[resolved_by],
    )
    alert_histories: Mapped[list["AlertHistory"]] = relationship(  # noqa: F821
        back_populates="incident"
    )
    rag_documents: Mapped[list["RAGDocument"]] = relationship(  # noqa: F821
        back_populates="incident", passive_deletes=True
    )

    __table_args__ = (
        Index("ix_incidents_instance_status", "instance_id", "status"),
        Index(
            "ix_incidents_severity",
            "severity",
            postgresql_where="status IN ('open', 'in_progress')",
        ),
        Index("ix_incidents_detected", "detected_at", postgresql_using="btree"),
    )

    def __repr__(self) -> str:
        return f"<Incident [{self.severity}] {self.title[:50]}>"

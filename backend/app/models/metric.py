from __future__ import annotations
# Spec: DM-001
"""MetricSample model — 1-second metric snapshots (partitioned by sampled_at).

Note: Table uses PARTITION BY RANGE (sampled_at) managed by pg_partman.
Partitioning is handled in Alembic migration, NOT by SQLAlchemy.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MetricSample(Base):
    """1-second metric snapshot for a monitored DB instance.

    Composite PK (id, sampled_at) is required for PostgreSQL native
    range partitioning — partition key must be part of the primary key.

    Categories: hot (1s), warm (10s), cold (1m).
    """

    __tablename__ = "metric_samples"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instance_id: Mapped[UUID] = mapped_column(
        ForeignKey("db_instances.id", ondelete="CASCADE"), nullable=False
    )
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    category: Mapped[str] = mapped_column(String(10), nullable=False, comment="hot / warm / cold")
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # --- Relationships ---
    instance: Mapped["DBInstance"] = relationship(  # noqa: F821
        back_populates="metric_samples"
    )

    __table_args__ = (
        Index("ix_metric_instance_time", "instance_id", "sampled_at"),
        # PARTITION BY RANGE (sampled_at) — pg_partman daily, retention: hot=7d, warm=90d, cold=365d
        {"comment": "Partitioned by sampled_at (daily, pg_partman)"},
    )

    def __repr__(self) -> str:
        return f"<MetricSample {self.instance_id} @ {self.sampled_at}>"

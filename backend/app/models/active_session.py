from __future__ import annotations
# Spec: DM-001
"""ActiveSession model — ASH 1-second sampling (partitioned by sampled_at).

Note: Table uses PARTITION BY RANGE (sampled_at) managed by pg_partman.
Partitioning is handled in Alembic migration, NOT by SQLAlchemy.
Retention: 7 days raw + Materialized View downsampling.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ActiveSession(Base):
    """1-second ASH (Active Session History) sample from pg_stat_activity.

    Composite PK (id, sampled_at) is required for PostgreSQL native
    range partitioning — partition key must be part of the primary key.
    """

    __tablename__ = "active_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instance_id: Mapped[UUID] = mapped_column(
        ForeignKey("db_instances.id", ondelete="CASCADE"), nullable=False
    )
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_hash: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="pg_stat_statements queryid"
    )
    state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="active / idle / idle in transaction / locked",
    )
    wait_event_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="CPU, LWLock, Lock, I/O, IPC, etc."
    )
    wait_event: Mapped[str | None] = mapped_column(String(100), nullable=True)
    backend_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="client backend, autovacuum, etc."
    )
    client_addr: Mapped[str | None] = mapped_column(
        String(45), nullable=True, comment="Client IP address (INET)"
    )
    application_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    query_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Elapsed time in milliseconds"
    )

    # --- Relationships ---
    instance: Mapped["DBInstance"] = relationship(  # noqa: F821
        back_populates="active_sessions"
    )

    __table_args__ = (
        Index("ix_ash_instance_time", "instance_id", "sampled_at"),
        Index("ix_ash_wait_event", "wait_event_type", "wait_event"),
        Index(
            "ix_ash_state",
            "state",
            postgresql_where="state != 'idle'",
        ),
        # PARTITION BY RANGE (sampled_at) — pg_partman daily, retention: 7d raw
        {"comment": "Partitioned by sampled_at (daily, pg_partman)"},
    )

    def __repr__(self) -> str:
        return f"<ActiveSession pid={self.pid} state={self.state} @ {self.sampled_at}>"

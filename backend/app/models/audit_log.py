from __future__ import annotations
# Spec: DM-001
"""AuditLog model — immutable audit trail (partitioned by created_at).

Note: Table uses PARTITION BY RANGE (created_at) managed by pg_partman (monthly).
Partitioning is handled in Alembic migration, NOT by SQLAlchemy.
Retention: 365 days hot + glacier archive.
Audit logs are NEVER deleted or soft-deleted (regulatory compliance).
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditLog(Base):
    """Immutable audit log entry recording WHO/WHAT/WHEN/WHERE/WHY.

    Composite PK (id, created_at) is required for PostgreSQL native
    range partitioning — partition key must be part of the primary key.
    """

    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Actor; null = system-generated",
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="login / create / update / delete / execute / ai_decision",
    )
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="incident / playbook / instance / user, etc.",
    )
    resource_id: Mapped[UUID | None] = mapped_column(nullable=True)
    details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="WHO/WHAT/WHEN/WHERE/WHY + before/after state",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True, comment="Client IP (IPv4 or IPv6)"
    )
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        server_default=func.now(),
    )

    # --- Relationships ---
    user: Mapped["User | None"] = relationship(  # noqa: F821
        back_populates="audit_logs"
    )

    __table_args__ = (
        Index("ix_audit_user_time", "user_id", created_at.desc()),
        Index("ix_audit_resource", "resource_type", "resource_id"),
        # PARTITION BY RANGE (created_at) — pg_partman monthly, retention: 365d
        {"comment": "Partitioned by created_at (monthly, pg_partman)"},
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} on {self.resource_type} @ {self.created_at}>"

from __future__ import annotations
# Spec: DM-001
"""AlertChannel model — notification channel configuration (Slack, Email, Webhook, PagerDuty)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class AlertChannel(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Alert delivery channel configuration.

    Supports slack, email, webhook, and pagerduty channel types.
    Config JSONB stores channel-specific settings (webhook_url, smtp_host, etc.)
    and is encrypted at rest.
    """

    __tablename__ = "alert_channels"

    name: Mapped[str] = mapped_column(String(255), nullable=False, comment='e.g. "#db-alerts"')
    channel_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="slack / email / webhook / pagerduty",
    )
    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Channel-specific settings (encrypted at rest)",
    )
    severity_filter: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{critical,warning}",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_result: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # --- Relationships ---
    creator: Mapped["User | None"] = relationship(  # noqa: F821
        foreign_keys=[created_by],
    )
    alert_histories: Mapped[list["AlertHistory"]] = relationship(  # noqa: F821
        back_populates="channel"
    )

    __table_args__ = (
        Index("ix_alert_channels_type", "channel_type"),
        Index(
            "ix_alert_channels_active",
            "is_active",
            postgresql_where=(is_active == True),  # noqa: E712
        ),
    )

    def __repr__(self) -> str:
        return f"<AlertChannel {self.name} ({self.channel_type})>"

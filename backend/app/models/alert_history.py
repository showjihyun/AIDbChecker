# Spec: DM-001
"""AlertHistory model — alert delivery audit trail."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin


class AlertHistory(Base, UUIDMixin):
    """Record of an alert notification sent (or attempted) for an incident.

    Tracks delivery status, escalation level, and any error details
    for debugging failed notifications.
    """

    __tablename__ = "alert_history"

    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[UUID] = mapped_column(
        ForeignKey("alert_channels.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("alert_policies.id", ondelete="SET NULL"), nullable=True
    )
    escalation_level: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1
    )
    status: Mapped[str] = mapped_column(
        String(15), nullable=False,
        comment="sent / failed / suppressed",
    )
    response_code: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="HTTP response code for webhooks"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # --- Relationships ---
    incident: Mapped["Incident"] = relationship(  # noqa: F821
        back_populates="alert_histories"
    )
    channel: Mapped["AlertChannel"] = relationship(  # noqa: F821
        back_populates="alert_histories"
    )
    policy: Mapped["AlertPolicy | None"] = relationship(  # noqa: F821
        foreign_keys=[policy_id],
    )

    __table_args__ = (
        Index("ix_alert_history_incident", "incident_id", sent_at.desc()),
    )

    def __repr__(self) -> str:
        return f"<AlertHistory {self.status} for incident={self.incident_id}>"

# Spec: DM-001
"""AlertPolicy model — escalation policy configuration."""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class AlertPolicy(Base, UUIDMixin, TimestampMixin):
    """Escalation policy defining multi-level alert routing.

    escalation_chain example:
    [
        {"level": 1, "channel_id": "uuid-slack", "delay_minutes": 0},
        {"level": 2, "channel_id": "uuid-email", "delay_minutes": 15},
        {"level": 3, "channel_id": "uuid-pagerduty", "delay_minutes": 30}
    ]
    """

    __tablename__ = "alert_policies"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_chain: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="[{level, channel_id, delay_minutes}]",
    )
    severity: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="critical / warning / notice / info",
    )
    cooldown_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        comment="Suppress duplicate alerts for same incident within this window",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<AlertPolicy {self.name} severity={self.severity}>"

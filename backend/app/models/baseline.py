# Spec: DM-001
"""Baseline model — AI-generated automatic baselines for anomaly detection."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Baseline(Base, UUIDMixin, TimestampMixin):
    """AI-computed baseline for a specific metric and time bucket.

    Baselines are used for dynamic anomaly detection by comparing
    real-time metric values against learned normal ranges.

    Models: stl (STL decomposition), isolation_forest, prophet.
    Time buckets: weekday_business, weekday_night, weekend, etc.
    """

    __tablename__ = "baselines"

    instance_id: Mapped[UUID] = mapped_column(
        ForeignKey("db_instances.id", ondelete="CASCADE"), nullable=False
    )
    metric_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="cpu_usage, connections, tps, etc.",
    )
    time_bucket: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="weekday_business / weekday_night / weekend",
    )
    normal_min: Mapped[float] = mapped_column(Float, nullable=False)
    normal_max: Mapped[float] = mapped_column(Float, nullable=False)
    mean: Mapped[float] = mapped_column(Float, nullable=False)
    stddev: Mapped[float] = mapped_column(Float, nullable=False)
    model_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="stl / isolation_forest / prophet",
    )
    model_params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    training_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    last_trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # --- Relationships ---
    instance: Mapped["DBInstance"] = relationship(  # noqa: F821
        back_populates="baselines"
    )

    __table_args__ = (
        UniqueConstraint(
            "instance_id", "metric_type", "time_bucket",
            name="ix_baselines_lookup",
        ),
    )

    def __repr__(self) -> str:
        return f"<Baseline {self.metric_type}/{self.time_bucket} active={self.is_active}>"

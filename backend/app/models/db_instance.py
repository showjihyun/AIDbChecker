# Spec: DM-001
"""DBInstance model — monitored database instances."""

from sqlalchemy import Boolean, Index, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class DBInstance(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Monitored database instance registration.

    Represents a target DB (PostgreSQL/MySQL/MSSQL) that NeuralDB monitors.
    Connection credentials are stored encrypted in connection_config (JSONB).
    """

    __tablename__ = "db_instances"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    db_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="postgresql / mysql / mssql"
    )
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=5432)
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cluster_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    environment: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="production / staging / development"
    )
    connection_config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    autonomy_level: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, comment="Adaptive autonomy 0-4"
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, default=None, server_default="{}"
    )

    # --- Relationships ---
    metric_samples: Mapped[list["MetricSample"]] = relationship(  # noqa: F821
        back_populates="instance", passive_deletes=True
    )
    active_sessions: Mapped[list["ActiveSession"]] = relationship(  # noqa: F821
        back_populates="instance", passive_deletes=True
    )
    incidents: Mapped[list["Incident"]] = relationship(  # noqa: F821
        back_populates="instance"
    )
    baselines: Mapped[list["Baseline"]] = relationship(  # noqa: F821
        back_populates="instance", passive_deletes=True
    )
    schema_changes: Mapped[list["SchemaChange"]] = relationship(  # noqa: F821
        back_populates="instance", passive_deletes=True
    )
    nl2sql_histories: Mapped[list["NL2SQLHistory"]] = relationship(  # noqa: F821
        back_populates="instance"
    )

    __table_args__ = (
        Index("ix_db_instances_cluster", "cluster_id"),
        Index(
            "ix_db_instances_active",
            "is_active",
            postgresql_where=(is_active == True),  # noqa: E712
        ),
    )

    def __repr__(self) -> str:
        return f"<DBInstance {self.name} ({self.db_type})>"

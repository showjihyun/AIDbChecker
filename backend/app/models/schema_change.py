# Spec: DM-001
"""SchemaChange model — DDL change tracking on monitored databases."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin


class SchemaChange(Base, UUIDMixin):
    """Captured DDL change event (CREATE/ALTER/DROP/REINDEX/PARAM_CHANGE).

    Detected via PostgreSQL Event Triggers on the target DB.
    Impact analysis (AI) is populated asynchronously after detection.
    """

    __tablename__ = "schema_changes"

    instance_id: Mapped[UUID] = mapped_column(
        ForeignKey("db_instances.id", ondelete="CASCADE"), nullable=False
    )
    change_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="CREATE / ALTER / DROP / REINDEX / PARAM_CHANGE",
    )
    object_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="TABLE / INDEX / COLUMN / FUNCTION / PARAMETER",
    )
    object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ddl_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    executed_by: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="DB user who executed the DDL"
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    impact_analysis: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="AI impact analysis result"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # --- Relationships ---
    instance: Mapped["DBInstance"] = relationship(  # noqa: F821
        back_populates="schema_changes"
    )

    __table_args__ = (
        Index(
            "ix_schema_changes_instance_time",
            "instance_id",
            detected_at.desc(),
        ),
    )

    def __repr__(self) -> str:
        return f"<SchemaChange {self.change_type} {self.object_type} {self.object_name}>"

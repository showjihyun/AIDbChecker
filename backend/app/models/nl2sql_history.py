# Spec: DM-001
"""NL2SQLHistory model — natural language to SQL query history."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin


class NL2SQLHistory(Base, UUIDMixin):
    """Record of a user's natural language query translated to SQL.

    Stores the original question, generated SQL, execution result,
    and optional user feedback for continuous improvement.
    """

    __tablename__ = "nl2sql_histories"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    instance_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("db_instances.id", ondelete="SET NULL"), nullable=True
    )
    natural_query: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql: Mapped[str] = mapped_column(Text, nullable=False)
    execution_result: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Query result {rows, columns}"
    )
    is_correct: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, comment="User feedback: correct / incorrect"
    )
    ai_model: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # --- Relationships ---
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="nl2sql_histories"
    )
    instance: Mapped["DBInstance | None"] = relationship(  # noqa: F821
        back_populates="nl2sql_histories"
    )

    def __repr__(self) -> str:
        return f"<NL2SQLHistory '{self.natural_query[:40]}...'>"

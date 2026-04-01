# Spec: FS-AI-REPORT-002
"""DBAReport model — persisted DBA periodic reports."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DBAReport(Base):
    """Persisted DBA report for list/detail/PDF download."""

    __tablename__ = "dba_reports"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    instance_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    instance_name: Mapped[str] = mapped_column(String(255), nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    report_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ai_analysis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    incident_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    slow_query_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    slack_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

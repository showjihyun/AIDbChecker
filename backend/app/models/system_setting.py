# Spec: FS-AI-LLM-001
"""SystemSetting model — persistent key-value store for runtime config."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class SystemSetting(UUIDMixin, TimestampMixin, Base):
    """Persistent key-value settings (LLM config, feature flags, etc.)."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")

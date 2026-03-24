# Spec: DM-001
"""User model — system users with RBAC roles."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """System user with role-based access control.

    Roles: super_admin, db_admin, operator, viewer, api_user.
    Auth providers: local (email+password), saml, oidc, ldap.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="bcrypt hash, null for SSO users"
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="super_admin / db_admin / operator / viewer / api_user",
    )
    auth_provider: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="local",
        comment="local / saml / oidc / ldap",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    preferences: Mapped[dict | None] = mapped_column(
        JSONB, default=None, server_default="{}"
    )

    # --- Relationships ---
    audit_logs: Mapped[list["AuditLog"]] = relationship(  # noqa: F821
        back_populates="user"
    )
    nl2sql_histories: Mapped[list["NL2SQLHistory"]] = relationship(  # noqa: F821
        back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role}>"

# Spec: FS-AI-LLM-001
"""005 system_settings — persistent key-value store for runtime config.

Revision ID: 005_system_settings
Revises: 004_phase2
"""

from alembic import op
import sqlalchemy as sa

revision = "005_system_settings"
down_revision = "004_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"])


def downgrade() -> None:
    op.drop_index("ix_system_settings_key")
    op.drop_table("system_settings")

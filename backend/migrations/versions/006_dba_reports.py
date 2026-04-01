# Spec: FS-AI-REPORT-002
"""006 dba_reports — persisted DBA periodic reports for list/PDF download.

Revision ID: 006_dba_reports
Revises: 005_system_settings
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "006_dba_reports"
down_revision = "005_system_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dba_reports",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("instance_id", UUID(as_uuid=True), nullable=False),
        sa.Column("instance_name", sa.String(255), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("report_data", JSONB, nullable=False),
        sa.Column("ai_analysis", sa.Text(), nullable=False, server_default=""),
        sa.Column("incident_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("slow_query_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("slack_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dba_reports_instance", "dba_reports", ["instance_id", sa.text("created_at DESC")])
    op.create_index("ix_dba_reports_period", "dba_reports", ["period", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_dba_reports_period")
    op.drop_index("ix_dba_reports_instance")
    op.drop_table("dba_reports")

# Spec: FS-DBA-001
"""003 agent_actions — DBA Agent execution history table.

Stores all agent-initiated actions (create_index, vacuum, kill_session, etc.)
with risk classification, approval status, and before/after state.

Revision ID: 003_agent_actions
Revises: 002_graph
"""

from alembic import op
import sqlalchemy as sa

revision = "003_agent_actions"
down_revision = "002_graph"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_actions",
        sa.Column(
            "id", sa.Uuid(), nullable=False,
            default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("instance_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("sql_command", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(15), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False,
            server_default="pending",
        ),
        sa.Column("requested_by", sa.String(50), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("estimated_impact", sa.Text(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("rows_affected", sa.Integer(), nullable=True),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "approved_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "executed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["instance_id"], ["db_instances.id"],
            name="fk_agent_actions_instance_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["users.id"],
            name="fk_agent_actions_approved_by",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "idx_agent_actions_instance",
        "agent_actions", ["instance_id"],
    )
    op.create_index(
        "idx_agent_actions_status",
        "agent_actions", ["status"],
        postgresql_where=sa.text("status IN ('pending', 'executing')"),
    )
    op.create_index(
        "idx_agent_actions_created",
        "agent_actions", ["created_at"],
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index("idx_agent_actions_created", "agent_actions")
    op.drop_index("idx_agent_actions_status", "agent_actions")
    op.drop_index("idx_agent_actions_instance", "agent_actions")
    op.drop_table("agent_actions")

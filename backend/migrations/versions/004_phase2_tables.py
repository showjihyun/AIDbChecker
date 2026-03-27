# Spec: DM-001, DM-MIG-001
"""004 Phase 2/3 tables — playbooks, remediation_logs, copilot_sessions,
mtl_predictions, reasoning_chains, evidence_links.

Revision ID: 004_phase2
Revises: 003_agent_actions
"""

from alembic import op
import sqlalchemy as sa

revision = "004_phase2"
down_revision = "003_agent_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==================================================================
    # 1. playbooks (Spec: FS-AUTO-003)
    # ==================================================================
    op.create_table(
        "playbooks",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("yaml_content", sa.Text(), nullable=False),
        sa.Column("parsed_config", sa.JSON(), nullable=False),
        sa.Column("trigger_type", sa.String(30), nullable=False),
        sa.Column("min_autonomy_level", sa.SmallInteger(), nullable=False, server_default="2"),
        sa.Column("target_db_types", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("author", sa.String(50), nullable=False),
        sa.Column("success_rate", sa.Float(), server_default="0.0"),
        sa.Column("execution_count", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("tags", sa.ARRAY(sa.String()), server_default="{}"),
        sa.Column("git_sha", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_playbooks_trigger", "playbooks", ["trigger_type"])

    # ==================================================================
    # 2. remediation_logs (Spec: FS-AUTO-003, DM-001 §2.7)
    # ==================================================================
    op.create_table(
        "remediation_logs",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("playbook_id", sa.Uuid(), sa.ForeignKey("playbooks.id"), nullable=True),
        sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("incidents.id"), nullable=True),
        sa.Column("instance_id", sa.Uuid(), sa.ForeignKey("db_instances.id"), nullable=False),
        sa.Column("autonomy_level", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(15), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_by", sa.String(50), nullable=False),
        sa.Column("rollback_reason", sa.Text(), nullable=True),
        sa.Column("slo_check", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_remediation_instance_status", "remediation_logs", ["instance_id", "status"])

    # ==================================================================
    # 3. mtl_predictions (Spec: FS-AI-010, DM-001 v3.3)
    # ==================================================================
    op.create_table(
        "mtl_predictions",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instance_id", sa.Uuid(), sa.ForeignKey("db_instances.id"), nullable=True),
        sa.Column("anomaly_type", sa.String(50), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("severity_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reasoning_chain", sa.JSON(), nullable=True),
        sa.Column("evidence_links", sa.JSON(), nullable=True),
        sa.Column("suggested_actions", sa.JSON(), nullable=True),
        sa.Column("ai_model", sa.String(50), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("inference_time_ms", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.String(10), nullable=True),
        sa.Column("trace", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mtl_predictions_incident", "mtl_predictions", ["incident_id"])

    # ==================================================================
    # 4. copilot_sessions (Spec: FS-AI-012)
    # ==================================================================
    op.create_table(
        "copilot_sessions",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("instance_id", sa.Uuid(), sa.ForeignKey("db_instances.id"), nullable=False),
        sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("incidents.id"), nullable=True),
        sa.Column("prediction_id", sa.Uuid(), sa.ForeignKey("mtl_predictions.id"), nullable=True),
        sa.Column("branches_explored", sa.Integer(), nullable=False),
        sa.Column("selected_branch", sa.String(50), nullable=False),
        sa.Column("branch_scores", sa.JSON(), nullable=False),
        sa.Column("autonomy_level", sa.Integer(), nullable=False),
        sa.Column("execution_status", sa.String(20), nullable=False),
        sa.Column("executed_actions", sa.JSON(), nullable=True),
        sa.Column("execution_result", sa.JSON(), nullable=True),
        sa.Column("recommended_playbook", sa.String(255), nullable=True),
        sa.Column("total_inference_time_ms", sa.Integer(), nullable=True),
        sa.Column("total_tokens_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_copilot_sessions_instance", "copilot_sessions", ["instance_id"])
    op.create_index("ix_copilot_sessions_created", "copilot_sessions", ["created_at"])


def downgrade() -> None:
    op.drop_table("copilot_sessions")
    op.drop_table("mtl_predictions")
    op.drop_table("remediation_logs")
    op.drop_table("playbooks")

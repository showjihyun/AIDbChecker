# Spec: DM-001, DM-MIG-001
"""001 initial schema — all MVP tables.

Creates all MVP tables in FK dependency order:
  1. users
  2. db_instances
  3. metric_samples (partitioned at deploy time via pg_partman)
  4. active_sessions (partitioned at deploy time via pg_partman)
  5. incidents
  6. baselines
  7. schema_changes
  8. audit_logs (partitioned at deploy time via pg_partman)
  9. nl2sql_histories
 10. rag_documents (pgvector embedding)
 11. alert_channels
 12. alert_policies
 13. alert_history

Revision ID: 001_initial
Revises: None
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # PostgreSQL extensions (safe to call in non-PG environments)
    # ------------------------------------------------------------------
    try:
        op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    except Exception:
        pass  # Non-PostgreSQL environment (e.g., SQLite in tests)

    try:
        op.execute('CREATE EXTENSION IF NOT EXISTS "pgvector"')
    except Exception:
        pass  # pgvector not available

    # ==================================================================
    # 1. users (no FK dependencies)
    # ==================================================================
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "hashed_password", sa.String(255), nullable=True,
            comment="bcrypt hash, null for SSO users",
        ),
        sa.Column(
            "role", sa.String(20), nullable=False,
            comment="super_admin / db_admin / operator / viewer / api_user",
        ),
        sa.Column(
            "auth_provider", sa.String(20), nullable=False,
            server_default="local",
            comment="local / saml / oidc / ldap",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=True, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    # ==================================================================
    # 2. db_instances (no FK dependencies)
    # ==================================================================
    op.create_table(
        "db_instances",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "db_type", sa.String(20), nullable=False,
            comment="postgresql / mysql / mssql",
        ),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default=sa.text("5432")),
        sa.Column("database_name", sa.String(255), nullable=False),
        sa.Column("cluster_id", sa.String(100), nullable=True),
        sa.Column(
            "environment", sa.String(20), nullable=False,
            comment="production / staging / development",
        ),
        sa.Column("connection_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "autonomy_level", sa.SmallInteger(), nullable=False, server_default=sa.text("0"),
            comment="Adaptive autonomy 0-4",
        ),
        sa.Column("metadata", sa.JSON(), nullable=True, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_db_instances_cluster", "db_instances", ["cluster_id"])
    op.create_index(
        "ix_db_instances_active", "db_instances", ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    # ==================================================================
    # 3. metric_samples (FK: db_instances, composite PK)
    # Partitioning configured via pg_partman at deploy time
    # ==================================================================
    op.create_table(
        "metric_samples",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "instance_id", sa.Uuid(), nullable=False,
        ),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "category", sa.String(10), nullable=False,
            comment="hot / warm / cold",
        ),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", "sampled_at"),
        sa.ForeignKeyConstraint(
            ["instance_id"], ["db_instances.id"],
            name="fk_metric_samples_instance_id",
            ondelete="CASCADE",
        ),
        comment="Partitioned by sampled_at (daily, pg_partman)",
    )
    op.create_index(
        "ix_metric_instance_time", "metric_samples",
        ["instance_id", "sampled_at"],
    )

    # ==================================================================
    # 4. active_sessions (FK: db_instances, composite PK)
    # Partitioning configured via pg_partman at deploy time
    # ==================================================================
    op.create_table(
        "active_sessions",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("instance_id", sa.Uuid(), nullable=False),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column(
            "query_hash", sa.BigInteger(), nullable=True,
            comment="pg_stat_statements queryid",
        ),
        sa.Column(
            "state", sa.String(20), nullable=False,
            comment="active / idle / idle in transaction / locked",
        ),
        sa.Column(
            "wait_event_type", sa.String(30), nullable=True,
            comment="CPU, LWLock, Lock, I/O, IPC, etc.",
        ),
        sa.Column("wait_event", sa.String(100), nullable=True),
        sa.Column(
            "backend_type", sa.String(30), nullable=True,
            comment="client backend, autovacuum, etc.",
        ),
        sa.Column(
            "client_addr", sa.String(45), nullable=True,
            comment="Client IP address (INET)",
        ),
        sa.Column("application_name", sa.String(255), nullable=True),
        sa.Column("query_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "duration_ms", sa.Float(), nullable=True,
            comment="Elapsed time in milliseconds",
        ),
        sa.PrimaryKeyConstraint("id", "sampled_at"),
        sa.ForeignKeyConstraint(
            ["instance_id"], ["db_instances.id"],
            name="fk_active_sessions_instance_id",
            ondelete="CASCADE",
        ),
        comment="Partitioned by sampled_at (daily, pg_partman)",
    )
    op.create_index(
        "ix_ash_instance_time", "active_sessions",
        ["instance_id", "sampled_at"],
    )
    op.create_index(
        "ix_ash_wait_event", "active_sessions",
        ["wait_event_type", "wait_event"],
    )
    op.create_index(
        "ix_ash_state", "active_sessions", ["state"],
        postgresql_where=sa.text("state != 'idle'"),
    )

    # ==================================================================
    # 5. incidents (FK: db_instances SET NULL, users SET NULL)
    # ==================================================================
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("instance_id", sa.Uuid(), nullable=True),
        sa.Column(
            "severity", sa.String(10), nullable=False,
            comment="critical / warning / notice / info",
        ),
        sa.Column(
            "status", sa.String(15), nullable=False, server_default="open",
            comment="open / acknowledged / in_progress / resolved / closed",
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "source", sa.String(30), nullable=False,
            comment="ai_baseline / threshold / manual / schema_change",
        ),
        sa.Column("metric_type", sa.String(50), nullable=True),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column("baseline_value", sa.Float(), nullable=True),
        sa.Column(
            "detected_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["instance_id"], ["db_instances.id"],
            name="fk_incidents_instance_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"], ["users.id"],
            name="fk_incidents_resolved_by",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_incidents_instance_status", "incidents",
        ["instance_id", "status"],
    )
    op.create_index(
        "ix_incidents_severity", "incidents", ["severity"],
        postgresql_where=sa.text("status IN ('open', 'in_progress')"),
    )
    op.create_index("ix_incidents_detected", "incidents", [sa.text("detected_at DESC")])

    # ==================================================================
    # 6. baselines (FK: db_instances CASCADE)
    # ==================================================================
    op.create_table(
        "baselines",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("instance_id", sa.Uuid(), nullable=False),
        sa.Column(
            "metric_type", sa.String(50), nullable=False,
            comment="cpu_usage, connections, tps, etc.",
        ),
        sa.Column(
            "time_bucket", sa.String(20), nullable=False,
            comment="weekday_business / weekday_night / weekend",
        ),
        sa.Column("normal_min", sa.Float(), nullable=False),
        sa.Column("normal_max", sa.Float(), nullable=False),
        sa.Column("mean", sa.Float(), nullable=False),
        sa.Column("stddev", sa.Float(), nullable=False),
        sa.Column(
            "model_type", sa.String(20), nullable=False,
            comment="stl / isolation_forest / prophet",
        ),
        sa.Column("model_params", sa.JSON(), nullable=False),
        sa.Column("training_samples", sa.Integer(), nullable=False),
        sa.Column("last_trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["instance_id"], ["db_instances.id"],
            name="fk_baselines_instance_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "instance_id", "metric_type", "time_bucket",
            name="ix_baselines_lookup",
        ),
    )

    # ==================================================================
    # 7. schema_changes (FK: db_instances CASCADE)
    # ==================================================================
    op.create_table(
        "schema_changes",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("instance_id", sa.Uuid(), nullable=False),
        sa.Column(
            "change_type", sa.String(20), nullable=False,
            comment="CREATE / ALTER / DROP / REINDEX / PARAM_CHANGE",
        ),
        sa.Column(
            "object_type", sa.String(20), nullable=False,
            comment="TABLE / INDEX / COLUMN / FUNCTION / PARAMETER",
        ),
        sa.Column("object_name", sa.String(255), nullable=False),
        sa.Column("ddl_command", sa.Text(), nullable=True),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column(
            "executed_by", sa.String(255), nullable=True,
            comment="DB user who executed the DDL",
        ),
        sa.Column(
            "detected_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "impact_analysis", sa.JSON(), nullable=True,
            comment="AI impact analysis result",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["instance_id"], ["db_instances.id"],
            name="fk_schema_changes_instance_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_schema_changes_instance_time", "schema_changes",
        ["instance_id", sa.text("detected_at DESC")],
    )

    # ==================================================================
    # 8. audit_logs (FK: users SET NULL, composite PK)
    # Partitioning configured via pg_partman at deploy time
    # ==================================================================
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id", sa.Uuid(), nullable=True,
            comment="Actor; null = system-generated",
        ),
        sa.Column(
            "action", sa.String(50), nullable=False,
            comment="login / create / update / delete / execute / ai_decision",
        ),
        sa.Column(
            "resource_type", sa.String(50), nullable=False,
            comment="incident / playbook / instance / user, etc.",
        ),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column(
            "details", sa.JSON(), nullable=False,
            comment="WHO/WHAT/WHEN/WHERE/WHY + before/after state",
        ),
        sa.Column(
            "ip_address", sa.String(45), nullable=True,
            comment="Client IP (IPv4 or IPv6)",
        ),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", "created_at"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_audit_logs_user_id",
            ondelete="SET NULL",
        ),
        comment="Partitioned by created_at (monthly, pg_partman)",
    )
    op.create_index(
        "ix_audit_user_time", "audit_logs",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_audit_resource", "audit_logs",
        ["resource_type", "resource_id"],
    )

    # ==================================================================
    # 9. nl2sql_histories (FK: users CASCADE, db_instances SET NULL)
    # ==================================================================
    op.create_table(
        "nl2sql_histories",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("instance_id", sa.Uuid(), nullable=True),
        sa.Column("natural_query", sa.Text(), nullable=False),
        sa.Column("generated_sql", sa.Text(), nullable=False),
        sa.Column(
            "execution_result", sa.JSON(), nullable=True,
            comment="Query result {rows, columns}",
        ),
        sa.Column(
            "is_correct", sa.Boolean(), nullable=True,
            comment="User feedback: correct / incorrect",
        ),
        sa.Column("ai_model", sa.String(50), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_nl2sql_histories_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["instance_id"], ["db_instances.id"],
            name="fk_nl2sql_histories_instance_id",
            ondelete="SET NULL",
        ),
    )

    # ==================================================================
    # 10. rag_documents (FK: incidents CASCADE, pgvector embedding)
    # ==================================================================
    op.create_table(
        "rag_documents",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "source_type", sa.String(20), nullable=False, server_default="incident",
            comment="MVP: 'incident' only. Phase 2: 'document', 'playbook', 'manual'",
        ),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column(
            "content", sa.Text(), nullable=False,
            comment="Embedding source text",
        ),
        sa.Column(
            "metadata", sa.JSON(), nullable=False, server_default="{}",
            comment="instance_id, anomaly_type, severity, resolution, was_correct",
        ),
        # pgvector Vector(384) column — use LargeBinary as portable fallback.
        # On PostgreSQL with pgvector, the HNSW index below handles similarity search.
        # The actual column type is overridden to vector(384) via raw SQL on PostgreSQL.
        sa.Column(
            "embedding", sa.LargeBinary(), nullable=True,
            comment="sentence-transformers output (384 dim). Phase 2: 1536 (OpenAI)",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["incidents.id"],
            name="fk_rag_documents_source_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_rag_documents_source", "rag_documents",
        ["source_type", "source_id"],
    )
    op.create_index(
        "idx_rag_documents_created", "rag_documents",
        ["created_at"],
    )

    # On PostgreSQL: convert embedding column to vector(384) and create HNSW index
    try:
        op.execute(
            "ALTER TABLE rag_documents "
            "ALTER COLUMN embedding TYPE vector(384) USING embedding::vector(384)"
        )
        op.execute(
            "CREATE INDEX idx_rag_documents_embedding "
            "ON rag_documents USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )
    except Exception:
        pass  # pgvector not available; embedding stays as LargeBinary

    # ==================================================================
    # 11. alert_channels (FK: users SET NULL)
    # ==================================================================
    op.create_table(
        "alert_channels",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "name", sa.String(255), nullable=False,
            comment='e.g. "#db-alerts"',
        ),
        sa.Column(
            "channel_type", sa.String(20), nullable=False,
            comment="slack / email / webhook / pagerduty",
        ),
        sa.Column(
            "config", sa.JSON(), nullable=False,
            comment="Channel-specific settings (encrypted at rest)",
        ),
        # ARRAY(String) stored as Text for portability (PostgreSQL ARRAY not in SQLite)
        sa.Column(
            "severity_filter", sa.Text(), nullable=False,
            server_default="{critical,warning}",
            comment="PostgreSQL ARRAY; stored as text for portability",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_result", sa.Boolean(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name="fk_alert_channels_created_by",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_alert_channels_type", "alert_channels", ["channel_type"])
    op.create_index(
        "ix_alert_channels_active", "alert_channels", ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    # On PostgreSQL: convert severity_filter to actual ARRAY type
    try:
        op.execute(
            "ALTER TABLE alert_channels "
            "ALTER COLUMN severity_filter TYPE VARCHAR[] "
            "USING severity_filter::VARCHAR[]"
        )
    except Exception:
        pass  # Non-PostgreSQL; stays as Text

    # ==================================================================
    # 12. alert_policies (no FK to other tables)
    # ==================================================================
    op.create_table(
        "alert_policies",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "escalation_chain", sa.JSON(), nullable=False,
            comment="[{level, channel_id, delay_minutes}]",
        ),
        sa.Column(
            "severity", sa.String(10), nullable=False,
            comment="critical / warning / notice / info",
        ),
        sa.Column(
            "cooldown_minutes", sa.Integer(), nullable=False, server_default=sa.text("30"),
            comment="Suppress duplicate alerts for same incident within this window",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ==================================================================
    # 13. alert_history (FK: incidents CASCADE, alert_channels CASCADE,
    #                    alert_policies SET NULL)
    # ==================================================================
    op.create_table(
        "alert_history",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=True),
        sa.Column("escalation_level", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "status", sa.String(15), nullable=False,
            comment="sent / failed / suppressed",
        ),
        sa.Column(
            "response_code", sa.Integer(), nullable=True,
            comment="HTTP response code for webhooks",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "sent_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.id"],
            name="fk_alert_history_incident_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"], ["alert_channels.id"],
            name="fk_alert_history_channel_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"], ["alert_policies.id"],
            name="fk_alert_history_policy_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_alert_history_incident", "alert_history",
        ["incident_id", sa.text("sent_at DESC")],
    )


def downgrade() -> None:
    """Drop all MVP tables in reverse dependency order."""
    op.drop_table("alert_history")
    op.drop_table("alert_policies")
    op.drop_table("alert_channels")

    # Drop pgvector HNSW index before dropping table (safe if not exists)
    try:
        op.execute("DROP INDEX IF EXISTS idx_rag_documents_embedding")
    except Exception:
        pass

    op.drop_table("rag_documents")
    op.drop_table("nl2sql_histories")
    op.drop_table("audit_logs")
    op.drop_table("schema_changes")
    op.drop_table("baselines")
    op.drop_table("incidents")
    op.drop_table("active_sessions")
    op.drop_table("metric_samples")
    op.drop_table("db_instances")
    op.drop_table("users")

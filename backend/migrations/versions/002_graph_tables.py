# Spec: FS-AI-NL2SQL-001, DM-MIG-001
"""002 graph tables -- Schema Knowledge Graph for NL2GraphRAG.

Creates graph_nodes and graph_edges tables for Phase 2 NL2GraphRAG.
graph_nodes stores table/column/metric/concept nodes with pgvector embeddings.
graph_edges stores has_column/foreign_key/metric_source/concept_map relationships.

Revision ID: 002_graph
Revises: 001_initial
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002_graph"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==================================================================
    # 1. graph_nodes (FK: db_instances CASCADE)
    # ==================================================================
    op.create_table(
        "graph_nodes",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "node_type", sa.String(20), nullable=False,
            comment="table / column / metric / concept",
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "metadata", sa.JSON(), nullable=False, server_default="{}",
            comment="Extra metadata (data_type for columns, schema for tables, etc.)",
        ),
        # pgvector Vector(384) -- use LargeBinary as portable fallback.
        # Converted to vector(384) via raw SQL below on PostgreSQL with pgvector.
        sa.Column(
            "embedding", sa.LargeBinary(), nullable=True,
            comment="sentence-transformers embedding (384 dim, all-MiniLM-L6-v2)",
        ),
        sa.Column(
            "instance_id", sa.Uuid(), nullable=True,
            comment="Target DB instance this node belongs to (null for global concepts)",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["instance_id"], ["db_instances.id"],
            name="fk_graph_nodes_instance_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("idx_graph_nodes_type", "graph_nodes", ["node_type"])
    op.create_index("idx_graph_nodes_instance", "graph_nodes", ["instance_id"])

    # Convert embedding column to vector(384) and add HNSW index on PostgreSQL
    conn = op.get_bind()
    conn.execute(sa.text("SAVEPOINT graph_pgvector_check"))
    try:
        conn.execute(sa.text(
            "ALTER TABLE graph_nodes "
            "ALTER COLUMN embedding TYPE vector(384) USING embedding::vector(384)"
        ))
        conn.execute(sa.text(
            "CREATE INDEX idx_graph_nodes_embedding "
            "ON graph_nodes USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        ))
        conn.execute(sa.text("RELEASE SAVEPOINT graph_pgvector_check"))
    except Exception:
        conn.execute(sa.text("ROLLBACK TO SAVEPOINT graph_pgvector_check"))
        # pgvector not available; embedding stays as LargeBinary

    # ==================================================================
    # 2. graph_edges (FK: graph_nodes CASCADE on both sides)
    # ==================================================================
    op.create_table(
        "graph_edges",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column(
            "edge_type", sa.String(30), nullable=False,
            comment="has_column / foreign_key / metric_source / concept_map",
        ),
        sa.Column(
            "metadata", sa.JSON(), nullable=False, server_default="{}",
            comment="Extra edge metadata (constraint_name for FK, etc.)",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["graph_nodes.id"],
            name="fk_graph_edges_source_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"], ["graph_nodes.id"],
            name="fk_graph_edges_target_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "source_id", "target_id", "edge_type",
            name="uq_graph_edges_src_tgt_type",
        ),
    )
    op.create_index("idx_graph_edges_source", "graph_edges", ["source_id"])
    op.create_index("idx_graph_edges_target", "graph_edges", ["target_id"])


def downgrade() -> None:
    """Drop graph tables in reverse dependency order."""
    op.execute(sa.text("DROP INDEX IF EXISTS idx_graph_nodes_embedding"))
    op.drop_table("graph_edges")
    op.drop_table("graph_nodes")

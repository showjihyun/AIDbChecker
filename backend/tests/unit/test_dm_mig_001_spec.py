# Spec: DM-MIG-001
"""Tests for DM-MIG-001 Acceptance Criteria (Alembic Migration).

AC-1: Covered by integration test (test_db_tables.py::test_all_mvp_tables_exist)
AC-2: Destructive operation -- manual only
AC-3: Validates ORM partition-key prerequisites for pg_partman
AC-4: Covered by integration test (test_db_tables.py::test_hnsw_index_exists)

Unit-level tests here verify the ORM model metadata is consistent with
the migration expectations.

IMPORTANT: Do NOT delete the @spec_ref decorator -- it enables AC tracking in CI.
"""

import pytest

from tests.conftest import spec_ref


@spec_ref("DM-MIG-001", "AC-1")
async def test_dm_mig_001_ac1_orm_tables_registered():
    """DM-MIG-001 AC-1: All MVP tables are registered in SQLAlchemy Base.metadata.

    Validates that the ORM models imported via `app.models` produce the
    expected set of table names in Base.metadata, which is what Alembic
    --autogenerate reads to create migrations.
    """
    from app.db.base import Base
    import app.models  # noqa: F401 — triggers model registration

    table_names = {t.name for t in Base.metadata.sorted_tables}

    # Core MVP tables that must exist in ORM metadata
    expected_core = {
        "users",
        "db_instances",
        "metric_samples",
        "active_sessions",
        "incidents",
        "baselines",
        "schema_changes",
        "audit_logs",
        "nl2sql_histories",
        "rag_documents",
    }
    missing = expected_core - table_names
    assert not missing, (
        f"ORM metadata is missing tables: {missing}. "
        "Ensure all models are imported in app/models/__init__.py"
    )


@spec_ref("DM-MIG-001", "AC-2")
def test_dm_mig_001_ac2_alembic_downgrade():
    """DM-MIG-001 AC-2: All migrations have downgrade() defined for rollback."""
    from pathlib import Path

    versions_dir = Path(__file__).resolve().parent.parent.parent / "migrations" / "versions"
    migration_files = list(versions_dir.glob("*.py"))
    assert len(migration_files) >= 1, "No migration files found"

    for mf in migration_files:
        if mf.name.startswith("__"):
            continue
        content = mf.read_text(encoding="utf-8")
        assert "def downgrade()" in content, (
            f"Migration {mf.name} missing downgrade() function"
        )


@spec_ref("DM-MIG-001", "AC-3")
async def test_dm_mig_001_ac3_partitioned_tables_have_composite_pk():
    """DM-MIG-001 AC-3: Partitioned tables have composite PKs with partition key.

    pg_partman requires the partition key to be part of the primary key for
    native range partitioning. This test validates the ORM model prerequisite.

    The actual pg_partman premake=3 partition creation is verified in
    integration tests with live PostgreSQL.

    Partitioned tables per ERD (DM-001):
    - metric_samples: PARTITION BY RANGE (sampled_at)
    - active_sessions: PARTITION BY RANGE (sampled_at)
    - audit_logs: PARTITION BY RANGE (created_at)
    """
    from app.db.base import Base
    import app.models  # noqa: F401

    # metric_samples: composite PK must include sampled_at
    ms_table = Base.metadata.tables.get("metric_samples")
    assert ms_table is not None, "metric_samples table not found in metadata"
    ms_pk_cols = {col.name for col in ms_table.primary_key.columns}
    assert "sampled_at" in ms_pk_cols, (
        f"metric_samples PK must include 'sampled_at' for partitioning, "
        f"got PK columns: {ms_pk_cols}"
    )
    assert len(ms_pk_cols) >= 2, (
        "metric_samples must have composite PK (id + sampled_at)"
    )

    # active_sessions: composite PK must include sampled_at
    as_table = Base.metadata.tables.get("active_sessions")
    assert as_table is not None, "active_sessions table not found in metadata"
    as_pk_cols = {col.name for col in as_table.primary_key.columns}
    assert "sampled_at" in as_pk_cols, (
        f"active_sessions PK must include 'sampled_at' for partitioning, "
        f"got PK columns: {as_pk_cols}"
    )
    assert len(as_pk_cols) >= 2, (
        "active_sessions must have composite PK (id + sampled_at)"
    )

    # audit_logs: composite PK must include created_at
    al_table = Base.metadata.tables.get("audit_logs")
    assert al_table is not None, "audit_logs table not found in metadata"
    al_pk_cols = {col.name for col in al_table.primary_key.columns}
    assert "created_at" in al_pk_cols, (
        f"audit_logs PK must include 'created_at' for partitioning, "
        f"got PK columns: {al_pk_cols}"
    )
    assert len(al_pk_cols) >= 2, (
        "audit_logs must have composite PK (id + created_at)"
    )


@spec_ref("DM-MIG-001", "AC-3")
async def test_dm_mig_001_ac3_partition_key_columns_are_timestamptz():
    """DM-MIG-001 AC-3: Partition key columns use TIMESTAMPTZ (DateTime with timezone).

    pg_partman daily/monthly partitioning requires timezone-aware timestamps.
    """
    from app.db.base import Base
    import app.models  # noqa: F401

    partition_configs = [
        ("metric_samples", "sampled_at"),
        ("active_sessions", "sampled_at"),
        ("audit_logs", "created_at"),
    ]

    for table_name, col_name in partition_configs:
        table = Base.metadata.tables.get(table_name)
        assert table is not None, f"{table_name} not in metadata"

        col = table.columns.get(col_name)
        assert col is not None, f"{table_name}.{col_name} not found"

        # Check it's a DateTime with timezone=True
        col_type = col.type
        assert hasattr(col_type, "timezone"), (
            f"{table_name}.{col_name} should be DateTime(timezone=True), "
            f"got {col_type}"
        )
        assert col_type.timezone is True, (
            f"{table_name}.{col_name} must use timezone=True for pg_partman, "
            f"got timezone={col_type.timezone}"
        )


@spec_ref("DM-MIG-001", "AC-4")
async def test_dm_mig_001_ac4_rag_documents_has_vector_column():
    """DM-MIG-001 AC-4: rag_documents model defines a VECTOR(384) embedding column.

    Unit-level check that the ORM column type is correct. The actual HNSW
    index existence is verified in the integration test.
    """
    from app.models.rag_document import RAGDocument

    # Check the 'embedding' column exists and has the expected type string
    col = RAGDocument.__table__.columns.get("embedding")
    assert col is not None, "rag_documents must have an 'embedding' column"

    col_type_str = str(col.type).upper()
    assert "VECTOR" in col_type_str, (
        f"rag_documents.embedding should be VECTOR type, got {col_type_str}"
    )

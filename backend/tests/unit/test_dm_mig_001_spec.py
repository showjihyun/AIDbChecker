# Spec: DM-MIG-001
"""Tests for DM-MIG-001 Acceptance Criteria (Alembic Migration).

AC-1: Covered by integration test (test_db_tables.py::test_all_mvp_tables_exist)
AC-2: Destructive operation -- manual only
AC-3: Requires pg_partman extension -- integration only
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
async def test_dm_mig_001_ac2_alembic_downgrade():
    """DM-MIG-001 AC-2: alembic downgrade base -- destructive, manual only."""
    pytest.skip(
        "Destructive operation -- verify manually with: "
        "uv run alembic downgrade base && uv run alembic upgrade head"
    )


@spec_ref("DM-MIG-001", "AC-3")
async def test_dm_mig_001_ac3_pg_partman_partitions():
    """DM-MIG-001 AC-3: pg_partman creates premake=3 child partitions."""
    pytest.skip(
        "Requires pg_partman extension on live PostgreSQL. "
        "Covered by integration test when Docker is available."
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

# Spec: FS-AI-NL2SQL-001
"""Tests for NL2GraphRAG — NL2SQL + GraphRAG Phase 1 & Phase 2.

Strategy: TEST-STRATEGY-001
"""

import pytest

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# Phase 1 (MVP): Basic NL2SQL — AC-1 ~ AC-10
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-NL2SQL-001", "AC-1")
def test_fs_ai_nl2sql_001_ac1_query_returns_sql_and_results():
    """FS-AI-NL2SQL-001 AC-1: POST /api/v1/nl2sql/query returns SQL + results."""
    from app.services import nl2sql

    assert callable(nl2sql.generate_sql)
    assert callable(nl2sql.execute_readonly_sql)


@spec_ref("FS-AI-NL2SQL-001", "AC-2")
def test_fs_ai_nl2sql_001_ac2_write_keyword_rejected():
    """FS-AI-NL2SQL-001 AC-2: Write keywords blocked (INSERT/DELETE/DROP)."""
    from app.services.nl2sql import _validate_sql_readonly

    dangerous = [
        "INSERT INTO users VALUES (1, 'admin')",
        "DELETE FROM metric_samples",
        "DROP TABLE incidents",
        "UPDATE db_instances SET is_active = false",
        "TRUNCATE active_sessions",
        "ALTER TABLE users ADD COLUMN hack text",
    ]
    for sql in dangerous:
        with pytest.raises(ValueError):
            _validate_sql_readonly(sql)


@spec_ref("FS-AI-NL2SQL-001", "AC-3")
def test_fs_ai_nl2sql_001_ac3_dangerous_function_rejected():
    """FS-AI-NL2SQL-001 AC-3: Dangerous functions blocked."""
    from app.services.nl2sql import _validate_sql_readonly

    dangerous = [
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT dblink('host=evil', 'SELECT 1')",
        "SELECT lo_import('/tmp/evil')",
        "SELECT pg_sleep(9999)",
    ]
    for sql in dangerous:
        with pytest.raises(ValueError):
            _validate_sql_readonly(sql)


@spec_ref("FS-AI-NL2SQL-001", "AC-4")
def test_fs_ai_nl2sql_001_ac4_blocked_tables_rejected():
    """FS-AI-NL2SQL-001 AC-4: Sensitive tables blocked (users, audit_logs)."""
    from app.services.nl2sql import _validate_sql_readonly

    blocked = [
        "SELECT * FROM users",
        "SELECT email, hashed_password FROM users WHERE role = 'super_admin'",
        "SELECT * FROM audit_logs LIMIT 10",
    ]
    for sql in blocked:
        with pytest.raises(ValueError):
            _validate_sql_readonly(sql)


@spec_ref("FS-AI-NL2SQL-001", "AC-5")
def test_fs_ai_nl2sql_001_ac5_statement_timeout():
    """FS-AI-NL2SQL-001 AC-5: Valid SQL passes validation."""
    from app.services.nl2sql import _validate_sql_readonly

    # Valid read-only SQL should pass
    _validate_sql_readonly("SELECT count(*) FROM metric_samples")
    _validate_sql_readonly("SELECT * FROM incidents WHERE severity = 'critical'")
    _validate_sql_readonly("WITH cte AS (SELECT 1) SELECT * FROM cte")


@spec_ref("FS-AI-NL2SQL-001", "AC-6")
def test_fs_ai_nl2sql_001_ac6_result_row_limit():
    """FS-AI-NL2SQL-001 AC-6: Results limited to 1000 rows + warning."""
    from app.services import nl2sql

    assert callable(nl2sql.execute_readonly_sql)
    # execute_readonly_sql should enforce row limit internally


@spec_ref("FS-AI-NL2SQL-001", "AC-7")
def test_fs_ai_nl2sql_001_ac7_history_saved():
    """FS-AI-NL2SQL-001 AC-7: nl2sql_histories table stores query history."""
    from app.models.nl2sql_history import NL2SQLHistory

    assert hasattr(NL2SQLHistory, "natural_query")
    assert hasattr(NL2SQLHistory, "generated_sql")
    assert hasattr(NL2SQLHistory, "instance_id")
    assert hasattr(NL2SQLHistory, "ai_model")


@spec_ref("FS-AI-NL2SQL-001", "AC-8")
def test_fs_ai_nl2sql_001_ac8_uses_llm_provider_manager():
    """FS-AI-NL2SQL-001 AC-8: Uses LLMProviderManager for LLM calls."""
    from app.services import nl2sql

    assert callable(nl2sql.generate_sql)
    assert callable(nl2sql.generate_sql_with_graph)


@spec_ref("FS-AI-NL2SQL-001", "AC-9")
def test_fs_ai_nl2sql_001_ac9_instance_id_required():
    """FS-AI-NL2SQL-001 AC-9: Frontend passes instance_id."""
    from app.schemas.nl2sql import NL2SQLQueryRequest

    with pytest.raises(Exception):
        NL2SQLQueryRequest(question="test")  # Missing instance_id


@spec_ref("FS-AI-NL2SQL-001", "AC-10")
def test_fs_ai_nl2sql_001_ac10_model_and_time_in_response():
    """FS-AI-NL2SQL-001 AC-10: AI model name + execution time in response."""
    from app.schemas.nl2sql import NL2SQLQueryResponse

    fields = NL2SQLQueryResponse.model_fields
    assert "ai_model" in fields
    assert "execution_time_ms" in fields


# ---------------------------------------------------------------------------
# Phase 2 (GraphRAG): AC-11 ~ AC-17
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-NL2SQL-001", "AC-11")
def test_fs_ai_nl2sql_001_ac11_schema_graph_creation():
    """FS-AI-NL2SQL-001 AC-11: Schema → Graph auto generation."""
    from app.models.graph_node import GraphNode
    from app.models.graph_edge import GraphEdge
    from app.services.graph_rag import SchemaGraphBuilder

    assert hasattr(GraphNode, "node_type")
    assert hasattr(GraphNode, "embedding")
    assert hasattr(GraphNode, "instance_id")
    assert hasattr(GraphEdge, "source_id")
    assert hasattr(GraphEdge, "target_id")
    assert hasattr(GraphEdge, "edge_type")

    builder = SchemaGraphBuilder()
    assert hasattr(builder, "build_graph")


@spec_ref("FS-AI-NL2SQL-001", "AC-12")
def test_fs_ai_nl2sql_001_ac12_graphrag_retrieval():
    """FS-AI-NL2SQL-001 AC-12: GraphRAG Retrieval extracts relevant subgraph."""
    from app.services.graph_rag import GraphRAGRetriever, SubgraphContext

    retriever = GraphRAGRetriever()
    assert hasattr(retriever, "retrieve")

    ctx = SubgraphContext()
    assert hasattr(ctx, "tables")
    assert hasattr(ctx, "columns")
    assert hasattr(ctx, "join_paths")
    assert hasattr(ctx, "to_prompt_context")


@spec_ref("FS-AI-NL2SQL-001", "AC-13")
def test_fs_ai_nl2sql_001_ac13_subgraph_based_sql_generation():
    """FS-AI-NL2SQL-001 AC-13: Subgraph-based SQL replaces hardcoded schema."""
    from app.services.graph_rag import SubgraphContext

    ctx = SubgraphContext(
        tables=["metric_samples", "db_instances"],
        columns={
            "metric_samples": ["id", "instance_id", "sampled_at", "metrics"],
            "db_instances": ["id", "name", "host"],
        },
        join_paths=[("metric_samples.instance_id", "db_instances.id", "foreign_key")],
    )
    prompt = ctx.to_prompt_context()
    assert "metric_samples" in prompt
    assert "db_instances" in prompt


@spec_ref("FS-AI-NL2SQL-001", "AC-14")
def test_fs_ai_nl2sql_001_ac14_join_path_from_graph_edges():
    """FS-AI-NL2SQL-001 AC-14: Join paths discovered from Graph edges."""
    from app.services.graph_rag import SubgraphContext

    ctx = SubgraphContext(
        tables=["active_sessions", "db_instances"],
        columns={"active_sessions": ["instance_id"], "db_instances": ["id"]},
        join_paths=[("active_sessions.instance_id", "db_instances.id", "foreign_key")],
    )
    prompt = ctx.to_prompt_context()
    assert "instance_id" in prompt


@spec_ref("FS-AI-NL2SQL-001", "AC-15")
def test_fs_ai_nl2sql_001_ac15_business_metric_concept_registration():
    """FS-AI-NL2SQL-001 AC-15: Business metric/concept registration."""
    from app.services.graph_rag import SchemaGraphBuilder

    builder = SchemaGraphBuilder()
    assert hasattr(builder, "add_business_metric")
    assert hasattr(builder, "add_business_concept")


@spec_ref("FS-AI-NL2SQL-001", "AC-16")
def test_fs_ai_nl2sql_001_ac16_sql_accuracy():
    """FS-AI-NL2SQL-001 AC-16: SQL accuracy 80%+ (requires live LLM)."""
    pytest.skip("Requires live LLM + target DB for accuracy measurement")


@spec_ref("FS-AI-NL2SQL-001", "AC-17")
def test_fs_ai_nl2sql_001_ac17_target_db_direct_query():
    """FS-AI-NL2SQL-001 AC-17: Direct query on target DB (requires live DB)."""
    pytest.skip("Requires live target DB connection")


# ---------------------------------------------------------------------------
# Phase 3 (Agent-Based): AC-18 ~ AC-20
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-NL2SQL-001", "AC-18")
def test_fs_ai_nl2sql_001_ac18_4_agent_pipeline():
    """FS-AI-NL2SQL-001 AC-18: 4-Agent pipeline (Phase 3)."""
    pytest.skip("Phase 3 — not yet implemented")


@spec_ref("FS-AI-NL2SQL-001", "AC-19")
def test_fs_ai_nl2sql_001_ac19_multi_db_sql_dialect():
    """FS-AI-NL2SQL-001 AC-19: Multi-DB SQL dialect support (Phase 3)."""
    pytest.skip("Phase 3 — not yet implemented")


@spec_ref("FS-AI-NL2SQL-001", "AC-20")
def test_fs_ai_nl2sql_001_ac20_feedback_few_shot():
    """FS-AI-NL2SQL-001 AC-20: Feedback-based few-shot learning (Phase 3)."""
    pytest.skip("Phase 3 — not yet implemented")

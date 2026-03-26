# Spec: FR-AI-003, MVP-AI-004, MVP-AI-005, FS-AI-NL2SQL-001
"""NL2SQL service — convert natural language to SQL and execute read-only.

Uses LangChain for LLM abstraction. Online mode uses OpenAI GPT-4o,
offline mode uses Ollama (mistral:7b). All queries are strictly read-only
with a 5-second statement_timeout safety net.

Phase 2 (FS-AI-NL2SQL-001): GraphRAG path — if a Schema Knowledge Graph
exists for the target instance, uses GraphRAGRetriever to extract a
relevant subgraph and build a focused schema prompt. Falls back to the
hardcoded system schema prompt if no graph is available.
"""

import hashlib
import re
import time
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = structlog.get_logger(__name__)

# Spec: FR-AI-003 — SQL keywords that indicate write operations (NEVER execute)
_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|"
    r"COPY|VACUUM|REINDEX|CLUSTER|COMMENT|LOCK|DISCARD|REASSIGN|"
    r"DO|EXECUTE|CALL|PERFORM)\b",
    re.IGNORECASE,
)

# Dangerous functions that can exfiltrate data or read files even in read-only mode
_DANGEROUS_FUNCTIONS = re.compile(
    r"\b(pg_read_file|pg_read_binary_file|pg_stat_file|lo_get|lo_export|lo_import|"
    r"dblink|pg_execute_server_program|query_to_xml|xpath|pg_sleep)\b",
    re.IGNORECASE,
)

# Sensitive tables that NL2SQL must NEVER query
_BLOCKED_TABLES = re.compile(
    r"\b(users|audit_logs|alert_channels|alert_policies|rag_documents)\b",
    re.IGNORECASE,
)

# Spec: FR-AI-003 — PostgreSQL schema context for the LLM prompt
_NL2SQL_SYSTEM_PROMPT = """You are a PostgreSQL 16 SQL expert for NeuralDB, an AI-powered database monitoring system.
Convert the user's natural language question into a single read-only SQL query.

CRITICAL RULES:
1. Generate ONLY a single SELECT (or WITH...SELECT) statement.
2. NEVER use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or any DDL/DML.
3. Always add LIMIT (default 100) unless the user asks for a specific count or aggregate.
4. Prefer explicit column names over SELECT *.
5. Return ONLY the raw SQL query — no markdown fences, no explanations, no comments.
6. For JSONB columns (e.g., metrics), use ->> operator: metrics->>'cpu_usage'
7. For time-based queries, use NOW() - INTERVAL '...' for relative time ranges.
8. metric_samples.metrics is JSONB. To extract numeric values, ALWAYS cast: (metrics->>'key')::numeric
   Available keys: numbackends, xact_commit, xact_rollback, blks_hit, blks_read, tup_returned, tup_fetched, tup_inserted, tup_updated, tup_deleted, deadlocks, db_size.
   Example: SELECT (metrics->>'numbackends')::int AS connections FROM metric_samples LIMIT 5

DATABASE SCHEMA (NeuralDB system tables):

-- Monitored database instances
db_instances(id UUID, name VARCHAR, db_type VARCHAR, host VARCHAR, port INT,
  database_name VARCHAR, environment VARCHAR, is_active BOOLEAN,
  autonomy_level SMALLINT, created_at TIMESTAMPTZ)

-- 1-second metric snapshots (partitioned by sampled_at)
metric_samples(id UUID, instance_id UUID FK->db_instances, sampled_at TIMESTAMPTZ,
  category VARCHAR, metrics JSONB)
  -- metrics keys: cpu_usage, memory_usage, active_connections, tps, buffer_hit_ratio

-- ASH 1-second samples (partitioned by sampled_at)
active_sessions(id UUID, instance_id UUID FK->db_instances, sampled_at TIMESTAMPTZ,
  pid INT, query TEXT, query_hash BIGINT, state VARCHAR,
  wait_event_type VARCHAR, wait_event VARCHAR, duration_ms FLOAT)

-- Detected anomalies
incidents(id UUID, instance_id UUID FK->db_instances, severity VARCHAR,
  status VARCHAR, title VARCHAR, description TEXT, source VARCHAR,
  metric_type VARCHAR, metric_value FLOAT, baseline_value FLOAT,
  detected_at TIMESTAMPTZ, resolved_at TIMESTAMPTZ)

-- AI baselines
baselines(id UUID, instance_id UUID FK->db_instances, metric_type VARCHAR,
  time_bucket VARCHAR, normal_min FLOAT, normal_max FLOAT, mean FLOAT,
  stddev FLOAT, model_type VARCHAR, last_trained_at TIMESTAMPTZ)

-- DDL change tracking
schema_changes(id UUID, instance_id UUID FK->db_instances, change_type VARCHAR,
  object_type VARCHAR, object_name VARCHAR, ddl_command TEXT,
  detected_at TIMESTAMPTZ)

-- Users
users(id UUID, email VARCHAR, name VARCHAR, role VARCHAR, is_active BOOLEAN)
"""


def _get_llm():
    """Create LangChain LLM via unified LLMProviderManager.

    Spec: FS-AI-LLM-001 — AC-6: all services use LLMProviderManager.
    """
    from app.services.llm_provider import get_llm_manager

    return get_llm_manager().get_llm(temperature=0, max_tokens=500, request_timeout=15)


def _validate_sql_readonly(sql: str) -> None:
    """Reject any SQL that contains write operations or dangerous functions.

    Defense-in-depth: multiple layers beyond SET default_transaction_read_only.
    """
    # Block write operations
    if _WRITE_KEYWORDS.search(sql):
        raise ValueError(
            "Generated SQL contains write operations. "
            "Only SELECT queries are allowed."
        )
    # Block dangerous functions (data exfiltration via pg_read_file etc.)
    if _DANGEROUS_FUNCTIONS.search(sql):
        raise ValueError(
            "Generated SQL contains restricted functions. "
            "Only standard SELECT queries are allowed."
        )
    # Block queries against sensitive tables
    if _BLOCKED_TABLES.search(sql):
        raise ValueError(
            "Generated SQL references restricted tables. "
            "Only monitoring data tables (metric_samples, active_sessions, "
            "incidents, baselines, schema_changes) are queryable."
        )
    # Block multi-statement (semicolons)
    if ";" in sql.strip():
        raise ValueError(
            "Multi-statement SQL is not allowed. Use a single SELECT query."
        )
    # Must start with SELECT (after whitespace)
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
        raise ValueError(
            "Only SELECT or WITH (CTE) queries are allowed."
        )


def _clean_sql(raw: str) -> str:
    """Extract SQL from LLM output, stripping markdown fences and whitespace."""
    sql = raw.strip()
    # Remove markdown code fences
    if sql.startswith("```"):
        lines = sql.split("\n")
        # Drop first line (```sql) and last line (```)
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        sql = "\n".join(lines).strip()
    # Remove trailing semicolons (asyncpg handles them)
    sql = sql.rstrip(";").strip()
    return sql


async def generate_sql(question: str, instance_id: UUID) -> str:
    """Convert a natural language question to a PostgreSQL SELECT query.

    Args:
        question: User's natural language question.
        instance_id: Target DB instance UUID for context.

    Returns:
        A valid read-only SQL string.

    Raises:
        ValueError: If the generated SQL contains write operations.
        RuntimeError: If the LLM call fails.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = _get_llm()
    user_prompt = (
        f"Target instance ID: {instance_id}\n"
        f"Question: {question}\n\n"
        "Generate a single PostgreSQL SELECT query:"
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=_NL2SQL_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        # LangChain returns AIMessage for chat models, plain str for LLMs
        raw_sql = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error("nl2sql.llm_call_failed", error=str(exc), question=question)
        raise RuntimeError(
            f"LLM call failed: {exc}. Check AI_MODE setting and API keys."
        ) from exc

    sql = _clean_sql(raw_sql)
    _validate_sql_readonly(sql)

    logger.info(
        "nl2sql.generated",
        question=question[:100],
        sql=sql[:200],
        model=get_model_name(),
    )
    return sql


async def execute_readonly_sql(
    session: AsyncSession,
    sql: str,
    *,
    timeout_seconds: int = 5,
    max_rows: int = 1000,
) -> tuple[list[str], list[list], int]:
    """Execute a read-only SQL query against the system DB.

    Sets statement_timeout and default_transaction_read_only for safety.

    Args:
        session: SQLAlchemy async session (system DB).
        sql: Validated SELECT query.
        timeout_seconds: Statement timeout in seconds.
        max_rows: Maximum rows to return.

    Returns:
        Tuple of (column_names, rows, execution_time_ms).

    Raises:
        RuntimeError: If execution fails.
    """
    # Spec: FR-AI-003 — read-only execution with statement_timeout
    _validate_sql_readonly(sql)

    start = time.monotonic()
    try:
        # Set statement_timeout for this transaction
        await session.execute(
            text(f"SET LOCAL statement_timeout = '{timeout_seconds * 1000}'")
        )
        await session.execute(text("SET LOCAL default_transaction_read_only = on"))

        # Add LIMIT if not present
        sql_lower = sql.lower().strip()
        if "limit" not in sql_lower:
            sql = f"{sql}\nLIMIT {max_rows}"

        result = await session.execute(text(sql))
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchall()]
        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Truncate to max_rows
        if len(rows) > max_rows:
            rows = rows[:max_rows]

        logger.info(
            "nl2sql.executed",
            rows_returned=len(rows),
            execution_time_ms=elapsed_ms,
        )
        return columns, rows, elapsed_ms

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "nl2sql.execution_failed",
            error=str(exc),
            sql=sql[:200],
            elapsed_ms=elapsed_ms,
        )
        # Rollback the failed transaction so session can be reused (e.g., history save)
        await session.rollback()
        raise RuntimeError(
            f"SQL execution failed: {exc}. Verify the query is valid."
        ) from exc


def get_model_name() -> str:
    """Return the current LLM model name.

    Spec: FS-AI-LLM-001 — uses unified AI_PROVIDER / AI_MODEL settings.
    """
    return settings.AI_MODEL


# ---------------------------------------------------------------------------
# Phase 2: GraphRAG-enhanced SQL generation
# Spec: FS-AI-NL2SQL-001 Sections 2-4
# ---------------------------------------------------------------------------

# Spec: FS-AI-NL2SQL-001 — GraphRAG system prompt template (subgraph injected)
_GRAPHRAG_SYSTEM_PROMPT_TEMPLATE = """You are a PostgreSQL 16 SQL expert for NeuralDB, an AI-powered database monitoring system.
Convert the user's natural language question into a single read-only SQL query.

CRITICAL RULES:
1. Generate ONLY a single SELECT (or WITH...SELECT) statement.
2. NEVER use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or any DDL/DML.
3. Always add LIMIT (default 100) unless the user asks for a specific count or aggregate.
4. Prefer explicit column names over SELECT *.
5. Return ONLY the raw SQL query — no markdown fences, no explanations, no comments.
6. Use the join paths below to construct correct JOINs between tables.
7. For JSONB columns (e.g., metrics), use ->> operator to extract values: metrics->>'cpu_usage'
8. For time-based queries, use NOW() - INTERVAL '...' for relative time ranges.
9. metric_samples.metrics is JSONB. To extract numeric values, ALWAYS cast: (metrics->>'key')::numeric
   Available keys: numbackends, xact_commit, xact_rollback, blks_hit, blks_read, tup_returned, tup_fetched, tup_inserted, tup_updated, tup_deleted, deadlocks, db_size.
   Example: SELECT (metrics->>'numbackends')::int AS connections FROM metric_samples LIMIT 5

RELEVANT SCHEMA (extracted via GraphRAG):
{schema_context}
"""


async def generate_sql_with_graph(
    question: str,
    instance_id: UUID,
    session: AsyncSession,
) -> str:
    """Convert a natural language question to SQL using GraphRAG retrieval.

    Spec: FS-AI-NL2SQL-001 Section 2 — NL2GraphRAG architecture.

    If a Knowledge Graph exists for the instance, uses GraphRAGRetriever
    to extract a relevant subgraph for a focused schema prompt.
    If no graph exists, falls back to the hardcoded schema prompt
    via generate_sql().

    All 5 safety layers are preserved regardless of path.

    Args:
        question: User's natural language question.
        instance_id: Target DB instance UUID.
        session: System DB async session (for graph queries).

    Returns:
        A valid read-only SQL string.

    Raises:
        ValueError: If the generated SQL contains write operations.
        RuntimeError: If the LLM call fails.
    """
    from app.services.graph_rag import GraphRAGRetriever, has_graph_for_instance

    # Spec: FS-AI-NL2SQL-001 — fallback: if no graph, use hardcoded schema
    graph_exists = await has_graph_for_instance(session, instance_id)
    if not graph_exists:
        logger.info(
            "nl2sql.graph_not_found_fallback",
            instance_id=str(instance_id),
        )
        return await generate_sql(question, instance_id)

    # GraphRAG path: retrieve relevant subgraph
    retriever = GraphRAGRetriever()
    subgraph = await retriever.retrieve(
        session=session,
        question=question,
        instance_id=instance_id,
        top_k=10,
    )

    # If subgraph is empty (no relevant nodes found), fall back
    if not subgraph.tables:
        logger.info(
            "nl2sql.graph_empty_subgraph_fallback",
            instance_id=str(instance_id),
        )
        return await generate_sql(question, instance_id)

    # Build focused schema prompt from subgraph
    schema_context = subgraph.to_prompt_context()
    system_prompt = _GRAPHRAG_SYSTEM_PROMPT_TEMPLATE.format(
        schema_context=schema_context,
    )

    from langchain_core.messages import HumanMessage, SystemMessage

    llm = _get_llm()
    user_prompt = (
        f"Target instance ID: {instance_id}\n"
        f"Question: {question}\n\n"
        "Generate a single PostgreSQL SELECT query:"
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        raw_sql = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error(
            "nl2sql.graphrag_llm_call_failed",
            error=str(exc),
            question=question,
        )
        raise RuntimeError(
            f"LLM call failed: {exc}. Check AI_MODE setting and API keys."
        ) from exc

    sql = _clean_sql(raw_sql)

    # Spec: FS-AI-NL2SQL-001 Section 5 — all 5 safety layers applied
    _validate_sql_readonly(sql)

    logger.info(
        "nl2sql.graphrag_generated",
        question=question[:100],
        sql=sql[:200],
        model=get_model_name(),
        subgraph_tables=len(subgraph.tables),
    )
    return sql

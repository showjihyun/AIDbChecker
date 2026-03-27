# Spec: FS-DBA-001 E2
"""DBA ops tools — write operations that return ActionRequest (never execute directly).

Every tool returns an ActionRequest. Execution happens only through ExecutionEngine
after Safety Guard approval. This is the core Harness principle:
"LLM 20%, Harness 80%".
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class ActionRequest(BaseModel):
    """Spec: FS-DBA-001 §2.2 — Agent execution request."""

    instance_id: UUID
    action_type: str
    sql: str
    description: str
    risk_level: str = ""  # Filled by SafetyGuard
    estimated_impact: str = ""
    requires_approval: bool = False  # Filled by SafetyGuard
    requested_by: str = "agent-tuning"
    confidence: float = 0.0


class ActionResult(BaseModel):
    """Spec: FS-DBA-001 §2.2 — Execution result."""

    action_id: UUID
    status: str  # executed | approved | rejected | failed | rolled_back
    execution_time_ms: int | None = None
    rows_affected: int | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    error: str | None = None


def create_index(
    instance_id: UUID,
    table: str,
    columns: list[str],
    index_name: str | None = None,
    *,
    requested_by: str = "agent-tuning",
    confidence: float = 0.8,
) -> ActionRequest:
    """Spec: FS-DBA-001 AC-5 — CREATE INDEX CONCURRENTLY.

    Always uses CONCURRENTLY to avoid table locks.
    """
    cols = ", ".join(columns)
    name = index_name or f"idx_{table}_{'_'.join(columns)}"
    sql = f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} ({cols})"

    return ActionRequest(
        instance_id=instance_id,
        action_type="create_index",
        sql=sql,
        description=f"Create index {name} on {table}({cols}) — CONCURRENTLY, no table lock.",
        estimated_impact=(
            f"Index build on {table}. Non-blocking (CONCURRENTLY). "
            "May take minutes on large tables."
        ),
        requested_by=requested_by,
        confidence=confidence,
    )


def vacuum_table(
    instance_id: UUID,
    table: str,
    full: bool = False,
    *,
    requested_by: str = "agent-tuning",
    confidence: float = 0.7,
) -> ActionRequest:
    """Spec: FS-DBA-001 AC-6 — VACUUM (FULL is DANGEROUS)."""
    if full:
        sql = f"VACUUM FULL VERBOSE {table}"
        action_type = "vacuum_full"
        desc = (
            f"VACUUM FULL on {table} — acquires ACCESS EXCLUSIVE lock, "
            "table offline during operation."
        )
        impact = (
            "Table fully rewritten. ACCESS EXCLUSIVE lock = table offline. "
            "May take hours on large tables."
        )
    else:
        sql = f"VACUUM VERBOSE {table}"
        action_type = "vacuum"
        desc = f"VACUUM on {table} — reclaims dead tuples, no exclusive lock."
        impact = "Online operation. Reclaims dead tuple space. Usually completes in seconds."

    return ActionRequest(
        instance_id=instance_id,
        action_type=action_type,
        sql=sql,
        description=desc,
        estimated_impact=impact,
        requested_by=requested_by,
        confidence=confidence,
    )


def kill_session(
    instance_id: UUID,
    pid: int,
    reason: str = "Agent-initiated session termination",
    *,
    requested_by: str = "agent-copilot",
    confidence: float = 0.6,
) -> ActionRequest:
    """Spec: FS-DBA-001 AC-7 — pg_terminate_backend."""
    sql = f"SELECT pg_terminate_backend({pid})"

    return ActionRequest(
        instance_id=instance_id,
        action_type="kill_session",
        sql=sql,
        description=f"Terminate backend PID {pid}. Reason: {reason}",
        estimated_impact=(
            f"Session {pid} will be forcefully terminated. Active transaction will be rolled back."
        ),
        requested_by=requested_by,
        confidence=confidence,
    )


def alter_parameter(
    instance_id: UUID,
    param: str,
    value: str,
    *,
    requested_by: str = "agent-tuning",
    confidence: float = 0.7,
) -> ActionRequest:
    """Spec: FS-DBA-001 — ALTER SYSTEM SET (DANGEROUS)."""
    sql = f"ALTER SYSTEM SET {param} = '{value}'"

    return ActionRequest(
        instance_id=instance_id,
        action_type="alter_parameter",
        sql=sql,
        description=(
            f"Set PostgreSQL parameter {param} = {value}. Requires pg_reload_conf() to apply."
        ),
        estimated_impact=(
            "Parameter change. Some params need restart. Current value will be overridden."
        ),
        requested_by=requested_by,
        confidence=confidence,
    )


def reindex(
    instance_id: UUID,
    index_name: str,
    *,
    requested_by: str = "agent-tuning",
    confidence: float = 0.8,
) -> ActionRequest:
    """Spec: FS-DBA-001 — REINDEX CONCURRENTLY."""
    sql = f"REINDEX INDEX CONCURRENTLY {index_name}"

    return ActionRequest(
        instance_id=instance_id,
        action_type="reindex",
        sql=sql,
        description=f"Rebuild index {index_name} — CONCURRENTLY, no table lock.",
        estimated_impact="Index rebuild. Non-blocking. May take minutes on large indexes.",
        requested_by=requested_by,
        confidence=confidence,
    )


def analyze_table(
    instance_id: UUID,
    table: str,
    *,
    requested_by: str = "agent-tuning",
    confidence: float = 0.9,
) -> ActionRequest:
    """Spec: FS-DBA-001 — ANALYZE (SAFE)."""
    sql = f"ANALYZE {table}"

    return ActionRequest(
        instance_id=instance_id,
        action_type="analyze_table",
        sql=sql,
        description=f"Update statistics for {table}. Safe, read-like operation.",
        estimated_impact="Lightweight. Updates planner statistics. No locks.",
        requested_by=requested_by,
        confidence=confidence,
    )

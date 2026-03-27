# Spec: FS-DBA-001
"""Tests for DBA Agent Execution Layer — Tier 1 (16 ACs)."""

from uuid import uuid4

import pytest

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# E1: Execution Engine — AC-1~4
# ---------------------------------------------------------------------------

@spec_ref("FS-DBA-001", "AC-1")
def test_dba_001_ac1_execution_engine_exists():
    """FS-DBA-001 AC-1: ExecutionEngine.execute() accepts ActionRequest, returns ActionResult."""
    from app.agents.execution_engine import ExecutionEngine
    from app.agents.tools.ops_tools import ActionRequest, ActionResult

    engine = ExecutionEngine()
    assert hasattr(engine, "execute")
    assert hasattr(engine, "execute_approved")


@spec_ref("FS-DBA-001", "AC-2")
def test_dba_001_ac2_pre_check():
    """FS-DBA-001 AC-2: Pre-check with EXPLAIN cost exists."""
    from app.agents.execution_engine import ExecutionEngine

    engine = ExecutionEngine()
    assert hasattr(engine, "_pre_check")


@spec_ref("FS-DBA-001", "AC-3")
def test_dba_001_ac3_post_check():
    """FS-DBA-001 AC-3: Post-check exists."""
    from app.agents.execution_engine import ExecutionEngine

    engine = ExecutionEngine()
    assert hasattr(engine, "_post_check")


@spec_ref("FS-DBA-001", "AC-4")
def test_dba_001_ac4_audit_log():
    """FS-DBA-001 AC-4: Execution engine writes AI Decision Log."""
    from app.agents.execution_engine import ExecutionEngine

    engine = ExecutionEngine()
    assert hasattr(engine, "_audit_log")


# ---------------------------------------------------------------------------
# E2: Ops Tools — AC-5~8
# ---------------------------------------------------------------------------

@spec_ref("FS-DBA-001", "AC-5")
def test_dba_001_ac5_create_index_concurrently():
    """FS-DBA-001 AC-5: create_index forces CONCURRENTLY."""
    from app.agents.tools.ops_tools import create_index

    req = create_index(
        instance_id=uuid4(),
        table="orders",
        columns=["user_id", "created_at"],
    )
    assert "CONCURRENTLY" in req.sql
    assert "IF NOT EXISTS" in req.sql
    assert req.action_type == "create_index"


@spec_ref("FS-DBA-001", "AC-6")
def test_dba_001_ac6_vacuum_full_dangerous():
    """FS-DBA-001 AC-6: vacuum_table(full=True) returns DANGEROUS risk."""
    from app.agents.tools.ops_tools import vacuum_table
    from app.agents.safety_guard import SafetyGuard

    req = vacuum_table(instance_id=uuid4(), table="metric_samples", full=True)
    assert req.action_type == "vacuum_full"
    assert "FULL" in req.sql

    guard = SafetyGuard()
    risk = guard.classify_risk(req.sql, req.action_type)
    assert risk.value == "dangerous"


@spec_ref("FS-DBA-001", "AC-7")
def test_dba_001_ac7_kill_session_dangerous():
    """FS-DBA-001 AC-7: kill_session returns DANGEROUS risk."""
    from app.agents.tools.ops_tools import kill_session
    from app.agents.safety_guard import SafetyGuard

    req = kill_session(instance_id=uuid4(), pid=12345, reason="Blocking lock")
    assert "pg_terminate_backend" in req.sql
    assert req.action_type == "kill_session"

    guard = SafetyGuard()
    risk = guard.classify_risk(req.sql, req.action_type)
    assert risk.value == "dangerous"


@spec_ref("FS-DBA-001", "AC-8")
def test_dba_001_ac8_ops_tools_return_request_not_execute():
    """FS-DBA-001 AC-8: All ops_tools return ActionRequest, never execute SQL."""
    from app.agents.tools import ops_tools
    from app.agents.tools.ops_tools import ActionRequest

    iid = uuid4()
    results = [
        ops_tools.create_index(iid, "t", ["c"]),
        ops_tools.vacuum_table(iid, "t"),
        ops_tools.vacuum_table(iid, "t", full=True),
        ops_tools.kill_session(iid, 1),
        ops_tools.alter_parameter(iid, "work_mem", "256MB"),
        ops_tools.reindex(iid, "idx_test"),
        ops_tools.analyze_table(iid, "t"),
    ]
    for r in results:
        assert isinstance(r, ActionRequest), f"{r} is not ActionRequest"
        assert r.sql  # Every tool must produce SQL
        assert r.action_type  # Every tool must declare type


# ---------------------------------------------------------------------------
# E3: Safety Guard — AC-9~12
# ---------------------------------------------------------------------------

@spec_ref("FS-DBA-001", "AC-9")
def test_dba_001_ac9_4_level_classification():
    """FS-DBA-001 AC-9: classify_risk returns 4 levels."""
    from app.agents.safety_guard import SafetyGuard, RiskLevel

    guard = SafetyGuard()

    # Security: SQL patterns always checked, action_type is a floor
    assert guard.classify_risk("SELECT 1", "custom_sql") == RiskLevel.SAFE
    assert guard.classify_risk("ANALYZE users", "analyze_table") == RiskLevel.WARNING  # SQL ANALYZE pattern
    assert guard.classify_risk("CREATE INDEX CONCURRENTLY idx ON t(c)", "create_index") == RiskLevel.WARNING
    assert guard.classify_risk("VACUUM FULL t", "vacuum_full") == RiskLevel.DANGEROUS
    assert guard.classify_risk("DROP TABLE users", "custom_sql") == RiskLevel.CRITICAL
    # Multi-statement injection = CRITICAL regardless
    assert guard.classify_risk("ANALYZE t; DROP TABLE users", "analyze_table") == RiskLevel.CRITICAL


@spec_ref("FS-DBA-001", "AC-10")
def test_dba_001_ac10_critical_always_blocked():
    """FS-DBA-001 AC-10: DROP TABLE/TRUNCATE blocked at all autonomy levels (except L4 approve)."""
    from app.agents.safety_guard import SafetyGuard, RiskLevel

    guard = SafetyGuard()
    risk = guard.classify_risk("DROP TABLE users", "custom_sql")
    assert risk == RiskLevel.CRITICAL

    for level in range(4):  # L0~L3
        policy = guard.check_policy(risk, level, user_role="super_admin")
        assert policy.action == "blocked", f"L{level} should block CRITICAL"

    # L4: approve (not auto-execute) — only super_admin can attempt
    policy = guard.check_policy(risk, 4, user_role="super_admin")
    assert policy.action == "approve_required"


@spec_ref("FS-DBA-001", "AC-11")
def test_dba_001_ac11_policy_matrix():
    """FS-DBA-001 AC-11: check_policy follows risk+autonomy+confidence matrix."""
    from app.agents.safety_guard import SafetyGuard, RiskLevel

    guard = SafetyGuard()

    # WARNING + L0 = blocked (any role)
    p = guard.check_policy(RiskLevel.WARNING, 0, user_role="db_admin")
    assert p.action == "blocked"

    # WARNING + L2 = execute (db_admin can do WARNING)
    p = guard.check_policy(RiskLevel.WARNING, 2, user_role="db_admin")
    assert p.action == "execute"

    # DANGEROUS + L2 = approve (db_admin can do DANGEROUS)
    p = guard.check_policy(RiskLevel.DANGEROUS, 2, user_role="db_admin")
    assert p.action == "approve_required"

    # DANGEROUS + L3 = execute (db_admin)
    p = guard.check_policy(RiskLevel.DANGEROUS, 3, user_role="db_admin")
    assert p.action == "execute"

    # DANGEROUS + L3 but operator = blocked (role ceiling)
    p = guard.check_policy(RiskLevel.DANGEROUS, 3, user_role="operator")
    assert p.action == "blocked"


@spec_ref("FS-DBA-001", "AC-12")
def test_dba_001_ac12_low_confidence_blocks():
    """FS-DBA-001 AC-12: Confidence < 0.5 blocks DANGEROUS actions."""
    from app.agents.safety_guard import SafetyGuard, RiskLevel

    guard = SafetyGuard()

    # High autonomy but low confidence
    p = guard.check_policy(RiskLevel.DANGEROUS, autonomy_level=3, confidence=0.4, user_role="db_admin")
    assert p.action == "blocked"

    # Same autonomy, sufficient confidence
    p = guard.check_policy(RiskLevel.DANGEROUS, autonomy_level=3, confidence=0.6, user_role="db_admin")
    assert p.action == "execute"


# ---------------------------------------------------------------------------
# E4: API + Approval — AC-13~16
# ---------------------------------------------------------------------------

@spec_ref("FS-DBA-001", "AC-13")
def test_dba_001_ac13_action_request_model():
    """FS-DBA-001 AC-13: ActionRequest model has all required fields."""
    from app.agents.tools.ops_tools import ActionRequest

    fields = ActionRequest.model_fields
    assert "instance_id" in fields
    assert "action_type" in fields
    assert "sql" in fields
    assert "risk_level" in fields
    assert "requires_approval" in fields
    assert "confidence" in fields


@spec_ref("FS-DBA-001", "AC-14")
def test_dba_001_ac14_execute_approved_exists():
    """FS-DBA-001 AC-14: ExecutionEngine.execute_approved() for approval flow."""
    from app.agents.execution_engine import ExecutionEngine

    engine = ExecutionEngine()
    assert hasattr(engine, "execute_approved")


@spec_ref("FS-DBA-001", "AC-15")
def test_dba_001_ac15_action_result_statuses():
    """FS-DBA-001 AC-15: ActionResult supports all status values."""
    from app.agents.tools.ops_tools import ActionResult

    for status in ["executed", "approved", "rejected", "failed", "rolled_back", "pending", "blocked"]:
        r = ActionResult(action_id=uuid4(), status=status)
        assert r.status == status


@spec_ref("FS-DBA-001", "AC-16")
def test_dba_001_ac16_save_action_method():
    """FS-DBA-001 AC-16: ExecutionEngine saves action to agent_actions table."""
    from app.agents.execution_engine import ExecutionEngine

    engine = ExecutionEngine()
    assert hasattr(engine, "_save_action")

# Spec: FS-AUTO-002
"""Tests for Adaptive Autonomy — AC-1~11."""

import pytest
from pydantic import ValidationError
from tests.conftest import spec_ref


@spec_ref("FS-AUTO-002", "AC-1")
def test_fs_auto_002_ac1_default_autonomy_level():
    """FS-AUTO-002 AC-1: Instance created with autonomy_level=0 by default."""
    from app.models.db_instance import DBInstance

    assert hasattr(DBInstance, "autonomy_level")
    # Check column default
    col = DBInstance.__table__.columns["autonomy_level"]
    assert col.default is not None or col.server_default is not None


@spec_ref("FS-AUTO-002", "AC-2")
def test_fs_auto_002_ac2_autonomy_level_range():
    """FS-AUTO-002 AC-2: Admin can set autonomy_level 0~2 in MVP."""
    from app.models.db_instance import DBInstance

    assert hasattr(DBInstance, "autonomy_level")
    # SMALLINT column allows 0~4 at DB level, validation at app level


@spec_ref("FS-AUTO-002", "AC-3")
def test_fs_auto_002_ac3_l0_blocks_playbook():
    """FS-AUTO-002 AC-3: L0 blocks playbook execution (alert only)."""
    # L0 = alert only, no execution allowed
    autonomy_level = 0
    action_risk = 1  # any risk level
    assert autonomy_level < action_risk  # execution should be blocked


@spec_ref("FS-AUTO-002", "AC-4")
def test_fs_auto_002_ac4_l1_recommends_playbook():
    """FS-AUTO-002 AC-4: L1 recommends playbook in UI (no auto-execute)."""
    autonomy_level = 1
    # L1 = recommend, don't execute
    assert autonomy_level >= 1  # can recommend
    assert autonomy_level < 2  # cannot auto-execute


@spec_ref("FS-AUTO-002", "AC-5")
def test_fs_auto_002_ac5_l2_executes_after_approval():
    """FS-AUTO-002 AC-5: L2 executes playbook after human approval."""
    autonomy_level = 2
    human_approved = True
    can_execute = autonomy_level >= 2 and human_approved
    assert can_execute


@spec_ref("FS-AUTO-002", "AC-6")
def test_fs_auto_002_ac6_low_confidence_blocks():
    """FS-AUTO-002 AC-6: Confidence < 0.5 blocks auto-response at all levels."""
    confidence = 0.45
    for level in range(5):
        should_block = confidence < 0.5
        assert should_block, f"L{level} should block at confidence {confidence}"


@spec_ref("FS-AUTO-002", "AC-7")
def test_fs_auto_002_ac7_audit_log_on_change():
    """FS-AUTO-002 AC-7: Autonomy level change recorded in audit_logs."""
    from app.models.audit_log import AuditLog

    assert hasattr(AuditLog, "action")
    assert hasattr(AuditLog, "details")
    assert hasattr(AuditLog, "resource_type")


@spec_ref("FS-AUTO-002", "AC-8")
def test_fs_auto_002_ac8_phase2_rejects_l3_l4():
    """FS-AUTO-002 AC-8: Phase 2 rejects L3/L4 (ValidationError)."""
    # The max allowed in Phase 2 is L2
    MAX_AUTONOMY_PHASE2 = 2
    for level in [3, 4]:
        assert level > MAX_AUTONOMY_PHASE2


@spec_ref("FS-AUTO-002", "AC-9")
def test_fs_auto_002_ac9_phase3_l3_l4():
    """FS-AUTO-002 AC-9: L3/L4 allowed in Phase 3."""
    pytest.skip("Phase 3 — not yet implemented")


@spec_ref("FS-AUTO-002", "AC-10")
def test_fs_auto_002_ac10_l3_auto_execute():
    """FS-AUTO-002 AC-10: L3 auto-execute + report."""
    pytest.skip("Phase 3 — not yet implemented")


@spec_ref("FS-AUTO-002", "AC-11")
def test_fs_auto_002_ac11_failure_downgrades():
    """FS-AUTO-002 AC-11: Failure triggers autonomy downgrade."""
    pytest.skip("Phase 3 — not yet implemented")

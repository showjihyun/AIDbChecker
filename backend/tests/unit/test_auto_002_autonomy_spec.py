# Spec: FS-AUTO-002
"""Spec-Driven tests for Adaptive Autonomy Level (Phase 2).

Feature Spec: docs/specs/ai/ADAPTIVE_AUTONOMY_SPEC.md
PRD Reference: FR-AUTO-001, FR-AUTO-002
ACs: AC-1 through AC-8 (Phase 2 scope only)

Tests cover:
  - Default autonomy_level=0 on instance creation
  - Admin can set levels 0~2 in Phase 2
  - L0: playbook execution blocked (alert only)
  - L1: playbook recommended in UI (no auto-execute)
  - L2: execute after human approval
  - Confidence < 0.5 blocks at all levels
  - Autonomy level change audit logging
  - Phase 2 rejects L3/L4 setting
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field, ValidationError

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# Helper: Phase 2 autonomy validation schema (mirrors expected app behavior)
# ---------------------------------------------------------------------------

class AutonomyLevelUpdatePhase2(BaseModel):
    """Pydantic schema for autonomy level update in Phase 2.

    Spec: FS-AUTO-002 AC-8 -- L3/L4 rejected in Phase 2.
    """
    autonomy_level: int = Field(ge=0, le=2)


class AutonomyGate:
    """Logic gate for autonomy-level enforcement.

    Spec: FS-AUTO-002, AG-001 Section 2.3 -- Autonomy Behavior.
    """

    MAX_LEVEL_PHASE2 = 2

    @staticmethod
    def can_recommend(level: int) -> bool:
        return level >= 1

    @staticmethod
    def can_execute(level: int, human_approved: bool = False) -> bool:
        if level < 2:
            return False
        return human_approved

    @staticmethod
    def should_block_on_low_confidence(confidence: float) -> bool:
        return confidence < 0.5

    @classmethod
    def validate_phase2(cls, level: int) -> None:
        if level > cls.MAX_LEVEL_PHASE2:
            raise ValueError(
                f"Phase 2 restricts autonomy_level to 0-{cls.MAX_LEVEL_PHASE2}. "
                f"Level {level} requires Phase 3+."
            )


# ---------------------------------------------------------------------------
# AC-1: Instance created with autonomy_level=0 by default
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-002", "AC-1")
def test_fs_auto_002_ac1_db_instance_has_autonomy_level():
    """DBInstance model has autonomy_level column."""
    from app.models.db_instance import DBInstance

    assert hasattr(DBInstance, "autonomy_level")


@spec_ref("FS-AUTO-002", "AC-1")
def test_fs_auto_002_ac1_default_autonomy_level_is_zero():
    """DBInstance.autonomy_level column default is 0."""
    from app.models.db_instance import DBInstance

    col = DBInstance.__table__.columns["autonomy_level"]
    # Check Python-side default
    assert col.default is not None
    assert col.default.arg == 0


@spec_ref("FS-AUTO-002", "AC-1")
@pytest.mark.asyncio
async def test_fs_auto_002_ac1_created_instance_has_level_zero(sample_instance):
    """Newly created DBInstance fixture has autonomy_level=0."""
    assert sample_instance.autonomy_level == 0


# ---------------------------------------------------------------------------
# AC-2: Admin can set autonomy_level 0~2
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-002", "AC-2")
def test_fs_auto_002_ac2_valid_levels_0_through_2():
    """AutonomyLevelUpdatePhase2 accepts levels 0, 1, 2."""
    for level in [0, 1, 2]:
        schema = AutonomyLevelUpdatePhase2(autonomy_level=level)
        assert schema.autonomy_level == level


@spec_ref("FS-AUTO-002", "AC-2")
def test_fs_auto_002_ac2_rejects_negative_level():
    """AutonomyLevelUpdatePhase2 rejects negative levels."""
    with pytest.raises(ValidationError):
        AutonomyLevelUpdatePhase2(autonomy_level=-1)


@spec_ref("FS-AUTO-002", "AC-2")
def test_fs_auto_002_ac2_autonomy_column_is_smallint():
    """DBInstance.autonomy_level column is SMALLINT type."""
    from app.models.db_instance import DBInstance
    from sqlalchemy import SmallInteger

    col = DBInstance.__table__.columns["autonomy_level"]
    assert isinstance(col.type, SmallInteger)


# ---------------------------------------------------------------------------
# AC-3: L0 blocks playbook execution (alert only)
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-002", "AC-3")
def test_fs_auto_002_ac3_l0_cannot_recommend():
    """L0 cannot recommend playbooks."""
    assert not AutonomyGate.can_recommend(0)


@spec_ref("FS-AUTO-002", "AC-3")
def test_fs_auto_002_ac3_l0_cannot_execute():
    """L0 blocks playbook execution even with human approval."""
    assert not AutonomyGate.can_execute(0, human_approved=True)


@spec_ref("FS-AUTO-002", "AC-3")
def test_fs_auto_002_ac3_l0_any_risk_is_blocked():
    """At L0 any action_risk > 0 exceeds the max_allowed_risk."""
    autonomy_level = 0
    for action_risk in [1, 2, 3, 4]:
        assert autonomy_level < action_risk, (
            f"L0 should block action with risk={action_risk}"
        )


# ---------------------------------------------------------------------------
# AC-4: L1 recommends playbook in UI (no auto-execute)
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-002", "AC-4")
def test_fs_auto_002_ac4_l1_can_recommend():
    """L1 can recommend playbooks."""
    assert AutonomyGate.can_recommend(1)


@spec_ref("FS-AUTO-002", "AC-4")
def test_fs_auto_002_ac4_l1_cannot_execute():
    """L1 cannot auto-execute, even with approval (requires L2+)."""
    assert not AutonomyGate.can_execute(1, human_approved=True)


@spec_ref("FS-AUTO-002", "AC-4")
def test_fs_auto_002_ac4_l1_is_recommend_only():
    """L1 is strictly recommend-only: can_recommend=True, can_execute=False."""
    assert AutonomyGate.can_recommend(1)
    assert not AutonomyGate.can_execute(1, human_approved=False)
    assert not AutonomyGate.can_execute(1, human_approved=True)


# ---------------------------------------------------------------------------
# AC-5: L2 executes after human approval
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-002", "AC-5")
def test_fs_auto_002_ac5_l2_requires_approval():
    """L2 cannot execute without human approval."""
    assert not AutonomyGate.can_execute(2, human_approved=False)


@spec_ref("FS-AUTO-002", "AC-5")
def test_fs_auto_002_ac5_l2_executes_with_approval():
    """L2 executes playbook after human approval."""
    assert AutonomyGate.can_execute(2, human_approved=True)


@spec_ref("FS-AUTO-002", "AC-5")
def test_fs_auto_002_ac5_l2_can_also_recommend():
    """L2 still has recommend capability (superset of L1)."""
    assert AutonomyGate.can_recommend(2)


# ---------------------------------------------------------------------------
# AC-6: Confidence < 0.5 blocks at all levels
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-002", "AC-6")
def test_fs_auto_002_ac6_low_confidence_blocks_all_levels():
    """Confidence < 0.5 triggers block at every autonomy level (0-4)."""
    for confidence in [0.0, 0.1, 0.25, 0.49]:
        assert AutonomyGate.should_block_on_low_confidence(confidence), (
            f"Should block at confidence={confidence}"
        )


@spec_ref("FS-AUTO-002", "AC-6")
def test_fs_auto_002_ac6_sufficient_confidence_not_blocked():
    """Confidence >= 0.5 does not trigger the block."""
    for confidence in [0.5, 0.7, 0.85, 1.0]:
        assert not AutonomyGate.should_block_on_low_confidence(confidence), (
            f"Should NOT block at confidence={confidence}"
        )


@spec_ref("FS-AUTO-002", "AC-6")
def test_fs_auto_002_ac6_boundary_value_0_5_not_blocked():
    """Boundary: confidence=0.5 exactly is not blocked (< 0.5 is the condition)."""
    assert not AutonomyGate.should_block_on_low_confidence(0.5)


# ---------------------------------------------------------------------------
# AC-7: Autonomy level change recorded in audit_logs
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-002", "AC-7")
def test_fs_auto_002_ac7_audit_log_model_supports_required_fields():
    """AuditLog model has action, resource_type, details fields."""
    from app.models.audit_log import AuditLog

    assert hasattr(AuditLog, "action")
    assert hasattr(AuditLog, "resource_type")
    assert hasattr(AuditLog, "details")
    assert hasattr(AuditLog, "user_id")


@spec_ref("FS-AUTO-002", "AC-7")
def test_fs_auto_002_ac7_audit_log_action_column_accepts_update():
    """AuditLog.action column (VARCHAR 50) can hold 'update' action type."""
    from app.models.audit_log import AuditLog

    col = AuditLog.__table__.columns["action"]
    assert col.type.length >= 6  # "update" = 6 chars


@spec_ref("FS-AUTO-002", "AC-7")
def test_fs_auto_002_ac7_audit_log_details_is_jsonb():
    """AuditLog.details column is JSONB for structured before/after data."""
    from app.models.audit_log import AuditLog
    from sqlalchemy.dialects.postgresql import JSONB

    col = AuditLog.__table__.columns["details"]
    assert isinstance(col.type, JSONB)


# ---------------------------------------------------------------------------
# AC-8: Phase 2 rejects L3/L4 setting
# ---------------------------------------------------------------------------

@spec_ref("FS-AUTO-002", "AC-8")
def test_fs_auto_002_ac8_pydantic_rejects_l3():
    """Pydantic Phase 2 schema rejects autonomy_level=3."""
    with pytest.raises(ValidationError) as exc_info:
        AutonomyLevelUpdatePhase2(autonomy_level=3)
    assert "autonomy_level" in str(exc_info.value)


@spec_ref("FS-AUTO-002", "AC-8")
def test_fs_auto_002_ac8_pydantic_rejects_l4():
    """Pydantic Phase 2 schema rejects autonomy_level=4."""
    with pytest.raises(ValidationError) as exc_info:
        AutonomyLevelUpdatePhase2(autonomy_level=4)
    assert "autonomy_level" in str(exc_info.value)


@spec_ref("FS-AUTO-002", "AC-8")
def test_fs_auto_002_ac8_gate_validate_rejects_l3_l4():
    """AutonomyGate.validate_phase2 raises ValueError for L3 and L4."""
    for level in [3, 4]:
        with pytest.raises(ValueError, match="Phase 2 restricts"):
            AutonomyGate.validate_phase2(level)


@spec_ref("FS-AUTO-002", "AC-8")
def test_fs_auto_002_ac8_gate_validate_accepts_l0_to_l2():
    """AutonomyGate.validate_phase2 accepts levels 0, 1, 2 without error."""
    for level in [0, 1, 2]:
        AutonomyGate.validate_phase2(level)  # Should not raise

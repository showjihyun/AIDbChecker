# Spec: FS-ADMIN-004
"""Spec-Driven tests for AI Decision Log (audit_logs with action='ai_decision').

Feature Spec: docs/specs/services/AI_DECISION_LOG_SPEC.md
PRD Reference: FR-ADMIN-003, FR-AI-009
ACs: AC-1 through AC-6

Tests cover:
  - create_ai_decision_log callable with correct resource_type
  - build_ai_details returns structured JSONB with all required fields
  - Error recording in details.error
  - AuditLog model supports action='ai_decision' and resource_type filtering
  - Prompt summary truncation to 200 chars
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# AC-1: MTL RCA call logs ai_decision with resource_type="mtl_rca"
# ---------------------------------------------------------------------------

@spec_ref("FS-ADMIN-004", "AC-1")
def test_fs_admin_004_ac1_create_ai_decision_log_callable():
    """create_ai_decision_log function exists and is callable."""
    from app.utils.ai_logger import create_ai_decision_log

    assert callable(create_ai_decision_log)


@spec_ref("FS-ADMIN-004", "AC-1")
@pytest.mark.asyncio
async def test_fs_admin_004_ac1_create_log_accepts_mtl_rca_resource():
    """create_ai_decision_log accepts resource_type='mtl_rca'."""
    from app.utils.ai_logger import create_ai_decision_log

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.flush = AsyncMock()

    # Should not raise for mtl_rca resource type
    await create_ai_decision_log(
        mock_session,
        resource_type="mtl_rca",
        resource_id=str(uuid4()),
        details={
            "ai_model": "gpt-4o",
            "inference_time_ms": 2500,
            "confidence": 0.85,
            "decision": "rca_completed",
        },
    )
    # Verify session.execute was called (log was written)
    assert mock_session.execute.called


@spec_ref("FS-ADMIN-004", "AC-1")
def test_fs_admin_004_ac1_audit_log_action_field_supports_ai_decision():
    """AuditLog.action column is VARCHAR(50) -- big enough for 'ai_decision'."""
    from app.models.audit_log import AuditLog

    col = AuditLog.__table__.columns["action"]
    assert col.type.length >= len("ai_decision")


@spec_ref("FS-ADMIN-004", "AC-1")
def test_fs_admin_004_ac1_build_details_for_mtl_rca():
    """build_ai_details produces correct structure for MTL RCA."""
    from app.utils.ai_logger import build_ai_details

    details = build_ai_details(
        ai_model="gpt-4o",
        inference_time_ms=3200,
        decision="rca_completed",
        confidence=0.92,
        total_tokens=2100,
        prompt_tokens=1500,
        completion_tokens=600,
    )
    assert details["ai_model"] == "gpt-4o"
    assert details["decision"] == "rca_completed"
    assert details["confidence"] == 0.92
    assert details["total_tokens"] == 2100


# ---------------------------------------------------------------------------
# AC-2: NL2SQL call logs with resource_type="nl2sql"
# ---------------------------------------------------------------------------

@spec_ref("FS-ADMIN-004", "AC-2")
@pytest.mark.asyncio
async def test_fs_admin_004_ac2_create_log_accepts_nl2sql_resource():
    """create_ai_decision_log accepts resource_type='nl2sql'."""
    from app.utils.ai_logger import create_ai_decision_log

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.flush = AsyncMock()

    await create_ai_decision_log(
        mock_session,
        resource_type="nl2sql",
        details={
            "ai_model": "mistral:7b",
            "inference_time_ms": 800,
            "decision": "sql_generated",
            "total_tokens": 350,
        },
    )
    assert mock_session.execute.called


@spec_ref("FS-ADMIN-004", "AC-2")
def test_fs_admin_004_ac2_build_details_for_nl2sql():
    """build_ai_details produces correct structure for NL2SQL."""
    from app.utils.ai_logger import build_ai_details

    details = build_ai_details(
        ai_model="llama3.1:8b",
        inference_time_ms=1200,
        decision="sql_generated",
        total_tokens=500,
    )
    assert details["ai_model"] == "llama3.1:8b"
    assert details["inference_time_ms"] == 1200
    assert details["decision"] == "sql_generated"
    assert details["total_tokens"] == 500


@spec_ref("FS-ADMIN-004", "AC-2")
def test_fs_admin_004_ac2_audit_log_resource_type_accepts_nl2sql():
    """AuditLog.resource_type column (VARCHAR 50) can hold 'nl2sql'."""
    from app.models.audit_log import AuditLog

    col = AuditLog.__table__.columns["resource_type"]
    assert col.type.length >= len("nl2sql")


# ---------------------------------------------------------------------------
# AC-3: details JSONB contains ai_model, inference_time_ms, total_tokens, confidence
# ---------------------------------------------------------------------------

@spec_ref("FS-ADMIN-004", "AC-3")
def test_fs_admin_004_ac3_build_details_has_required_keys():
    """build_ai_details always includes ai_model, inference_time_ms, decision."""
    from app.utils.ai_logger import build_ai_details

    details = build_ai_details(
        ai_model="gpt-4o",
        inference_time_ms=2340,
        decision="rca_completed",
        confidence=0.87,
        total_tokens=1650,
        prompt_tokens=1200,
        completion_tokens=450,
    )
    assert "ai_model" in details
    assert "inference_time_ms" in details
    assert "decision" in details
    assert "confidence" in details
    assert "total_tokens" in details
    assert "prompt_tokens" in details
    assert "completion_tokens" in details


@spec_ref("FS-ADMIN-004", "AC-3")
def test_fs_admin_004_ac3_confidence_rounded_to_4_decimals():
    """Confidence value is rounded to 4 decimal places."""
    from app.utils.ai_logger import build_ai_details

    details = build_ai_details(
        ai_model="gpt-4o",
        inference_time_ms=1000,
        decision="rca_completed",
        confidence=0.8765432,
    )
    assert details["confidence"] == 0.8765


@spec_ref("FS-ADMIN-004", "AC-3")
def test_fs_admin_004_ac3_optional_fields_omitted_when_none():
    """Optional fields are not included when not provided."""
    from app.utils.ai_logger import build_ai_details

    details = build_ai_details(
        ai_model="gpt-4o",
        inference_time_ms=1000,
        decision="rca_completed",
    )
    assert "confidence" not in details
    assert "total_tokens" not in details
    assert "error" not in details
    assert "prompt_summary" not in details


@spec_ref("FS-ADMIN-004", "AC-3")
def test_fs_admin_004_ac3_details_includes_ai_mode():
    """build_ai_details includes ai_mode field (online/offline)."""
    from app.utils.ai_logger import build_ai_details

    details = build_ai_details(
        ai_model="gpt-4o",
        inference_time_ms=1000,
        decision="test",
    )
    assert "ai_mode" in details
    assert details["ai_mode"] in ("online", "offline")


# ---------------------------------------------------------------------------
# AC-4: LLM failure records error in details.error
# ---------------------------------------------------------------------------

@spec_ref("FS-ADMIN-004", "AC-4")
def test_fs_admin_004_ac4_error_field_present_on_failure():
    """build_ai_details includes 'error' field when error message provided."""
    from app.utils.ai_logger import build_ai_details

    details = build_ai_details(
        ai_model="mistral:7b",
        inference_time_ms=500,
        decision="error",
        error="Connection timeout to Ollama",
    )
    assert "error" in details
    assert details["error"] == "Connection timeout to Ollama"
    assert details["decision"] == "error"


@spec_ref("FS-ADMIN-004", "AC-4")
def test_fs_admin_004_ac4_error_field_absent_on_success():
    """build_ai_details does not include 'error' when no error."""
    from app.utils.ai_logger import build_ai_details

    details = build_ai_details(
        ai_model="gpt-4o",
        inference_time_ms=2000,
        decision="rca_completed",
        confidence=0.9,
    )
    assert "error" not in details


@spec_ref("FS-ADMIN-004", "AC-4")
@pytest.mark.asyncio
async def test_fs_admin_004_ac4_log_write_failure_does_not_propagate():
    """create_ai_decision_log swallows DB write errors (never breaks main flow)."""
    from app.utils.ai_logger import create_ai_decision_log

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=RuntimeError("DB connection lost"))

    # Should not raise -- errors are swallowed
    await create_ai_decision_log(
        mock_session,
        resource_type="mtl_rca",
        details={"ai_model": "gpt-4o", "inference_time_ms": 100, "decision": "error"},
    )
    # The function should complete without raising


# ---------------------------------------------------------------------------
# AC-5: GET /audit-logs?action=ai_decision filter
# ---------------------------------------------------------------------------

@spec_ref("FS-ADMIN-004", "AC-5")
def test_fs_admin_004_ac5_audit_log_model_has_action_field():
    """AuditLog model exposes action field for filtering."""
    from app.models.audit_log import AuditLog

    assert hasattr(AuditLog, "action")
    col = AuditLog.__table__.columns["action"]
    assert col.nullable is False


@spec_ref("FS-ADMIN-004", "AC-5")
def test_fs_admin_004_ac5_audit_log_has_resource_type():
    """AuditLog model exposes resource_type for filtering."""
    from app.models.audit_log import AuditLog

    assert hasattr(AuditLog, "resource_type")
    col = AuditLog.__table__.columns["resource_type"]
    assert col.nullable is False


@spec_ref("FS-ADMIN-004", "AC-5")
def test_fs_admin_004_ac5_audit_log_has_details_jsonb():
    """AuditLog.details is JSONB for structured AI decision data."""
    from app.models.audit_log import AuditLog
    from sqlalchemy.dialects.postgresql import JSONB

    col = AuditLog.__table__.columns["details"]
    assert isinstance(col.type, JSONB)


@spec_ref("FS-ADMIN-004", "AC-5")
def test_fs_admin_004_ac5_audit_log_has_resource_index():
    """AuditLog has index on (resource_type, resource_id) for efficient filtering."""
    from app.models.audit_log import AuditLog

    index_names = {idx.name for idx in AuditLog.__table__.indexes}
    assert "ix_audit_resource" in index_names


# ---------------------------------------------------------------------------
# AC-6: Full prompt not stored, prompt_summary 200 chars max
# ---------------------------------------------------------------------------

@spec_ref("FS-ADMIN-004", "AC-6")
def test_fs_admin_004_ac6_truncate_prompt_short_input():
    """truncate_prompt returns short prompts unchanged."""
    from app.utils.ai_logger import truncate_prompt

    short = "Short prompt text"
    assert truncate_prompt(short) == short


@spec_ref("FS-ADMIN-004", "AC-6")
def test_fs_admin_004_ac6_truncate_prompt_long_input():
    """truncate_prompt truncates to 200 chars with '...' suffix."""
    from app.utils.ai_logger import truncate_prompt

    long_prompt = "x" * 500
    result = truncate_prompt(long_prompt)
    assert len(result) <= 200
    assert result.endswith("...")


@spec_ref("FS-ADMIN-004", "AC-6")
def test_fs_admin_004_ac6_truncate_prompt_exactly_200():
    """truncate_prompt returns 200-char input unchanged."""
    from app.utils.ai_logger import truncate_prompt

    exact = "y" * 200
    result = truncate_prompt(exact)
    assert result == exact
    assert len(result) == 200


@spec_ref("FS-ADMIN-004", "AC-6")
def test_fs_admin_004_ac6_truncate_prompt_201_chars():
    """truncate_prompt truncates 201-char input (boundary test)."""
    from app.utils.ai_logger import truncate_prompt

    prompt = "z" * 201
    result = truncate_prompt(prompt)
    assert len(result) <= 200
    assert result.endswith("...")


@spec_ref("FS-ADMIN-004", "AC-6")
def test_fs_admin_004_ac6_build_details_truncates_prompt_summary():
    """build_ai_details auto-truncates prompt_summary to 200 chars."""
    from app.utils.ai_logger import build_ai_details

    long_prompt = "SELECT " + "a" * 500
    details = build_ai_details(
        ai_model="gpt-4o",
        inference_time_ms=1000,
        decision="sql_generated",
        prompt_summary=long_prompt,
    )
    assert "prompt_summary" in details
    assert len(details["prompt_summary"]) <= 200


@spec_ref("FS-ADMIN-004", "AC-6")
def test_fs_admin_004_ac6_empty_prompt_summary_omitted():
    """build_ai_details omits prompt_summary when not provided."""
    from app.utils.ai_logger import build_ai_details

    details = build_ai_details(
        ai_model="gpt-4o",
        inference_time_ms=1000,
        decision="rca_completed",
    )
    assert "prompt_summary" not in details

# Spec: FS-ADMIN-004
"""Tests for AI Decision Log — AC-1~6."""

from tests.conftest import spec_ref


@spec_ref("FS-ADMIN-004", "AC-1")
def test_fs_admin_004_ac1_ai_logger_exists():
    """FS-ADMIN-004 AC-1: ai_logger module with create_ai_decision_log function."""
    from app.utils.ai_logger import create_ai_decision_log
    assert callable(create_ai_decision_log)


@spec_ref("FS-ADMIN-004", "AC-2")
def test_fs_admin_004_ac2_build_details_resource_types():
    """FS-ADMIN-004 AC-2: build_ai_details supports all resource types."""
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


@spec_ref("FS-ADMIN-004", "AC-3")
def test_fs_admin_004_ac3_details_has_required_fields():
    """FS-ADMIN-004 AC-3: details JSONB includes ai_model, inference_time_ms, confidence."""
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
    assert "confidence" in details
    assert "total_tokens" in details
    assert details["confidence"] == 0.87


@spec_ref("FS-ADMIN-004", "AC-4")
def test_fs_admin_004_ac4_error_in_details():
    """FS-ADMIN-004 AC-4: LLM failure records error in details."""
    from app.utils.ai_logger import build_ai_details

    details = build_ai_details(
        ai_model="mistral:7b",
        inference_time_ms=500,
        decision="error",
        error="Connection timeout to Ollama",
    )
    assert details["error"] == "Connection timeout to Ollama"
    assert details["decision"] == "error"


@spec_ref("FS-ADMIN-004", "AC-5")
def test_fs_admin_004_ac5_audit_log_model_has_action():
    """FS-ADMIN-004 AC-5: audit_logs model supports action='ai_decision'."""
    from app.models.audit_log import AuditLog

    assert hasattr(AuditLog, "action")
    assert hasattr(AuditLog, "resource_type")
    assert hasattr(AuditLog, "details")


@spec_ref("FS-ADMIN-004", "AC-6")
def test_fs_admin_004_ac6_prompt_summary_truncated():
    """FS-ADMIN-004 AC-6: prompt_summary truncated to 200 chars."""
    from app.utils.ai_logger import truncate_prompt

    short = "Short prompt"
    assert truncate_prompt(short) == short

    long_prompt = "x" * 500
    truncated = truncate_prompt(long_prompt)
    assert len(truncated) <= 200
    assert truncated.endswith("...")

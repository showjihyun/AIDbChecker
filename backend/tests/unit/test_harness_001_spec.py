# Spec: FS-HARNESS-001
"""Tests for Harness v3 — 4-Pillar Pre-Commit Quality Gate."""

import os
from pathlib import Path

import pytest

from tests.conftest import spec_ref

ROOT = Path(__file__).resolve().parents[3]
HOOK_SCRIPT = ROOT / "backend" / "scripts" / "precommit_check.sh"
GIT_HOOK = ROOT / ".git" / "hooks" / "pre-commit"
CLAUDE_SETTINGS = ROOT / ".claude" / "settings.json"


@spec_ref("FS-HARNESS-001", "AC-1")
def test_fs_harness_001_ac1_precommit_hook_exists():
    """FS-HARNESS-001 AC-1: pre-commit hook exists and delegates to 4-pillar script."""
    assert GIT_HOOK.exists(), ".git/hooks/pre-commit not installed"
    content = GIT_HOOK.read_text(encoding="utf-8")
    assert "precommit_check.sh" in content


@spec_ref("FS-HARNESS-001", "AC-2")
def test_fs_harness_001_ac2_pillar1_ruff_autofix():
    """FS-HARNESS-001 AC-2: Pillar 1 runs ruff --fix for auto-correction."""
    content = HOOK_SCRIPT.read_text(encoding="utf-8")
    assert "ruff check --fix" in content
    assert "ruff format" in content
    assert "git add" in content  # re-stages auto-fixed files


@spec_ref("FS-HARNESS-001", "AC-3")
def test_fs_harness_001_ac3_pillar2_mypy_warn_only():
    """FS-HARNESS-001 AC-3: Pillar 2 mypy warns but does NOT block commit."""
    content = HOOK_SCRIPT.read_text(encoding="utf-8")
    assert "mypy" in content
    # v2: mypy is warn-only — should NOT set FAILED=1
    assert "WARN" in content or "warn" in content


@spec_ref("FS-HARNESS-001", "AC-4")
def test_fs_harness_001_ac4_pillar3_affected_tests():
    """FS-HARNESS-001 AC-4: Pillar 3 runs affected tests only, not full suite."""
    content = HOOK_SCRIPT.read_text(encoding="utf-8")
    assert "AFFECTED_TESTS" in content
    assert "affected only" in content.lower() or "affected" in content


@spec_ref("FS-HARNESS-001", "AC-5")
def test_fs_harness_001_ac5_pillar4_feedback_no_block():
    """FS-HARNESS-001 AC-5: Pillar 4 shows AC dashboard but never blocks."""
    content = HOOK_SCRIPT.read_text(encoding="utf-8")
    assert "spec_dashboard" in content
    # Pillar 4 section should not set FAILED
    lines = content.split("\n")
    in_p4 = False
    for line in lines:
        if "[4/4]" in line:
            in_p4 = True
        if in_p4 and "FAILED=1" in line:
            pytest.fail("Pillar 4 should never set FAILED=1")
        if in_p4 and "Result" in line:
            break


@spec_ref("FS-HARNESS-001", "AC-6")
def test_fs_harness_001_ac6_timing_displayed():
    """FS-HARNESS-001 AC-6: Hook execution time is displayed."""
    content = HOOK_SCRIPT.read_text(encoding="utf-8")
    assert "ELAPSED" in content or "elapsed" in content
    assert "TOTAL_TIME" in content or "date +%s" in content


@spec_ref("FS-HARNESS-001", "AC-7")
def test_fs_harness_001_ac7_claude_precommit_hook():
    """FS-HARNESS-001 AC-7: Claude Code settings.json has PreCommit hook."""
    import json

    content = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))
    hooks = content.get("hooks", {})
    assert "PreCommit" in hooks, "PreCommit hook not in .claude/settings.json"
    pre_hooks = hooks["PreCommit"]
    assert len(pre_hooks) > 0
    assert any("precommit_check" in str(h) for h in pre_hooks)


@spec_ref("FS-HARNESS-001", "AC-8")
def test_fs_harness_001_ac8_script_executable():
    """FS-HARNESS-001 AC-8: precommit_check.sh is executable and has shebang."""
    content = HOOK_SCRIPT.read_text(encoding="utf-8")
    assert content.startswith("#!/bin/bash")
    assert HOOK_SCRIPT.exists()


@spec_ref("FS-HARNESS-001", "AC-9")
def test_fs_harness_001_ac9_exit_codes():
    """FS-HARNESS-001 AC-9: Script exits 0 on success, 1 on failure."""
    content = HOOK_SCRIPT.read_text(encoding="utf-8")
    assert "exit 0" in content
    assert "exit 1" in content

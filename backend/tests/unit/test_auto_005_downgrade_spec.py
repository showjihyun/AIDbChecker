# Spec: FR-AUTO-005, FS-AUTO-002 AC-11
"""Spec-Driven tests for Dynamic Autonomy Downgrade.

Feature Spec: docs/specs/ai/ADAPTIVE_AUTONOMY_SPEC.md §5.2
AC Coverage:
  AC-11a: 단일 실패 → level -= 1
  AC-11b: 연속 3회 실패 → L0 강제
  AC-11c: 성공 시 카운터 리셋
"""

from uuid import uuid4

import pytest

from tests.conftest import spec_ref

from app.services.autonomy_manager import (
    clear,
    get_failure_count,
    record_failure,
    record_success,
)


@pytest.fixture(autouse=True)
def _reset():
    clear()
    yield
    clear()


@spec_ref("FS-AUTO-002", "AC-11")
def test_fs_auto_002_ac11_single_failure_downgrades_by_1():
    """AC-11: 단일 실패 → autonomy_level -= 1."""
    iid = uuid4()
    new_level = record_failure(iid, current_level=3)
    assert new_level == 2
    assert get_failure_count(iid) == 1


@spec_ref("FS-AUTO-002", "AC-11")
def test_fs_auto_002_ac11_minimum_level_is_0():
    """AC-11: level 0 아래로 내려가지 않음."""
    iid = uuid4()
    new_level = record_failure(iid, current_level=0)
    assert new_level == 0


@spec_ref("FS-AUTO-002", "AC-11")
def test_fs_auto_002_ac11_three_consecutive_failures_force_l0():
    """AC-11: 연속 3회 실패 → L0 강제."""
    iid = uuid4()
    record_failure(iid, current_level=4)  # → 3
    record_failure(iid, current_level=3)  # → 2
    new_level = record_failure(iid, current_level=2)  # → 0 (forced)
    assert new_level == 0
    assert get_failure_count(iid) == 3


@spec_ref("FS-AUTO-002", "AC-11")
def test_fs_auto_002_ac11_success_resets_counter():
    """AC-11: 성공 시 실패 카운터 리셋."""
    iid = uuid4()
    record_failure(iid, current_level=3)
    record_failure(iid, current_level=2)
    assert get_failure_count(iid) == 2

    record_success(iid)
    assert get_failure_count(iid) == 0


@spec_ref("FS-AUTO-002", "AC-11")
def test_fs_auto_002_ac11_after_reset_failure_restarts_count():
    """AC-11: 리셋 후 새 실패는 1부터 다시 시작."""
    iid = uuid4()
    record_failure(iid, current_level=3)
    record_failure(iid, current_level=2)
    record_success(iid)  # reset

    new_level = record_failure(iid, current_level=3)
    assert new_level == 2
    assert get_failure_count(iid) == 1


@spec_ref("FS-AUTO-002", "AC-11")
def test_fs_auto_002_ac11_independent_per_instance():
    """AC-11: 인스턴스별 독립 카운팅."""
    iid1 = uuid4()
    iid2 = uuid4()

    record_failure(iid1, current_level=3)
    record_failure(iid1, current_level=2)

    assert get_failure_count(iid1) == 2
    assert get_failure_count(iid2) == 0

# Spec: FS-AUTO-004
"""Spec-Driven tests for Task Queue Service.

Feature Spec: docs/specs/services/TASK_QUEUE_SPEC.md
Test Strategy: docs/specs/tests/TEST_STRATEGY.md

AC Coverage:
  AC-1: POST /tasks → status pending_approval → test_ac1_*
  AC-2: Autonomy L1 → pending_approval → test_ac2_*
  AC-3: 승인 후 실행 → completed/failed → test_ac3_*
  AC-4: 동일 인스턴스 동시 Task 거부 → test_ac4_*
  AC-5: 승인 대기 30분 초과 → cancelled → test_ac5_*
  AC-6: GET /tasks status 필터링 → test_ac6_*
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from tests.conftest import spec_ref

from app.schemas.task_queue import TaskStatus, TaskTrigger
from app.services.task_queue import (
    approve_task,
    cancel_task,
    clear_store,
    create_task,
    expire_stale_tasks,
    get_task,
    list_tasks,
    reject_task,
)


@pytest.fixture(autouse=True)
def _reset_store():
    """Clear in-memory task store before each test."""
    clear_store()
    yield
    clear_store()


# ---------------------------------------------------------------------------
# AC-1: POST /tasks → status pending_approval
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-004", "AC-1")
def test_fs_auto_004_ac1_create_l1_pending():
    """FS-AUTO-004 AC-1: L1 → pending_approval."""
    task, err = create_task(
        playbook_name="lock-remediation",
        instance_id=uuid4(),
        autonomy_level=1,
    )
    assert err is None
    assert task.status == TaskStatus.PENDING_APPROVAL


@spec_ref("FS-AUTO-004", "AC-1")
def test_fs_auto_004_ac1_create_l2_pending():
    """FS-AUTO-004 AC-1: L2도 pending_approval."""
    task, err = create_task(
        playbook_name="vacuum-maintenance",
        instance_id=uuid4(),
        autonomy_level=2,
    )
    assert err is None
    assert task.status == TaskStatus.PENDING_APPROVAL


@spec_ref("FS-AUTO-004", "AC-1")
def test_fs_auto_004_ac1_l0_rejected():
    """FS-AUTO-004 AC-1: L0 → rejected."""
    task, err = create_task(
        playbook_name="lock-remediation",
        instance_id=uuid4(),
        autonomy_level=0,
    )
    assert err is None
    assert task.status == TaskStatus.REJECTED


@spec_ref("FS-AUTO-004", "AC-1")
def test_fs_auto_004_ac1_has_required_fields():
    """FS-AUTO-004 AC-1: Task에 필수 필드 존재."""
    iid = uuid4()
    task, _ = create_task(
        playbook_name="connection-pool",
        instance_id=iid,
        trigger=TaskTrigger.AUTO,
        autonomy_level=1,
        confidence_score=0.9,
    )
    assert task.id is not None
    assert task.playbook_name == "connection-pool"
    assert task.instance_id == iid
    assert task.trigger == TaskTrigger.AUTO
    assert task.confidence_score == 0.9
    assert task.created_at is not None


@spec_ref("FS-AUTO-004", "AC-1")
def test_fs_auto_004_ac1_endpoint_registered():
    """FS-AUTO-004 AC-1: POST /tasks 엔드포인트 등록됨."""
    from app.main import app as fastapi_app

    routes = [r.path for r in fastapi_app.routes]
    assert "/api/v1/tasks" in routes


# ---------------------------------------------------------------------------
# AC-2: Autonomy L1 → pending_approval
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-004", "AC-2")
def test_fs_auto_004_ac2_l1_pending():
    """FS-AUTO-004 AC-2: L1 → pending_approval."""
    task, _ = create_task(
        playbook_name="query-timeout",
        instance_id=uuid4(),
        autonomy_level=1,
    )
    assert task.status == TaskStatus.PENDING_APPROVAL


@spec_ref("FS-AUTO-004", "AC-2")
def test_fs_auto_004_ac2_stored_in_memory():
    """FS-AUTO-004 AC-2: Task가 store에 저장됨."""
    task, _ = create_task(
        playbook_name="vacuum-maintenance",
        instance_id=uuid4(),
        autonomy_level=1,
    )
    stored = get_task(task.id)
    assert stored is not None
    assert stored.id == task.id


# ---------------------------------------------------------------------------
# AC-3: 승인 후 실행 → completed/failed
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-004", "AC-3")
def test_fs_auto_004_ac3_approve_completes():
    """FS-AUTO-004 AC-3: 승인 → completed."""
    task, _ = create_task(
        playbook_name="lock-remediation",
        instance_id=uuid4(),
        autonomy_level=2,
    )
    approved, err = approve_task(task.id)
    assert err is None
    assert approved.status == TaskStatus.COMPLETED
    assert approved.started_at is not None
    assert approved.completed_at is not None


@spec_ref("FS-AUTO-004", "AC-3")
def test_fs_auto_004_ac3_approve_has_log():
    """FS-AUTO-004 AC-3: 승인 후 execution_log 존재."""
    task, _ = create_task(
        playbook_name="vacuum-maintenance",
        instance_id=uuid4(),
        autonomy_level=1,
    )
    approved, _ = approve_task(task.id)
    assert len(approved.execution_log) >= 1


@spec_ref("FS-AUTO-004", "AC-3")
def test_fs_auto_004_ac3_reject():
    """FS-AUTO-004 AC-3: 거부 → rejected."""
    task, _ = create_task(
        playbook_name="index-optimization",
        instance_id=uuid4(),
        autonomy_level=1,
    )
    rejected, err = reject_task(task.id, "Too risky")
    assert err is None
    assert rejected.status == TaskStatus.REJECTED


@spec_ref("FS-AUTO-004", "AC-3")
def test_fs_auto_004_ac3_approve_completed_fails():
    """FS-AUTO-004 AC-3: 완료된 Task 재승인 → 에러."""
    task, _ = create_task(
        playbook_name="lock-remediation",
        instance_id=uuid4(),
        autonomy_level=2,
    )
    approve_task(task.id)
    _, err = approve_task(task.id)
    assert err is not None
    assert "not pending_approval" in err


@spec_ref("FS-AUTO-004", "AC-3")
def test_fs_auto_004_ac3_approve_nonexistent():
    """FS-AUTO-004 AC-3: 존재하지 않는 Task → 에러."""
    _, err = approve_task(uuid4())
    assert err == "Task not found"


# ---------------------------------------------------------------------------
# AC-4: 동일 인스턴스 동시 Task 거부
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-004", "AC-4")
def test_fs_auto_004_ac4_same_instance_conflict():
    """FS-AUTO-004 AC-4: 같은 인스턴스 2번째 Task → error."""
    iid = uuid4()
    _, err1 = create_task(playbook_name="lock-remediation", instance_id=iid, autonomy_level=1)
    assert err1 is None

    task2, err2 = create_task(playbook_name="vacuum-maintenance", instance_id=iid, autonomy_level=1)
    assert task2 is None
    assert "already has an active task" in err2


@spec_ref("FS-AUTO-004", "AC-4")
def test_fs_auto_004_ac4_different_instance_ok():
    """FS-AUTO-004 AC-4: 다른 인스턴스 → 동시 생성 가능."""
    _, err1 = create_task(playbook_name="lock-remediation", instance_id=uuid4(), autonomy_level=1)
    _, err2 = create_task(playbook_name="vacuum-maintenance", instance_id=uuid4(), autonomy_level=1)
    assert err1 is None
    assert err2 is None


@spec_ref("FS-AUTO-004", "AC-4")
def test_fs_auto_004_ac4_completed_allows_new():
    """FS-AUTO-004 AC-4: 완료 후 같은 인스턴스 새 Task 가능."""
    iid = uuid4()
    task1, _ = create_task(playbook_name="lock-remediation", instance_id=iid, autonomy_level=1)
    approve_task(task1.id)

    task2, err = create_task(playbook_name="vacuum-maintenance", instance_id=iid, autonomy_level=1)
    assert err is None
    assert task2 is not None


@spec_ref("FS-AUTO-004", "AC-4")
def test_fs_auto_004_ac4_global_limit():
    """FS-AUTO-004 AC-4: 전역 3개 초과 시 거부."""
    for _ in range(3):
        _, err = create_task(playbook_name="vacuum-maintenance", instance_id=uuid4(), autonomy_level=1)
        assert err is None

    _, err = create_task(playbook_name="lock-remediation", instance_id=uuid4(), autonomy_level=1)
    assert "Global concurrent" in err


# ---------------------------------------------------------------------------
# AC-5: 승인 대기 30분 초과 → cancelled
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-004", "AC-5")
def test_fs_auto_004_ac5_expire_31min():
    """FS-AUTO-004 AC-5: 31분 경과 → cancelled."""
    task, _ = create_task(playbook_name="lock-remediation", instance_id=uuid4(), autonomy_level=1)
    task.created_at = datetime.now(UTC) - timedelta(minutes=31)

    expired = expire_stale_tasks()
    assert expired == 1
    assert task.status == TaskStatus.CANCELLED


@spec_ref("FS-AUTO-004", "AC-5")
def test_fs_auto_004_ac5_not_expired_29min():
    """FS-AUTO-004 AC-5: 29분 → 만료 안 됨."""
    task, _ = create_task(playbook_name="lock-remediation", instance_id=uuid4(), autonomy_level=1)
    task.created_at = datetime.now(UTC) - timedelta(minutes=29)

    expired = expire_stale_tasks()
    assert expired == 0
    assert task.status == TaskStatus.PENDING_APPROVAL


@spec_ref("FS-AUTO-004", "AC-5")
def test_fs_auto_004_ac5_manual_cancel():
    """FS-AUTO-004 AC-5: 수동 cancel."""
    task, _ = create_task(playbook_name="vacuum-maintenance", instance_id=uuid4(), autonomy_level=1)
    cancelled, err = cancel_task(task.id)
    assert err is None
    assert cancelled.status == TaskStatus.CANCELLED


@spec_ref("FS-AUTO-004", "AC-5")
def test_fs_auto_004_ac5_cancel_completed_fails():
    """FS-AUTO-004 AC-5: 완료 Task cancel 불가."""
    task, _ = create_task(playbook_name="lock-remediation", instance_id=uuid4(), autonomy_level=2)
    approve_task(task.id)
    _, err = cancel_task(task.id)
    assert "cannot cancel" in err


# ---------------------------------------------------------------------------
# AC-6: GET /tasks status 필터링
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-004", "AC-6")
def test_fs_auto_004_ac6_list_all():
    """FS-AUTO-004 AC-6: 전체 목록."""
    for _ in range(3):
        create_task(playbook_name="vacuum-maintenance", instance_id=uuid4(), autonomy_level=1)
    assert len(list_tasks()) == 3


@spec_ref("FS-AUTO-004", "AC-6")
def test_fs_auto_004_ac6_filter_by_status():
    """FS-AUTO-004 AC-6: status 필터."""
    create_task(playbook_name="lock-remediation", instance_id=uuid4(), autonomy_level=1)
    create_task(playbook_name="vacuum-maintenance", instance_id=uuid4(), autonomy_level=0)

    assert len(list_tasks(status_filter=TaskStatus.PENDING_APPROVAL)) == 1
    assert len(list_tasks(status_filter=TaskStatus.REJECTED)) == 1


@spec_ref("FS-AUTO-004", "AC-6")
def test_fs_auto_004_ac6_filter_by_instance():
    """FS-AUTO-004 AC-6: instance 필터."""
    target = uuid4()
    create_task(playbook_name="lock-remediation", instance_id=target, autonomy_level=1)
    create_task(playbook_name="vacuum-maintenance", instance_id=uuid4(), autonomy_level=1)

    filtered = list_tasks(instance_id=target)
    assert len(filtered) == 1
    assert filtered[0].instance_id == target


@spec_ref("FS-AUTO-004", "AC-6")
def test_fs_auto_004_ac6_endpoints_registered():
    """FS-AUTO-004 AC-6: GET /tasks, /tasks/{id} 등록됨."""
    from app.main import app as fastapi_app

    routes = [r.path for r in fastapi_app.routes]
    assert "/api/v1/tasks" in routes
    assert "/api/v1/tasks/{task_id}" in routes
    assert "/api/v1/tasks/{task_id}/approve" in routes
    assert "/api/v1/tasks/{task_id}/reject" in routes
    assert "/api/v1/tasks/{task_id}/cancel" in routes

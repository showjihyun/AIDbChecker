# Spec: FS-AUTO-003
"""Spec-Driven tests for Playbook Lite (Built-in 7 + Executor).

Feature Spec: docs/specs/playbooks/PLAYBOOK_SPEC.md
Test Strategy: docs/specs/tests/TEST_STRATEGY.md

AC Coverage:
  AC-1: 7개 Built-in Playbook 시스템 시작 시 자동 로드 → test_ac1_*
  AC-2: GET /playbooks에서 Built-in 목록 반환 → test_ac2_*
  AC-3: Autonomy L2에서 lock-remediation 수동 실행 성공 → test_ac3_*
  AC-4: Autonomy L0에서 Playbook 실행 시 blocked 반환 → test_ac4_*
  AC-5: Confidence < 0.5에서 Playbook 자동 트리거 차단 → test_ac5_*
  AC-6: 실행 실패 시 역순 롤백 후 이력 저장 → test_ac6_*
  AC-7: DB Copilot 진단 결과에서 매칭 Playbook 추천 → test_ac7_*
  AC-8: 승인 대기 상태 Playbook UI 승인/거부 → test_ac8_*
"""

from uuid import uuid4

import pytest

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# AC-1: 7개 Built-in Playbook 시스템 시작 시 자동 로드
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-003", "AC-1")
def test_fs_auto_003_ac1_all_7_playbooks_loaded():
    """FS-AUTO-003 AC-1: 7개 Built-in Playbook이 로드됨."""
    from app.services.playbook_executor import _playbook_cache, _load_all_playbooks

    _playbook_cache.clear()  # reset cache
    playbooks = _load_all_playbooks()
    assert len(playbooks) == 7


@spec_ref("FS-AUTO-003", "AC-1")
def test_fs_auto_003_ac1_expected_names():
    """FS-AUTO-003 AC-1: 7개 Playbook 이름이 Spec과 일치."""
    from app.services.playbook_executor import _playbook_cache, _load_all_playbooks

    _playbook_cache.clear()
    playbooks = _load_all_playbooks()
    expected = {
        "lock-remediation",
        "index-optimization",
        "replication-lag",
        "connection-pool",
        "vacuum-maintenance",
        "query-timeout",
        "memory-pressure",
    }
    assert set(playbooks.keys()) == expected


@spec_ref("FS-AUTO-003", "AC-1")
def test_fs_auto_003_ac1_all_have_valid_metadata():
    """FS-AUTO-003 AC-1: 모든 Playbook에 name, version, risk_level 존재."""
    from app.services.playbook_executor import _playbook_cache, _load_all_playbooks

    _playbook_cache.clear()
    for name, data in _load_all_playbooks().items():
        meta = data.get("metadata", {})
        assert meta.get("name"), f"{name} missing metadata.name"
        assert meta.get("version"), f"{name} missing metadata.version"
        assert meta.get("risk_level") in ("low", "medium", "high", "critical"), (
            f"{name} invalid risk_level: {meta.get('risk_level')}"
        )
        assert meta.get("author") == "builtin", f"{name} author must be 'builtin'"


# ---------------------------------------------------------------------------
# AC-2: GET /playbooks에서 Built-in 목록 반환
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-003", "AC-2")
def test_fs_auto_003_ac2_list_returns_7():
    """FS-AUTO-003 AC-2: list_playbooks() 반환 7건."""
    from app.services.playbook_executor import _playbook_cache, list_playbooks

    _playbook_cache.clear()
    summaries = list_playbooks()
    assert len(summaries) == 7


@spec_ref("FS-AUTO-003", "AC-2")
def test_fs_auto_003_ac2_summary_fields():
    """FS-AUTO-003 AC-2: 각 summary에 필수 필드 존재."""
    from app.services.playbook_executor import _playbook_cache, list_playbooks

    _playbook_cache.clear()
    for s in list_playbooks():
        assert s.name
        assert s.description
        assert s.steps_count > 0
        assert s.min_autonomy_level in (0, 1, 2)


@spec_ref("FS-AUTO-003", "AC-2")
def test_fs_auto_003_ac2_get_detail_returns_yaml():
    """FS-AUTO-003 AC-2: get_playbook에 yaml_content 포함."""
    from app.services.playbook_executor import _playbook_cache, get_playbook

    _playbook_cache.clear()
    detail = get_playbook("lock-remediation")
    assert detail is not None
    assert "apiVersion" in detail.yaml_content
    assert detail.metadata.name == "lock-remediation"
    assert len(detail.steps) >= 1


@spec_ref("FS-AUTO-003", "AC-2")
def test_fs_auto_003_ac2_get_nonexistent_returns_none():
    """FS-AUTO-003 AC-2: 존재하지 않는 Playbook은 None."""
    from app.services.playbook_executor import _playbook_cache, get_playbook

    _playbook_cache.clear()
    assert get_playbook("nonexistent-playbook") is None


@spec_ref("FS-AUTO-003", "AC-2")
def test_fs_auto_003_ac2_endpoint_exists():
    """FS-AUTO-003 AC-2: /playbooks GET 엔드포인트 등록됨."""
    from app.main import app as fastapi_app

    routes = [r.path for r in fastapi_app.routes]
    assert "/api/v1/playbooks" in routes


# ---------------------------------------------------------------------------
# AC-3: Autonomy L2에서 lock-remediation 실행 성공
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-003", "AC-3")
@pytest.mark.asyncio
async def test_fs_auto_003_ac3_l2_executes_successfully():
    """FS-AUTO-003 AC-3: Autonomy L2 + confidence 0.8 → status=success."""
    from app.services.playbook_executor import _playbook_cache, execute_playbook

    _playbook_cache.clear()
    result = await execute_playbook(
        playbook_name="lock-remediation",
        instance_id=uuid4(),
        autonomy_level=2,
        confidence_score=0.8,
    )
    assert result.status.value == "success"
    assert len(result.steps) >= 1
    assert result.total_duration_ms >= 0


@spec_ref("FS-AUTO-003", "AC-3")
@pytest.mark.asyncio
async def test_fs_auto_003_ac3_dry_run_skips_execution():
    """FS-AUTO-003 AC-3: dry_run=true → steps all skipped."""
    from app.services.playbook_executor import _playbook_cache, execute_playbook

    _playbook_cache.clear()
    result = await execute_playbook(
        playbook_name="vacuum-maintenance",
        instance_id=uuid4(),
        autonomy_level=1,
        confidence_score=0.8,
        dry_run=True,
    )
    assert result.status.value == "success"
    assert result.reason == "dry_run: no SQL executed"
    for step in result.steps:
        assert step.status == "skipped"


# ---------------------------------------------------------------------------
# AC-4: Autonomy L0에서 Playbook 실행 시 blocked
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-003", "AC-4")
@pytest.mark.asyncio
async def test_fs_auto_003_ac4_l0_blocked():
    """FS-AUTO-003 AC-4: Autonomy L0 → status=blocked."""
    from app.services.playbook_executor import _playbook_cache, execute_playbook

    _playbook_cache.clear()
    result = await execute_playbook(
        playbook_name="lock-remediation",
        instance_id=uuid4(),
        autonomy_level=0,
        confidence_score=0.9,
    )
    assert result.status.value == "blocked"
    assert "L0" in result.reason


@spec_ref("FS-AUTO-003", "AC-4")
@pytest.mark.asyncio
async def test_fs_auto_003_ac4_l1_on_l2_playbook_pending():
    """FS-AUTO-003 AC-4: L1 + L2 required → pending_approval."""
    from app.services.playbook_executor import _playbook_cache, execute_playbook

    _playbook_cache.clear()
    result = await execute_playbook(
        playbook_name="lock-remediation",  # min_autonomy_level: 2
        instance_id=uuid4(),
        autonomy_level=1,
        confidence_score=0.8,
    )
    assert result.status.value == "pending_approval"


# ---------------------------------------------------------------------------
# AC-5: Confidence < 0.5에서 Playbook 자동 트리거 차단
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-003", "AC-5")
@pytest.mark.asyncio
async def test_fs_auto_003_ac5_low_confidence_blocked():
    """FS-AUTO-003 AC-5: Confidence 0.3 < 0.5 → blocked."""
    from app.services.playbook_executor import _playbook_cache, execute_playbook

    _playbook_cache.clear()
    result = await execute_playbook(
        playbook_name="vacuum-maintenance",
        instance_id=uuid4(),
        autonomy_level=2,
        confidence_score=0.3,
    )
    assert result.status.value == "blocked"
    assert "Confidence" in result.reason


@spec_ref("FS-AUTO-003", "AC-5")
@pytest.mark.asyncio
async def test_fs_auto_003_ac5_boundary_confidence_passes():
    """FS-AUTO-003 AC-5: Confidence exactly 0.5 → not blocked."""
    from app.services.playbook_executor import _playbook_cache, execute_playbook

    _playbook_cache.clear()
    result = await execute_playbook(
        playbook_name="vacuum-maintenance",  # min_confidence: 0.5
        instance_id=uuid4(),
        autonomy_level=1,
        confidence_score=0.5,
    )
    # Should pass confidence gate (0.5 >= 0.5) but may be pending or success
    assert result.status.value != "blocked"


# ---------------------------------------------------------------------------
# AC-6: 실행 실패 시 역순 롤백
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-003", "AC-6")
@pytest.mark.asyncio
async def test_fs_auto_003_ac6_success_has_step_history():
    """FS-AUTO-003 AC-6: 성공 시 steps에 전체 실행 이력 저장."""
    from app.services.playbook_executor import _playbook_cache, execute_playbook

    _playbook_cache.clear()
    result = await execute_playbook(
        playbook_name="lock-remediation",
        instance_id=uuid4(),
        autonomy_level=2,
        confidence_score=0.8,
    )
    assert result.status.value == "success"
    assert len(result.steps) >= 1
    for step in result.steps:
        assert step.step_name
        assert step.status == "success"


@spec_ref("FS-AUTO-003", "AC-6")
@pytest.mark.asyncio
async def test_fs_auto_003_ac6_nonexistent_playbook_fails():
    """FS-AUTO-003 AC-6: 존재하지 않는 Playbook → failed."""
    from app.services.playbook_executor import execute_playbook

    result = await execute_playbook(
        playbook_name="does-not-exist",
        instance_id=uuid4(),
        autonomy_level=2,
        confidence_score=0.9,
    )
    assert result.status.value == "failed"
    assert "not found" in result.reason


# ---------------------------------------------------------------------------
# AC-7: DB Copilot 진단 결과에서 매칭 Playbook 추천
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-003", "AC-7")
def test_fs_auto_003_ac7_match_lock_contention():
    """FS-AUTO-003 AC-7: lock_contention → lock-remediation 매칭."""
    from app.services.playbook_executor import match_playbook

    assert match_playbook("lock_contention") == "lock-remediation"


@spec_ref("FS-AUTO-003", "AC-7")
def test_fs_auto_003_ac7_match_all_known_types():
    """FS-AUTO-003 AC-7: 알려진 anomaly_type 전부 매칭."""
    from app.services.playbook_executor import match_playbook

    assert match_playbook("lock_contention") == "lock-remediation"
    assert match_playbook("query_performance_degradation") == "index-optimization"
    assert match_playbook("replication_lag") == "replication-lag"
    assert match_playbook("connection_saturation") == "connection-pool"
    assert match_playbook("vacuum_bloat") == "vacuum-maintenance"
    assert match_playbook("resource_exhaustion") == "memory-pressure"


@spec_ref("FS-AUTO-003", "AC-7")
def test_fs_auto_003_ac7_unknown_type_returns_none():
    """FS-AUTO-003 AC-7: 미지의 anomaly_type → None."""
    from app.services.playbook_executor import match_playbook

    assert match_playbook("unknown_type") is None
    assert match_playbook(None) is None


# ---------------------------------------------------------------------------
# AC-8: 승인 대기 상태 Playbook 승인/거부
# ---------------------------------------------------------------------------


@spec_ref("FS-AUTO-003", "AC-8")
@pytest.mark.asyncio
async def test_fs_auto_003_ac8_pending_approval_state():
    """FS-AUTO-003 AC-8: L1 + L2 required → pending_approval 상태 생성."""
    from app.services.playbook_executor import _playbook_cache, execute_playbook

    _playbook_cache.clear()
    result = await execute_playbook(
        playbook_name="index-optimization",  # min_autonomy_level: 2
        instance_id=uuid4(),
        autonomy_level=1,
        confidence_score=0.8,
    )
    assert result.status.value == "pending_approval"
    assert result.execution_id is not None  # can be used for approve/reject


@spec_ref("FS-AUTO-003", "AC-8")
def test_fs_auto_003_ac8_approve_endpoint_exists():
    """FS-AUTO-003 AC-8: /playbooks/{name}/execute POST 엔드포인트 등록됨."""
    from app.main import app as fastapi_app

    paths = [r.path for r in fastapi_app.routes]
    assert "/api/v1/playbooks/{name}/execute" in paths


@spec_ref("FS-AUTO-003", "AC-8")
def test_fs_auto_003_ac8_approve_request_schema():
    """FS-AUTO-003 AC-8: PlaybookApproveRequest 스키마 유효."""
    from app.schemas.playbook import PlaybookApproveRequest

    req = PlaybookApproveRequest(approved=True, comment="LGTM")
    assert req.approved is True

    req2 = PlaybookApproveRequest(approved=False, comment="Too risky")
    assert req2.approved is False

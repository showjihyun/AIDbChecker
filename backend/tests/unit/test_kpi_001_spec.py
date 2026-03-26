# Spec: FS-KPI-001
"""Tests for FS-KPI-001 Acceptance Criteria.

Covers delta-based KPI calculations, threshold evaluation, connection usage,
and advisory generation. Frontend ACs are skipped (require Vitest).

IMPORTANT: Do NOT delete the @spec_ref decorator -- it enables AC tracking in CI.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# Helpers: import production code under test
# ---------------------------------------------------------------------------
from app.services.kpi_calculator import (
    KPICalculator,
    _evaluate_status,
    _make_kpi,
)
from app.schemas.kpi import KPIResponse, KPIValue


# ---------------------------------------------------------------------------
# AC-1: GET /api/v1/instances/{id}/kpi returns all 12 KPIs
# ---------------------------------------------------------------------------
@spec_ref("FS-KPI-001", "AC-1")
async def test_fs_kpi_001_ac1_get_api_v1_instances_id_kpi_12_kpi(
    client, sample_instance
):
    """FS-KPI-001 AC-1: GET /api/v1/instances/{id}/kpi에서 12개 KPI가 모두 반환됨"""
    # Override auth dependency to bypass JWT requirement
    from app.api.deps import get_current_user
    from app.main import app as fastapi_app

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_user.role = "super_admin"
    mock_user.is_active = True

    async def _override_auth():
        return mock_user

    fastapi_app.dependency_overrides[get_current_user] = _override_auth
    try:
        response = await client.get(
            f"/api/v1/instances/{sample_instance.id}/kpi"
        )
    finally:
        # Restore only the auth override; client fixture manages get_session
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    data = response.json()

    # Verify 5 categories exist
    assert "throughput" in data
    assert "resource" in data
    assert "connection" in data
    assert "lock" in data
    assert "storage" in data

    # Verify all 12 KPIs are present (4 + 2 + 2 + 2 + 2)
    assert "tps" in data["throughput"]
    assert "qps" in data["throughput"]
    assert "avg_response_time_ms" in data["throughput"]
    assert "slow_queries" in data["throughput"]
    assert "buffer_hit_ratio" in data["resource"]
    assert "disk_iops" in data["resource"]
    assert "active_sessions" in data["connection"]
    assert "connection_usage_pct" in data["connection"]
    assert "lock_waits" in data["lock"]
    assert "deadlocks_per_sec" in data["lock"]
    assert "db_size_bytes" in data["storage"]
    assert "replication_lag_sec" in data["storage"]

    # Each KPI must have value, unit, status fields
    for kpi_val in [
        data["throughput"]["tps"],
        data["throughput"]["qps"],
        data["resource"]["buffer_hit_ratio"],
        data["lock"]["deadlocks_per_sec"],
        data["storage"]["db_size_bytes"],
    ]:
        assert "unit" in kpi_val
        assert "status" in kpi_val
        assert kpi_val["status"] in ("normal", "warning", "critical", "unknown")


# ---------------------------------------------------------------------------
# AC-2: TPS, QPS, Deadlocks are delta/second based
# ---------------------------------------------------------------------------
@spec_ref("FS-KPI-001", "AC-2")
async def test_fs_kpi_001_ac2_tps_qps_deadlocks_delta():
    """FS-KPI-001 AC-2: TPS, QPS, Deadlocks는 delta/초 기반으로 계산됨"""
    calc = KPICalculator()

    # TPS: 1000 transactions over 10 seconds = 100 tx/s
    assert calc.compute_delta_rate(current=2000, previous=1000, interval_sec=10) == 100.0

    # QPS: 5000 queries over 5 seconds = 1000 q/s
    assert calc.compute_delta_rate(current=10000, previous=5000, interval_sec=5) == 1000.0

    # Deadlocks: 3 deadlocks over 60 seconds = 0.05 deadlocks/s
    assert calc.compute_delta_rate(current=103, previous=100, interval_sec=60) == pytest.approx(0.05, abs=1e-9)

    # Counter wrap (current < previous) should clamp to 0
    assert calc.compute_delta_rate(current=50, previous=1000, interval_sec=10) == 0.0

    # Zero interval should return 0 (no division by zero)
    assert calc.compute_delta_rate(current=100, previous=50, interval_sec=0) == 0.0

    # Negative interval should return 0
    assert calc.compute_delta_rate(current=100, previous=50, interval_sec=-5) == 0.0


# ---------------------------------------------------------------------------
# AC-3: Buffer Hit Ratio is delta-based (not cumulative ratio)
# ---------------------------------------------------------------------------
@spec_ref("FS-KPI-001", "AC-3")
async def test_fs_kpi_001_ac3_buffer_hit_ratio_delta():
    """FS-KPI-001 AC-3: Buffer Hit Ratio는 delta 기반 (누적 비율이 아님)"""
    calc = KPICalculator()

    # Normal case: 950 hits, 50 reads => 95%
    assert calc.compute_hit_ratio(delta_hit=950, delta_read=50) == 95.0

    # Perfect cache: 1000 hits, 0 reads => 100%
    assert calc.compute_hit_ratio(delta_hit=1000, delta_read=0) == 100.0

    # No activity (both 0) => 100% (all from cache, no I/O)
    assert calc.compute_hit_ratio(delta_hit=0, delta_read=0) == 100.0

    # Poor cache: 500 hits, 500 reads => 50%
    assert calc.compute_hit_ratio(delta_hit=500, delta_read=500) == 50.0

    # Edge: all reads, no hits => 0%
    assert calc.compute_hit_ratio(delta_hit=0, delta_read=100) == 0.0

    # Verify the ratio is rounded to 2 decimal places
    result = calc.compute_hit_ratio(delta_hit=333, delta_read=100)
    assert result == pytest.approx(76.91, abs=0.01)


# ---------------------------------------------------------------------------
# AC-4: InstanceCard shows 5 KPIs (Frontend)
# ---------------------------------------------------------------------------
@spec_ref("FS-KPI-001", "AC-4")
async def test_fs_kpi_001_ac4_5_kpi_tps_hit_conn_locks_size():
    """FS-KPI-001 AC-4: 인스턴스 카드에 5개 핵심 KPI가 표시됨 (TPS, Hit%, Conn, Locks, Size)"""
    pytest.skip("Frontend AC -- requires Vitest + React Testing Library")


# ---------------------------------------------------------------------------
# AC-5: KPI Overview Panel shows 12 KPIs (Frontend)
# ---------------------------------------------------------------------------
@spec_ref("FS-KPI-001", "AC-5")
async def test_fs_kpi_001_ac5_kpi_overview_panel_12_kpi():
    """FS-KPI-001 AC-5: KPI Overview Panel이 인스턴스 선택 시 12개 전체 KPI 표시"""
    pytest.skip("Frontend AC -- requires Vitest + React Testing Library")


# ---------------------------------------------------------------------------
# AC-6: Threshold colors normal/warning/critical
# ---------------------------------------------------------------------------
@spec_ref("FS-KPI-001", "AC-6")
async def test_fs_kpi_001_ac6_normal_warning_critical():
    """FS-KPI-001 AC-6: 임계값에 따라 normal/warning/critical 색상 코딩"""
    # --- Upper-is-worse metrics ---

    # TPS: warn=5000, crit=10000
    assert _evaluate_status("tps", 100) == "normal"
    assert _evaluate_status("tps", 5000) == "warning"
    assert _evaluate_status("tps", 7000) == "warning"
    assert _evaluate_status("tps", 10000) == "critical"
    assert _evaluate_status("tps", 15000) == "critical"

    # Connection usage: warn=80, crit=95
    assert _evaluate_status("connection_usage_pct", 50) == "normal"
    assert _evaluate_status("connection_usage_pct", 80) == "warning"
    assert _evaluate_status("connection_usage_pct", 95) == "critical"

    # Deadlocks: warn=0.1, crit=1.0
    assert _evaluate_status("deadlocks_per_sec", 0.0) == "normal"
    assert _evaluate_status("deadlocks_per_sec", 0.1) == "warning"
    assert _evaluate_status("deadlocks_per_sec", 1.0) == "critical"

    # Replication lag: warn=10, crit=60
    assert _evaluate_status("replication_lag_sec", 5) == "normal"
    assert _evaluate_status("replication_lag_sec", 10) == "warning"
    assert _evaluate_status("replication_lag_sec", 60) == "critical"

    # --- Lower-is-worse metrics (inverted) ---

    # Buffer hit ratio: warn=<95, crit=<90
    assert _evaluate_status("buffer_hit_ratio", 99.5) == "normal"
    assert _evaluate_status("buffer_hit_ratio", 95) == "normal"    # >= 95 is normal
    assert _evaluate_status("buffer_hit_ratio", 93) == "warning"   # <95 but >=90
    assert _evaluate_status("buffer_hit_ratio", 89) == "critical"  # <90

    # --- None value ---
    assert _evaluate_status("tps", None) == "unknown"

    # --- Unknown metric (not in thresholds) ---
    assert _evaluate_status("some_unknown_metric", 999) == "normal"

    # --- _make_kpi integrates status ---
    kpi = _make_kpi("connection_usage_pct", 96.0, "%")
    assert kpi.status == "critical"
    assert kpi.value == 96.0
    assert kpi.unit == "%"


# ---------------------------------------------------------------------------
# AC-7: Connection usage % = numbackends / max_connections * 100
# ---------------------------------------------------------------------------
@spec_ref("FS-KPI-001", "AC-7")
async def test_fs_kpi_001_ac7_max_connections():
    """FS-KPI-001 AC-7: max_connections 대비 연결 사용률(%) 표시"""
    instance_id = uuid4()

    # Mock adapter that returns live KPI data with numbackends/max_connections
    mock_adapter = AsyncMock()
    mock_adapter.collect_kpi_extras = AsyncMock(return_value={
        "numbackends": 40,
        "max_connections": 200,
        "active_sessions": 5,
        "lock_waits": 0,
        "slow_query_count": 0,
        "avg_response_time_ms": 2.5,
    })

    # Mock the DB session to return no metric samples (focus on live KPIs)
    mock_session = AsyncMock()
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    result = await KPICalculator.compute_all_kpi(
        instance_id=instance_id,
        session=mock_session,
        adapter=mock_adapter,
    )

    # 40 / 200 * 100 = 20.0%
    assert result.connection.connection_usage_pct.value == 20.0
    assert result.connection.connection_usage_pct.status == "normal"

    # Test with high connection usage
    mock_adapter.collect_kpi_extras = AsyncMock(return_value={
        "numbackends": 190,
        "max_connections": 200,
        "active_sessions": 50,
        "lock_waits": 0,
        "slow_query_count": 0,
        "avg_response_time_ms": None,
    })
    result2 = await KPICalculator.compute_all_kpi(
        instance_id=instance_id,
        session=mock_session,
        adapter=mock_adapter,
    )
    # 190 / 200 * 100 = 95.0% -> critical
    assert result2.connection.connection_usage_pct.value == 95.0
    assert result2.connection.connection_usage_pct.status == "critical"


# ---------------------------------------------------------------------------
# AC-8: pg_stat_statements advisory warning + CREATE EXTENSION SQL
# ---------------------------------------------------------------------------
@spec_ref("FS-KPI-001", "AC-8")
async def test_fs_kpi_001_ac8_pg_stat_statements_advisory_warning_create_extensi():
    """FS-KPI-001 AC-8: pg_stat_statements 미설치 시 advisory warning + CREATE EXTENSION SQL 안내"""
    instance_id = uuid4()

    # Mock adapter that returns None for avg_response_time_ms (extension missing)
    mock_adapter = AsyncMock()
    mock_adapter.collect_kpi_extras = AsyncMock(return_value={
        "numbackends": 10,
        "max_connections": 200,
        "active_sessions": 3,
        "lock_waits": 0,
        "slow_query_count": None,
        "avg_response_time_ms": None,  # pg_stat_statements not installed
    })

    mock_session = AsyncMock()
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    result = await KPICalculator.compute_all_kpi(
        instance_id=instance_id,
        session=mock_session,
        adapter=mock_adapter,
    )

    # Should have a pg_stat_statements advisory
    pg_advisory = [
        a for a in result.advisories
        if "pg_stat_statements" in a.title
    ]
    assert len(pg_advisory) >= 1, "Expected pg_stat_statements advisory"

    adv = pg_advisory[0]
    assert adv.level == "warning"
    assert adv.action is not None
    assert "CREATE EXTENSION" in adv.action
    assert "pg_stat_statements" in adv.action


# ---------------------------------------------------------------------------
# AC-9: Toast auto-dismiss (Frontend)
# ---------------------------------------------------------------------------
@spec_ref("FS-KPI-001", "AC-9")
async def test_fs_kpi_001_ac9_toast_info_8_warning_12():
    """FS-KPI-001 AC-9: Toast 알림이 화면 우상단에 표시되고 자동 닫힘 (info 8초, warning 12초)"""
    pytest.skip("Frontend AC -- requires Vitest + React Testing Library")


# ---------------------------------------------------------------------------
# AC-10: NotificationPanel copy action (Frontend)
# ---------------------------------------------------------------------------
@spec_ref("FS-KPI-001", "AC-10")
async def test_fs_kpi_001_ac10_notification_panel_advisory_sql_action():
    """FS-KPI-001 AC-10: Notification Panel에서 advisory 목록 확인 + SQL action 복사 가능"""
    pytest.skip("Frontend AC -- requires Vitest + React Testing Library")


# ---------------------------------------------------------------------------
# AC-11: Unread badge (Frontend)
# ---------------------------------------------------------------------------
@spec_ref("FS-KPI-001", "AC-11")
async def test_fs_kpi_001_ac11():
    """FS-KPI-001 AC-11: 알림 벨에 미읽음 수 빨간 배지 표시"""
    pytest.skip("Frontend AC -- requires Vitest + React Testing Library")

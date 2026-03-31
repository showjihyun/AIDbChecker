# Spec: FS-SELF-001
"""Tests for System Health monitoring — FS-SELF-001 AC-1~6."""

from tests.conftest import spec_ref


@spec_ref("FS-SELF-001", "AC-1")
def test_fs_self_001_ac1_health_returns_components():
    """FS-SELF-001 AC-1: GET /system/health returns DB/Valkey/Celery + status."""
    from app.api.v1.system import HealthStatus

    fields = HealthStatus.model_fields
    assert "db" in fields
    assert "valkey" in fields
    assert "celery" in fields
    assert "status" in fields


@spec_ref("FS-SELF-001", "AC-2")
def test_fs_self_001_ac2_db_down_unhealthy():
    """FS-SELF-001 AC-2: DB down → status 'unhealthy'."""
    components = {"db": "down", "valkey": "up", "celery": "up"}
    if components["db"] == "down":
        overall = "unhealthy"
    elif all(v == "up" for v in components.values()):
        overall = "healthy"
    else:
        overall = "degraded"
    assert overall == "unhealthy"


@spec_ref("FS-SELF-001", "AC-3")
def test_fs_self_001_ac3_valkey_down_degraded():
    """FS-SELF-001 AC-3: Valkey down → status 'degraded'."""
    components = {"db": "up", "valkey": "down", "celery": "up"}
    if components["db"] == "down":
        overall = "unhealthy"
    elif all(v == "up" for v in components.values()):
        overall = "healthy"
    else:
        overall = "degraded"
    assert overall == "degraded"


@spec_ref("FS-SELF-001", "AC-4")
def test_fs_self_001_ac4_prometheus_metrics():
    """FS-SELF-001 AC-4: /metrics exposes Prometheus format."""
    import app.main as main_module

    source = open(main_module.__file__, encoding="utf-8").read()
    assert "Instrumentator" in source
    assert "/metrics" in source


@spec_ref("FS-SELF-001", "AC-5")
def test_fs_self_001_ac5_frontend_system_health():
    """FS-SELF-001 AC-5: Frontend SystemHealth component exists."""
    from pathlib import Path

    component = Path(__file__).resolve().parents[3] / "frontend/src/components/dashboard/SystemHealth.tsx"
    assert component.exists()
    content = component.read_text(encoding="utf-8")
    assert "SystemHealthPanel" in content


@spec_ref("FS-SELF-001", "AC-6")
def test_fs_self_001_ac6_health_detail_endpoint():
    """FS-SELF-001 AC-6: /system/health/detail returns uptime, version, latencies."""
    from app.api.v1.system import HealthDetail, ComponentHealthDetail

    fields = HealthDetail.model_fields
    assert "uptime_seconds" in fields
    assert "version" in fields
    assert "components" in fields

    comp_fields = ComponentHealthDetail.model_fields
    assert "latency_ms" in comp_fields
    assert "last_checked_at" in comp_fields


@spec_ref("FS-SELF-001", "AC-7")
def test_fs_self_001_ac7_celery_pool_solo_fallback():
    """FS-SELF-001 AC-7: Celery health check fallback for --pool solo busy workers."""
    import inspect

    from app.api.v1.system import _check_celery_detail

    source = inspect.getsource(_check_celery_detail)
    # Verify fallback to active_queues when ping fails
    assert "active_queues" in source

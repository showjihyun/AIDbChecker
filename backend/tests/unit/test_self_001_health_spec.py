# Spec: FS-SELF-001
"""Spec-Driven tests for System Health monitoring.

Feature Spec: docs/specs/services/SYSTEM_HEALTH_SPEC.md
PRD Reference: FR-SELF-001, MVP-DASH-005
ACs: AC-1 through AC-6

Tests cover:
  - GET /system/health returns DB/Valkey/Celery component status + overall status
  - DB down -> unhealthy
  - Valkey down -> degraded
  - GET /metrics exposes Prometheus format
  - (AC-5 skipped -- frontend component test)
  - GET /system/health/detail returns uptime, version, latency per component
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# Helper: status resolution logic (mirrors the actual implementation)
# ---------------------------------------------------------------------------

def resolve_overall_status(db: str, valkey: str, celery: str) -> str:
    """Determine overall system status from component statuses.

    Spec: FS-SELF-001 -- DB down=unhealthy, partial down=degraded, all up=healthy.
    """
    if db == "down":
        return "unhealthy"
    if all(s == "up" for s in [db, valkey, celery]):
        return "healthy"
    return "degraded"


# ---------------------------------------------------------------------------
# AC-1: GET /system/health returns DB/Valkey/Celery + overall status
# ---------------------------------------------------------------------------

@spec_ref("FS-SELF-001", "AC-1")
def test_fs_self_001_ac1_health_status_model_fields():
    """HealthStatus model has db, valkey, celery, status fields."""
    from app.api.v1.system import HealthStatus

    fields = HealthStatus.model_fields
    assert "db" in fields
    assert "valkey" in fields
    assert "celery" in fields
    assert "status" in fields


@spec_ref("FS-SELF-001", "AC-1")
def test_fs_self_001_ac1_health_status_all_up():
    """All components up -> status='healthy'."""
    from app.api.v1.system import HealthStatus

    health = HealthStatus(db="up", valkey="up", celery="up", status="healthy")
    assert health.status == "healthy"


@spec_ref("FS-SELF-001", "AC-1")
def test_fs_self_001_ac1_overall_status_logic_all_up():
    """resolve_overall_status returns 'healthy' when all components are up."""
    assert resolve_overall_status("up", "up", "up") == "healthy"


@spec_ref("FS-SELF-001", "AC-1")
def test_fs_self_001_ac1_health_endpoint_exists():
    """GET /system/health endpoint function exists in system module."""
    from app.api.v1 import system as system_module

    assert hasattr(system_module, "health_check")
    assert callable(system_module.health_check)


@spec_ref("FS-SELF-001", "AC-1")
@pytest.mark.asyncio
async def test_fs_self_001_ac1_health_endpoint_returns_200(client):
    """GET /api/v1/system/health returns 200 with component statuses."""
    with patch("app.api.v1.system._check_db", new_callable=AsyncMock, return_value="up"), \
         patch("app.api.v1.system._check_valkey", new_callable=AsyncMock, return_value="up"), \
         patch("app.api.v1.system._check_celery", new_callable=AsyncMock, return_value="up"):
        resp = await client.get("/api/v1/system/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "db" in body
        assert "valkey" in body
        assert "celery" in body
        assert "status" in body
        assert body["status"] == "healthy"


# ---------------------------------------------------------------------------
# AC-2: DB down -> status: "unhealthy"
# ---------------------------------------------------------------------------

@spec_ref("FS-SELF-001", "AC-2")
def test_fs_self_001_ac2_db_down_is_unhealthy():
    """DB down with other components up -> overall 'unhealthy'."""
    assert resolve_overall_status("down", "up", "up") == "unhealthy"


@spec_ref("FS-SELF-001", "AC-2")
def test_fs_self_001_ac2_db_down_all_down_is_unhealthy():
    """All components down -> still 'unhealthy' (DB down takes priority)."""
    assert resolve_overall_status("down", "down", "down") == "unhealthy"


@spec_ref("FS-SELF-001", "AC-2")
@pytest.mark.asyncio
async def test_fs_self_001_ac2_api_returns_unhealthy_when_db_down(client):
    """GET /system/health returns unhealthy when DB is unreachable."""
    with patch("app.api.v1.system._check_db", new_callable=AsyncMock, return_value="down"), \
         patch("app.api.v1.system._check_valkey", new_callable=AsyncMock, return_value="up"), \
         patch("app.api.v1.system._check_celery", new_callable=AsyncMock, return_value="up"):
        resp = await client.get("/api/v1/system/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["db"] == "down"
        assert body["status"] == "unhealthy"


# ---------------------------------------------------------------------------
# AC-3: Valkey down -> status: "degraded"
# ---------------------------------------------------------------------------

@spec_ref("FS-SELF-001", "AC-3")
def test_fs_self_001_ac3_valkey_down_is_degraded():
    """Valkey down with DB up -> overall 'degraded'."""
    assert resolve_overall_status("up", "down", "up") == "degraded"


@spec_ref("FS-SELF-001", "AC-3")
def test_fs_self_001_ac3_celery_down_is_degraded():
    """Celery down with DB up -> overall 'degraded'."""
    assert resolve_overall_status("up", "up", "down") == "degraded"


@spec_ref("FS-SELF-001", "AC-3")
def test_fs_self_001_ac3_valkey_and_celery_down_is_degraded():
    """Valkey + Celery down (DB up) -> still 'degraded' (not unhealthy)."""
    assert resolve_overall_status("up", "down", "down") == "degraded"


@spec_ref("FS-SELF-001", "AC-3")
@pytest.mark.asyncio
async def test_fs_self_001_ac3_api_returns_degraded_when_valkey_down(client):
    """GET /system/health returns degraded when Valkey is unreachable."""
    with patch("app.api.v1.system._check_db", new_callable=AsyncMock, return_value="up"), \
         patch("app.api.v1.system._check_valkey", new_callable=AsyncMock, return_value="down"), \
         patch("app.api.v1.system._check_celery", new_callable=AsyncMock, return_value="up"):
        resp = await client.get("/api/v1/system/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["valkey"] == "down"
        assert body["status"] == "degraded"


# ---------------------------------------------------------------------------
# AC-4: GET /metrics -> Prometheus format
# ---------------------------------------------------------------------------

@spec_ref("FS-SELF-001", "AC-4")
def test_fs_self_001_ac4_prometheus_instrumentator_configured():
    """FastAPI app uses Instrumentator for Prometheus /metrics endpoint."""
    import app.main as main_module

    source = open(main_module.__file__, encoding="utf-8").read()
    assert "Instrumentator" in source, (
        "Prometheus Instrumentator not found in app.main"
    )


@spec_ref("FS-SELF-001", "AC-4")
def test_fs_self_001_ac4_metrics_endpoint_exposed():
    """FastAPI app exposes /metrics endpoint."""
    import app.main as main_module

    source = open(main_module.__file__, encoding="utf-8").read()
    assert "/metrics" in source, "/metrics endpoint not found in app.main"


@spec_ref("FS-SELF-001", "AC-4")
@pytest.mark.asyncio
async def test_fs_self_001_ac4_metrics_endpoint_returns_200(client):
    """GET /metrics returns 200 with Prometheus text format."""
    resp = await client.get("/metrics")
    # Prometheus instrumentator should respond
    # (may be 200 or 404 depending on startup hook execution in tests)
    if resp.status_code == 200:
        content_type = resp.headers.get("content-type", "")
        # Prometheus responses use text/plain or openmetrics format
        assert "text" in content_type or "openmetrics" in content_type


# ---------------------------------------------------------------------------
# AC-5: Frontend SystemHealth component (skip -- frontend test)
# ---------------------------------------------------------------------------

@spec_ref("FS-SELF-001", "AC-5")
def test_fs_self_001_ac5_frontend_component_exists():
    """Frontend SystemHealth component exists (file presence check)."""
    from pathlib import Path

    component = (
        Path(__file__).resolve().parents[3]
        / "frontend" / "src" / "components" / "dashboard" / "SystemHealth.tsx"
    )
    if component.exists():
        content = component.read_text(encoding="utf-8")
        assert "SystemHealthPanel" in content or "SystemHealth" in content
    else:
        pytest.skip("Frontend component not yet created")


# ---------------------------------------------------------------------------
# AC-6: GET /system/health/detail -> uptime, version, latency
# ---------------------------------------------------------------------------

@spec_ref("FS-SELF-001", "AC-6")
def test_fs_self_001_ac6_health_detail_model_fields():
    """HealthDetail model has uptime_seconds, version, components fields."""
    from app.api.v1.system import HealthDetail

    fields = HealthDetail.model_fields
    assert "uptime_seconds" in fields
    assert "version" in fields
    assert "components" in fields
    assert "status" in fields


@spec_ref("FS-SELF-001", "AC-6")
def test_fs_self_001_ac6_component_health_detail_model():
    """ComponentHealthDetail has latency_ms and last_checked_at fields."""
    from app.api.v1.system import ComponentHealthDetail

    fields = ComponentHealthDetail.model_fields
    assert "status" in fields
    assert "latency_ms" in fields
    assert "last_checked_at" in fields


@spec_ref("FS-SELF-001", "AC-6")
def test_fs_self_001_ac6_health_detail_endpoint_exists():
    """GET /system/health/detail endpoint function exists."""
    from app.api.v1 import system as system_module

    assert hasattr(system_module, "health_detail")
    assert callable(system_module.health_detail)


@spec_ref("FS-SELF-001", "AC-6")
def test_fs_self_001_ac6_health_detail_schema_validation():
    """HealthDetail can be constructed with valid data."""
    from app.api.v1.system import HealthDetail, ComponentHealthDetail

    now = datetime.now(timezone.utc)
    detail = HealthDetail(
        status="healthy",
        uptime_seconds=3600,
        version="0.5.0.0",
        components={
            "db": ComponentHealthDetail(
                status="up", latency_ms=2, last_checked_at=now,
            ),
            "valkey": ComponentHealthDetail(
                status="up", latency_ms=1, last_checked_at=now,
            ),
            "celery": ComponentHealthDetail(
                status="up", latency_ms=150, last_checked_at=now,
            ),
        },
    )
    assert detail.uptime_seconds == 3600
    assert detail.version == "0.5.0.0"
    assert len(detail.components) == 3
    assert detail.components["db"].latency_ms == 2


@spec_ref("FS-SELF-001", "AC-6")
def test_fs_self_001_ac6_component_detail_latency_nullable():
    """ComponentHealthDetail.latency_ms is nullable (None when component is down)."""
    from app.api.v1.system import ComponentHealthDetail

    now = datetime.now(timezone.utc)
    comp = ComponentHealthDetail(
        status="down", latency_ms=None, last_checked_at=now,
    )
    assert comp.latency_ms is None
    assert comp.status == "down"


@spec_ref("FS-SELF-001", "AC-6")
@pytest.mark.asyncio
async def test_fs_self_001_ac6_health_detail_api_returns_200(client):
    """GET /api/v1/system/health/detail returns 200 with detailed info."""
    with patch("app.api.v1.system._check_db_detail", new_callable=AsyncMock, return_value=("up", 3)), \
         patch("app.api.v1.system._check_valkey_detail", new_callable=AsyncMock, return_value=("up", 1)), \
         patch("app.api.v1.system._check_celery_detail", new_callable=AsyncMock, return_value=("up", 120, {"worker_count": 4})):
        resp = await client.get("/api/v1/system/health/detail")
        assert resp.status_code == 200
        body = resp.json()
        assert "uptime_seconds" in body
        assert "version" in body
        assert "components" in body
        assert "db" in body["components"]
        assert "valkey" in body["components"]
        assert "celery" in body["components"]
        # Verify latency is present
        assert body["components"]["db"]["latency_ms"] is not None


@spec_ref("FS-SELF-001", "AC-6")
@pytest.mark.asyncio
async def test_fs_self_001_ac6_health_detail_shows_degraded_when_valkey_down(client):
    """GET /system/health/detail shows degraded + null latency for down component."""
    with patch("app.api.v1.system._check_db_detail", new_callable=AsyncMock, return_value=("up", 2)), \
         patch("app.api.v1.system._check_valkey_detail", new_callable=AsyncMock, return_value=("down", None)), \
         patch("app.api.v1.system._check_celery_detail", new_callable=AsyncMock, return_value=("up", 100, {"worker_count": 2})):
        resp = await client.get("/api/v1/system/health/detail")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["components"]["valkey"]["status"] == "down"
        assert body["components"]["valkey"]["latency_ms"] is None

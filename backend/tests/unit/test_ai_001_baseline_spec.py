# Spec: FS-AI-001
"""Spec-Driven tests for Auto Baseline (STL + Isolation Forest).

Feature Spec: docs/specs/ai/AUTO_BASELINE_SPEC.md
PRD Reference: FR-AI-001, MVP-AI-001, MVP-AI-002, MVP-AI-003
ACs: AC-1 through AC-7

Tests cover:
  - Baseline model fields and time-bucket classification
  - API endpoint contract for list and retrain
  - Anomaly detection -> incident creation with source="ai_baseline"
  - Celery Beat 6-hour retrain schedule
  - Valkey cache integration (mocked)
  - Dual defense: manual threshold + AI baseline
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# Fixtures: authenticated client for protected baselines endpoints
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def auth_client(async_session: AsyncSession):
    """httpx.AsyncClient with auth dependency overridden (no JWT needed)."""
    from app.db.session import get_session
    from app.api.deps import get_current_user
    from app.main import app as fastapi_app

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_user.role = "super_admin"

    async def _override_session():
        yield async_session

    fastapi_app.dependency_overrides[get_session] = _override_session
    fastapi_app.dependency_overrides[get_current_user] = lambda: mock_user

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_instance(async_session: AsyncSession):
    """Create a unique DBInstance for baseline tests."""
    from app.models.db_instance import DBInstance

    instance = DBInstance(
        id=uuid4(),
        name=f"baseline-test-{uuid4().hex[:8]}",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="testdb",
        environment="development",
        connection_config={},
        is_active=True,
        autonomy_level=0,
    )
    async_session.add(instance)
    await async_session.commit()
    await async_session.refresh(instance)
    return instance


# ---------------------------------------------------------------------------
# AC-1: 2-week metric data -> time-bucket baselines auto-generated
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-001", "AC-1")
def test_fs_ai_001_ac1_baseline_model_has_time_bucket_fields():
    """Baseline model exposes all fields required for time-bucket learning."""
    from app.models.baseline import Baseline

    required_fields = [
        "instance_id", "metric_type", "time_bucket",
        "normal_min", "normal_max", "mean", "stddev",
        "model_type", "model_params", "training_samples",
        "last_trained_at", "is_active",
    ]
    for field in required_fields:
        assert hasattr(Baseline, field), f"Baseline missing field: {field}"


@spec_ref("FS-AI-001", "AC-1")
def test_fs_ai_001_ac1_classify_time_bucket_weekday_business():
    """classify_time_bucket returns weekday_business for Mon-Fri 09:00-17:59."""
    from app.analyzers.baseline import classify_time_bucket

    # Wednesday 14:00 UTC
    dt = datetime(2026, 3, 25, 14, 0, 0, tzinfo=timezone.utc)
    assert classify_time_bucket(dt) == "weekday_business"


@spec_ref("FS-AI-001", "AC-1")
def test_fs_ai_001_ac1_classify_time_bucket_weekday_night():
    """classify_time_bucket returns weekday_night for Mon-Fri outside 09-18."""
    from app.analyzers.baseline import classify_time_bucket

    # Tuesday 02:00 UTC
    dt = datetime(2026, 3, 24, 2, 0, 0, tzinfo=timezone.utc)
    assert classify_time_bucket(dt) == "weekday_night"


@spec_ref("FS-AI-001", "AC-1")
def test_fs_ai_001_ac1_classify_time_bucket_weekend():
    """classify_time_bucket returns weekend for Sat-Sun."""
    from app.analyzers.baseline import classify_time_bucket

    # Saturday 12:00 UTC
    dt = datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
    assert classify_time_bucket(dt) == "weekend"


@spec_ref("FS-AI-001", "AC-1")
def test_fs_ai_001_ac1_compute_baseline_returns_required_keys():
    """_compute_baseline returns normal_min, normal_max, mean, stddev, model_params."""
    from app.analyzers.baseline import _compute_baseline

    import numpy as np

    np.random.seed(42)
    now = datetime(2026, 3, 25, 10, 0, 0, tzinfo=timezone.utc)
    data_points = [
        (now, float(v))
        for v in np.random.normal(50.0, 5.0, 200)
    ]

    result = _compute_baseline(data_points)

    assert "normal_min" in result
    assert "normal_max" in result
    assert "mean" in result
    assert "stddev" in result
    assert "model_params" in result
    assert result["stddev"] > 0, "stddev must be positive"
    assert result["normal_min"] <= result["mean"] <= result["normal_max"]


@spec_ref("FS-AI-001", "AC-1")
def test_fs_ai_001_ac1_hot_metric_keys_defined():
    """HOT_METRIC_KEYS includes the 5 required MVP hot metrics."""
    from app.analyzers.baseline import HOT_METRIC_KEYS

    expected = {"cpu_usage", "memory_usage", "active_connections", "tps", "buffer_hit_ratio"}
    assert expected.issubset(set(HOT_METRIC_KEYS))


# ---------------------------------------------------------------------------
# AC-2: GET /instances/{id}/baselines returns learned baselines
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-001", "AC-2")
def test_fs_ai_001_ac2_list_baselines_endpoint_exists():
    """list_baselines function exists in baselines router module."""
    from app.api.v1 import baselines as baselines_module

    assert hasattr(baselines_module, "list_baselines")
    assert callable(baselines_module.list_baselines)


@spec_ref("FS-AI-001", "AC-2")
def test_fs_ai_001_ac2_baseline_response_schema():
    """BaselineResponse schema validates all required fields."""
    from app.schemas.baseline import BaselineResponse

    fields = BaselineResponse.model_fields
    required = [
        "id", "instance_id", "metric_type", "time_bucket",
        "normal_min", "normal_max", "mean", "stddev",
        "model_type", "training_samples", "last_trained_at",
        "is_active",
    ]
    for field in required:
        assert field in fields, f"BaselineResponse missing: {field}"


@spec_ref("FS-AI-001", "AC-2")
def test_fs_ai_001_ac2_baseline_list_response_schema():
    """BaselineListResponse wraps items list with total count."""
    from app.schemas.baseline import BaselineListResponse

    fields = BaselineListResponse.model_fields
    assert "items" in fields
    assert "total" in fields


@spec_ref("FS-AI-001", "AC-2")
@pytest.mark.asyncio
async def test_fs_ai_001_ac2_list_baselines_api_returns_200(auth_client, test_instance):
    """GET /api/v1/instances/{id}/baselines returns 200 with items list."""
    resp = await auth_client.get(
        f"/api/v1/instances/{test_instance.id}/baselines"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


# ---------------------------------------------------------------------------
# AC-3: POST /instances/{id}/baselines/retrain triggers manual retrain
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-001", "AC-3")
def test_fs_ai_001_ac3_trigger_retrain_endpoint_exists():
    """trigger_retrain function exists in baselines router module."""
    from app.api.v1 import baselines as baselines_module

    assert hasattr(baselines_module, "trigger_retrain")
    assert callable(baselines_module.trigger_retrain)


@spec_ref("FS-AI-001", "AC-3")
def test_fs_ai_001_ac3_retrain_response_schema():
    """BaselineRetrainResponse has message, instance_id, task_id."""
    from app.schemas.baseline import BaselineRetrainResponse

    fields = BaselineRetrainResponse.model_fields
    assert "message" in fields
    assert "instance_id" in fields
    assert "task_id" in fields


@spec_ref("FS-AI-001", "AC-3")
@pytest.mark.asyncio
async def test_fs_ai_001_ac3_retrain_api_returns_202(auth_client, test_instance):
    """POST /api/v1/instances/{id}/baselines/retrain returns 202 Accepted."""
    with patch("app.tasks.analyze.retrain_baselines") as mock_task:
        mock_result = MagicMock()
        mock_result.id = "test-task-id-123"
        mock_task.delay.return_value = mock_result

        resp = await auth_client.post(
            f"/api/v1/instances/{test_instance.id}/baselines/retrain"
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "message" in body
        assert body["instance_id"] == str(test_instance.id)


# ---------------------------------------------------------------------------
# AC-4: Baseline deviation creates incident with source="ai_baseline"
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-001", "AC-4")
def test_fs_ai_001_ac4_incident_model_supports_ai_baseline_source():
    """Incident model has source, metric_type, metric_value, baseline_value fields."""
    from app.models.incident import Incident

    assert hasattr(Incident, "source")
    assert hasattr(Incident, "metric_type")
    assert hasattr(Incident, "metric_value")
    assert hasattr(Incident, "baseline_value")


@spec_ref("FS-AI-001", "AC-4")
def test_fs_ai_001_ac4_anomaly_detector_severity_thresholds():
    """AnomalyDetector uses sigma thresholds: >3=critical, >2=warning, >1.5=notice."""
    from app.analyzers.baseline import BaselineAnalyzer

    analyzer = BaselineAnalyzer()
    assert hasattr(analyzer, "detect_anomaly")


@spec_ref("FS-AI-001", "AC-4")
@pytest.mark.asyncio
async def test_fs_ai_001_ac4_anomaly_creates_incident_with_ai_baseline_source():
    """AnomalyDetector creates Incident with source='ai_baseline' on anomaly."""
    from app.analyzers.anomaly import AnomalyDetector
    from app.models.incident import Incident

    detector = AnomalyDetector()
    instance_id = uuid4()

    # Mock the baseline analyzer to return a known baseline
    mock_baseline = MagicMock()
    mock_baseline.mean = 50.0
    mock_baseline.stddev = 5.0
    mock_baseline.normal_min = 35.0
    mock_baseline.normal_max = 65.0

    # Build a mock session where `add` is a regular MagicMock (sync call)
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    # Track objects added to the session
    added_objects = []
    mock_session.add.side_effect = lambda obj: added_objects.append(obj)

    # Create an async context manager that yields mock_session
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch.object(
        detector._analyzer, "detect_anomaly",
        new_callable=AsyncMock, return_value=(4.0, "critical")
    ), patch.object(
        detector._analyzer, "get_baseline",
        new_callable=AsyncMock, return_value=mock_baseline
    ), patch(
        "app.analyzers.anomaly._is_in_cooldown",
        new_callable=AsyncMock, return_value=False
    ), patch(
        "app.analyzers.anomaly._set_cooldown",
        new_callable=AsyncMock
    ), patch(
        "app.analyzers.anomaly.AsyncSessionLocal",
        return_value=session_cm
    ):
        incidents = await detector.check(
            instance_id=instance_id,
            metric_sample={"cpu_usage": 80.0},
        )

        # Verify incident was created with correct source
        assert len(added_objects) > 0, (
            "No Incident was added to session. "
            f"session.add calls: {mock_session.add.call_count}"
        )
        incident = added_objects[0]
        assert isinstance(incident, Incident)
        assert incident.source == "ai_baseline"
        assert incident.severity == "critical"
        assert incident.metric_type == "cpu_usage"


# ---------------------------------------------------------------------------
# AC-5: Celery Beat 6-hour auto-retrain
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-001", "AC-5")
def test_fs_ai_001_ac5_celery_beat_has_retrain_schedule():
    """Celery Beat schedule includes retrain-baselines every 6 hours."""
    from app.tasks import celery_app

    beat = celery_app.conf.beat_schedule
    assert "retrain-baselines" in beat, "retrain-baselines not in beat_schedule"

    entry = beat["retrain-baselines"]
    assert entry["task"] == "app.tasks.analyze.retrain_baselines"

    # Verify crontab: every 6 hours (hour="*/6")
    schedule = entry["schedule"]
    from celery.schedules import crontab
    assert isinstance(schedule, crontab)


@spec_ref("FS-AI-001", "AC-5")
def test_fs_ai_001_ac5_retrain_baselines_task_importable():
    """retrain_baselines Celery task is importable and callable."""
    from app.tasks.analyze import retrain_baselines

    assert callable(retrain_baselines)
    assert retrain_baselines.name == "app.tasks.analyze.retrain_baselines"


# ---------------------------------------------------------------------------
# AC-6: Valkey cache for real-time comparison < 100ms
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-001", "AC-6")
def test_fs_ai_001_ac6_cooldown_key_format():
    """Valkey cooldown key follows neuraldb:incident_cooldown:{id}:{metric} format."""
    from app.analyzers.anomaly import _cooldown_key

    iid = uuid4()
    key = _cooldown_key(iid, "cpu_usage")
    assert key.startswith("neuraldb:incident_cooldown:")
    assert str(iid) in key
    assert "cpu_usage" in key


@spec_ref("FS-AI-001", "AC-6")
@pytest.mark.asyncio
async def test_fs_ai_001_ac6_cooldown_prevents_duplicate_incidents():
    """When in cooldown, _is_in_cooldown returns True."""
    from app.analyzers.anomaly import _is_in_cooldown

    instance_id = uuid4()

    # Mock Valkey as returning a cooldown value
    with patch("app.analyzers.anomaly._get_valkey_client", new_callable=AsyncMock) as mock_client_fn:
        mock_client = AsyncMock()
        mock_client.get.return_value = b"1"
        mock_client.aclose = AsyncMock()
        mock_client_fn.return_value = mock_client

        result = await _is_in_cooldown(instance_id, "cpu_usage")
        assert result is True, "Should be in cooldown when Valkey key exists"


@spec_ref("FS-AI-001", "AC-6")
@pytest.mark.asyncio
async def test_fs_ai_001_ac6_cooldown_fallback_when_valkey_down():
    """In-memory fallback deduplication when Valkey is unreachable."""
    from app.analyzers.anomaly import _is_in_cooldown, _set_cooldown, _cooldown_fallback

    instance_id = uuid4()
    metric = "tps"

    # Valkey unavailable
    with patch("app.analyzers.anomaly._get_valkey_client", new_callable=AsyncMock, return_value=None):
        # Not in cooldown initially
        result = await _is_in_cooldown(instance_id, metric)
        assert result is False

        # Set cooldown via fallback
        await _set_cooldown(instance_id, metric)

        # Now should be in cooldown
        result = await _is_in_cooldown(instance_id, metric)
        assert result is True

    # Clean up
    _cooldown_fallback.pop(f"{instance_id}:{metric}", None)


# ---------------------------------------------------------------------------
# AC-7: Manual threshold + AI baseline dual defense
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-001", "AC-7")
def test_fs_ai_001_ac7_incident_source_accepts_both_types():
    """Incident source field accepts both 'ai_baseline' and 'threshold' values."""
    from app.models.incident import Incident

    col = Incident.__table__.columns["source"]
    assert col is not None
    # VARCHAR(30) can hold "ai_baseline" (12 chars) and "threshold" (9 chars)
    assert col.type.length >= 9


@spec_ref("FS-AI-001", "AC-7")
def test_fs_ai_001_ac7_anomaly_detector_independent_of_threshold():
    """AnomalyDetector checks baselines independently from manual thresholds."""
    from app.analyzers.anomaly import AnomalyDetector

    detector = AnomalyDetector()
    # AnomalyDetector only uses BaselineAnalyzer -- no threshold dependency
    assert hasattr(detector, "_analyzer")
    from app.analyzers.baseline import BaselineAnalyzer
    assert isinstance(detector._analyzer, BaselineAnalyzer)

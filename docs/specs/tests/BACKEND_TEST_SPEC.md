# Backend Test Spec: Python/FastAPI 단위 테스트 전략

> **Spec ID**: TEST-BE-001
> **PRD 참조**: FR-DB-001, FR-AI-001~014, FR-AUTO-001, FR-ADMIN-001~004
> **상태**: Approved
> **프레임워크**: pytest + pytest-asyncio + httpx
> **관련 Spec**: API_SPEC.md, ERD.md, AGENT_SPEC.md, MTL_RCA_SPEC.md, CONFIDENCE_SCORE_SPEC.md, LIGHTWEIGHT_RAG_SPEC.md
> **테스트 전략**: `TEST_STRATEGY.md` (Spec-Driven Test Generation)

---

## 1. 테스트 원칙

| 원칙 | 설명 |
|------|------|
| **외부 의존 없음** | DB, Kafka, Valkey, LLM API 모두 Mock/Fixture. Docker 불필요 |
| **async 기본** | 모든 테스트 `async def`. `pytest-asyncio` 사용 |
| **Fixture 기반** | 테스트 데이터는 Factory/Fixture로 생성. 하드코딩 금지 |
| **빠른 실행** | 단위 테스트 전체 <30초 목표 |

> 외부 서비스(DB, Kafka)와 실제 연결하는 테스트는 `TEST_SPEC.md` (Integration)에서 다룸.

---

## 2. 디렉토리 구조

```
backend/
├── app/
│   ├── api/v1/
│   │   ├── monitoring.py
│   │   └── ...
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── adapters/
│   ├── agents/
│   ├── analyzers/
│   ├── collectors/
│   └── tasks/
├── tests/
│   ├── conftest.py                 ← 공통 Fixture
│   ├── factories.py                ← 테스트 데이터 Factory
│   ├── unit/                       ← 단위 테스트 (외부 의존 없음)
│   │   ├── test_schemas.py
│   │   ├── test_services.py
│   │   ├── test_adapters.py
│   │   ├── test_analyzers.py
│   │   ├── test_collectors.py
│   │   ├── test_agents.py
│   │   ├── test_tasks.py
│   │   ├── test_auth.py
│   │   └── test_crypto.py
│   ├── api/                        ← API 라우트 테스트 (httpx + mock service)
│   │   ├── test_instances_api.py
│   │   ├── test_metrics_api.py
│   │   ├── test_incidents_api.py
│   │   ├── test_ash_api.py
│   │   ├── test_nl2sql_api.py
│   │   ├── test_auth_api.py
│   │   ├── test_system_api.py
│   │   ├── test_mtl_api.py          ← MTL RCA API (FS-AI-010)
│   │   ├── test_confidence_api.py   ← Confidence 통계 API (FS-AI-011)
│   │   └── test_rag_api.py          ← RAG 검색 API (FS-AI-RAG-001)
│   └── integration/                ← 통합 테스트 (TEST_SPEC.md 관할)
└── pyproject.toml

### Spec-Driven 테스트 규칙 (TEST_STRATEGY.md 참조)

모든 테스트 함수에 Spec 참조를 명시합니다:

```python
# 규칙 1: @spec_ref 데코레이터로 Spec AC 참조
@spec_ref("FS-AI-010", "AC-1")
async def test_fs_ai_010_ac1_mtl_predict_returns_4_heads():
    """FS-AI-010 AC-1: POST /mtl/predict 호출 시 4개 Head 결과 반환"""
    ...

# 규칙 2: Spec에 없는 기능의 테스트는 작성 금지
# 규칙 3: Spec AC 변경 시 대응 테스트도 반드시 변경
```
```

---

## 3. Fixture 설계

### 3.1 공통 Fixture

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api.deps import get_db, get_current_user

# Mock DB Session
@pytest_asyncio.fixture
async def mock_db():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session

# Mock Current User (RBAC)
@pytest.fixture
def mock_user_admin():
    return User(id="uuid-admin", email="admin@test.com", role="super_admin", is_active=True)

@pytest.fixture
def mock_user_viewer():
    return User(id="uuid-viewer", email="viewer@test.com", role="viewer", is_active=True)

# httpx Test Client (FastAPI)
@pytest_asyncio.fixture
async def client(mock_db, mock_user_admin):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: mock_user_admin
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

### 3.2 데이터 Factory

```python
# tests/factories.py
from uuid import uuid4
from datetime import datetime, timezone
from app.schemas.instance import InstanceResponse
from app.schemas.incident import IncidentResponse

def make_instance(**overrides) -> InstanceResponse:
    defaults = {
        "id": str(uuid4()),
        "name": "pg-test-01",
        "db_type": "postgresql",
        "host": "10.0.1.100",
        "port": 5432,
        "database_name": "testdb",
        "environment": "production",
        "is_active": True,
        "autonomy_level": 1,
        "health_status": "healthy",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    return InstanceResponse(**(defaults | overrides))

def make_incident(**overrides) -> IncidentResponse:
    defaults = {
        "id": str(uuid4()),
        "instance_id": str(uuid4()),
        "severity": "warning",
        "status": "open",
        "title": "Test incident",
        "source": "ai_baseline",
        "detected_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    return IncidentResponse(**(defaults | overrides))

def make_metric_sample(**overrides) -> dict:
    defaults = {
        "instance_id": str(uuid4()),
        "sampled_at": datetime.now(timezone.utc).isoformat(),
        "category": "hot",
        "metrics": {
            "cpu_usage": 45.2,
            "memory_usage": 72.1,
            "active_connections": 42,
            "tps": 1240,
        },
    }
    return defaults | overrides
```

---

## 4. 모듈별 테스트 시나리오

### 4.1 Pydantic Schemas

```python
# tests/unit/test_schemas.py

class TestInstanceSchemas:
    def test_create_instance_valid(self):
        data = InstanceCreate(
            name="pg-prod-01", db_type="postgresql", host="10.0.1.1",
            port=5432, database_name="mydb", environment="production",
            connection_config={"ssl": True},
        )
        assert data.port == 5432

    def test_create_instance_invalid_db_type(self):
        with pytest.raises(ValidationError):
            InstanceCreate(name="x", db_type="oracle", host="x", port=0, ...)

    def test_create_instance_name_too_short(self):
        with pytest.raises(ValidationError):
            InstanceCreate(name="", ...)

    def test_metric_sample_category_enum(self):
        assert MetricCategory("hot") == MetricCategory.HOT
        with pytest.raises(ValueError):
            MetricCategory("ultra")

    def test_incident_severity_ordering(self):
        assert Severity.CRITICAL.value < Severity.WARNING.value  # or custom ordering

    def test_pagination_response(self):
        resp = InstanceList(items=[], total=0, has_next=False)
        assert resp.next_cursor is None
```

### 4.2 Services (비즈니스 로직)

```python
# tests/unit/test_services.py
from app.services.instance import InstanceService

class TestInstanceService:
    async def test_create_instance(self, mock_db):
        service = InstanceService(mock_db)
        mock_db.execute.return_value.scalar_one.return_value = make_instance()

        result = await service.create(InstanceCreate(...))
        assert result.name == "pg-test-01"
        mock_db.commit.assert_called_once()

    async def test_create_duplicate_name_raises(self, mock_db):
        from sqlalchemy.exc import IntegrityError
        mock_db.commit.side_effect = IntegrityError(None, None, None)

        service = InstanceService(mock_db)
        with pytest.raises(HTTPException) as exc:
            await service.create(InstanceCreate(name="duplicate", ...))
        assert exc.value.status_code == 409

    async def test_delete_instance_not_found(self, mock_db):
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        service = InstanceService(mock_db)
        with pytest.raises(HTTPException) as exc:
            await service.delete("nonexistent-uuid")
        assert exc.value.status_code == 404

    async def test_update_autonomy_level_range(self, mock_db):
        service = InstanceService(mock_db)
        with pytest.raises(HTTPException):
            await service.update_autonomy("uuid", level=5)  # max is 4
```

### 4.3 Adapter (PostgreSQL Remote)

```python
# tests/unit/test_adapters.py
from app.adapters.postgresql.adapter import PostgreSQLRemoteAdapter

class TestPostgreSQLRemoteAdapter:
    async def test_collect_metrics_returns_sample(self, mock_pool):
        adapter = PostgreSQLRemoteAdapter(pool=mock_pool)
        mock_pool.fetchrow.return_value = {
            "cpu_usage": 45.2, "active_connections": 42, ...
        }

        sample = await adapter.collect_metrics()
        assert sample.metrics["cpu_usage"] == 45.2
        assert sample.category == "hot"

    async def test_collect_ash_filters_idle_sessions(self, mock_pool):
        adapter = PostgreSQLRemoteAdapter(pool=mock_pool)
        mock_pool.fetch.return_value = [
            {"pid": 1, "state": "active", "wait_event_type": "Lock", ...},
            {"pid": 2, "state": "idle", ...},
        ]

        sessions = await adapter.collect_ash()
        assert len(sessions) == 1  # idle 제외
        assert sessions[0].pid == 1

    async def test_collect_with_timeout_graceful(self, mock_pool):
        """statement_timeout 초과 시 빈 결과 반환 (에러 아님)"""
        import asyncio
        mock_pool.fetchrow.side_effect = asyncio.TimeoutError()

        adapter = PostgreSQLRemoteAdapter(pool=mock_pool)
        sample = await adapter.collect_metrics()
        assert sample is None  # silent skip

    async def test_connection_failure_does_not_raise(self, mock_pool):
        """대상 DB 연결 실패 시 시스템 전체에 영향 없음"""
        from asyncpg.exceptions import ConnectionDoesNotExistError
        mock_pool.fetchrow.side_effect = ConnectionDoesNotExistError()

        adapter = PostgreSQLRemoteAdapter(pool=mock_pool)
        sample = await adapter.collect_metrics()
        assert sample is None
```

### 4.4 Analyzers (AI/ML)

```python
# tests/unit/test_analyzers.py
from app.analyzers.baseline import BaselineLearner
from app.analyzers.anomaly import AnomalyDetector

class TestBaselineLearner:
    def test_stl_decomposition(self):
        """14일 CPU 데이터 → STL 분해 → 정상 범위 생성"""
        data = generate_seasonal_data(days=14, mean=50, amplitude=10)
        learner = BaselineLearner()
        baseline = learner.train(data, metric_type="cpu_usage")

        assert baseline.normal_min < 50
        assert baseline.normal_max > 50
        assert baseline.model_type == "stl"

    def test_insufficient_data_raises(self):
        """2주 미만 데이터 시 학습 거부"""
        data = generate_seasonal_data(days=3)
        learner = BaselineLearner()
        with pytest.raises(InsufficientDataError):
            learner.train(data, metric_type="cpu_usage")

class TestAnomalyDetector:
    def test_detects_spike(self):
        baseline = make_baseline(normal_min=30, normal_max=70)
        detector = AnomalyDetector()

        result = detector.detect(value=95.0, baseline=baseline)
        assert result.is_anomaly is True
        assert result.deviation > 0

    def test_normal_value_not_flagged(self):
        baseline = make_baseline(normal_min=30, normal_max=70)
        detector = AnomalyDetector()

        result = detector.detect(value=50.0, baseline=baseline)
        assert result.is_anomaly is False

    def test_edge_case_boundary_value(self):
        """경계값은 이상으로 판정하지 않음"""
        baseline = make_baseline(normal_min=30, normal_max=70)
        detector = AnomalyDetector()

        result = detector.detect(value=70.0, baseline=baseline)
        assert result.is_anomaly is False
```

### 4.5 Auth & Crypto

```python
# tests/unit/test_auth.py
from app.utils.auth import create_access_token, verify_token, hash_password, verify_password

class TestJWT:
    def test_create_and_verify_token(self):
        token = create_access_token(user_id="uuid-1", role="db_admin")
        payload = verify_token(token)
        assert payload["sub"] == "uuid-1"
        assert payload["role"] == "db_admin"

    def test_expired_token_raises(self):
        token = create_access_token(user_id="uuid-1", expires_minutes=-1)
        with pytest.raises(HTTPException) as exc:
            verify_token(token)
        assert exc.value.status_code == 401

    def test_invalid_token_raises(self):
        with pytest.raises(HTTPException):
            verify_token("garbage.token.here")

class TestPassword:
    def test_hash_and_verify(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True
        assert verify_password("wrong", hashed) is False

# tests/unit/test_crypto.py
from app.utils.crypto import encrypt_config, decrypt_config

class TestConfigEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        config = {"password": "secret123", "ssl_key": "/path/to/key"}
        encrypted = encrypt_config(config)
        decrypted = decrypt_config(encrypted)
        assert decrypted == config

    def test_encrypted_output_is_not_plaintext(self):
        config = {"password": "secret123"}
        encrypted = encrypt_config(config)
        assert "secret123" not in encrypted
```

### 4.6 Celery Tasks

```python
# tests/unit/test_tasks.py
from unittest.mock import patch, AsyncMock
from app.tasks.collect_metrics import collect_hot_metrics

class TestCollectHotMetrics:
    @patch("app.tasks.collect_metrics.get_adapter")
    @patch("app.tasks.collect_metrics.kafka_producer")
    def test_collects_and_publishes(self, mock_kafka, mock_get_adapter):
        mock_adapter = AsyncMock()
        mock_adapter.collect_metrics.return_value = make_metric_sample()
        mock_get_adapter.return_value = mock_adapter

        collect_hot_metrics("instance-uuid")

        mock_adapter.collect_metrics.assert_called_once()
        mock_kafka.send.assert_called_once_with(
            "neuraldb.metrics.hot",
            key="instance-uuid",
            value=pytest.approx(mock_adapter.collect_metrics.return_value, abs=1),
        )

    @patch("app.tasks.collect_metrics.get_adapter")
    def test_adapter_failure_does_not_raise(self, mock_get_adapter):
        """수집 실패 시 태스크는 실패하지 않음 (silent skip)"""
        mock_adapter = AsyncMock()
        mock_adapter.collect_metrics.return_value = None  # 수집 실패
        mock_get_adapter.return_value = mock_adapter

        # Should not raise
        collect_hot_metrics("instance-uuid")
```

---

## 5. API Route 테스트

```python
# tests/api/test_instances_api.py

class TestInstancesAPI:
    async def test_list_instances(self, client, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = [
            make_instance(name="pg-1"), make_instance(name="pg-2"),
        ]

        response = await client.get("/api/v1/instances")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 2

    async def test_create_instance(self, client, mock_db):
        response = await client.post("/api/v1/instances", json={
            "name": "pg-new", "db_type": "postgresql",
            "host": "10.0.1.1", "port": 5432,
            "database_name": "mydb", "environment": "production",
            "connection_config": {},
        })
        assert response.status_code == 201
        assert response.json()["name"] == "pg-new"

    async def test_create_instance_invalid_body(self, client):
        response = await client.post("/api/v1/instances", json={"name": ""})
        assert response.status_code == 422

    async def test_get_instance_not_found(self, client, mock_db):
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        response = await client.get("/api/v1/instances/nonexistent-uuid")
        assert response.status_code == 404

    async def test_viewer_cannot_create(self, client, mock_user_viewer):
        """Viewer 역할은 POST /instances 403"""
        app.dependency_overrides[get_current_user] = lambda: mock_user_viewer
        response = await client.post("/api/v1/instances", json={...})
        assert response.status_code == 403

# tests/api/test_system_api.py

class TestSystemAPI:
    async def test_health_check(self, client):
        response = await client.get("/api/v1/system/health")
        assert response.status_code == 200
        assert response.json()["status"] in ["healthy", "degraded", "down"]

    async def test_prometheus_metrics_endpoint(self, client):
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "fastapi" in response.text
```

---

## 6. Coverage 목표 (모듈별)

| 모듈 | Lines | Branches | 우선순위 |
|------|-------|----------|---------|
| `schemas/` | 95% | 90% | P0 — 입력 검증 |
| `services/` | 85% | 80% | P0 — 비즈니스 로직 |
| `api/v1/` | 80% | 75% | P0 — HTTP 핸들링 |
| `adapters/postgresql/` | 85% | 80% | P0 — 수집 핵심 |
| `analyzers/` | 80% | 75% | P0 — AI/ML 로직 |
| `utils/auth.py` | 95% | 90% | P0 — 보안 |
| `utils/crypto.py` | 95% | 90% | P0 — 보안 |
| `tasks/` | 75% | 70% | P0 — 비동기 작업 |
| `collectors/` | 80% | 75% | P0 — 수집 오케스트레이션 |
| `agents/` | 70% | 60% | P1 — Phase 2 본격 |
| `rag/` | 60% | 50% | P1 — Phase 2 |
| `mcp/` | 60% | 50% | P1 — Phase 3 |
| `middleware/` | 80% | 75% | P0 |

---

## 7. 실행 명령

```bash
cd backend

# 단위 테스트만 (외부 의존 없음, <30초)
uv run pytest tests/unit/ -v

# API 테스트 (mock service, <30초)
uv run pytest tests/api/ -v

# 전체 + Coverage
uv run pytest tests/unit/ tests/api/ --cov=app --cov-report=term-missing --cov-report=html

# 특정 모듈
uv run pytest tests/unit/test_adapters.py -v

# Watch 모드 (pytest-watch)
uv run ptw tests/unit/
```

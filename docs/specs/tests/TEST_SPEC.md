# Test Spec: NeuralDB MVP 통합/E2E 테스트 전략

> **Spec ID**: TEST-001
> **PRD 참조**: 9.1 Phase 1 MVP 인수 기준 (AC-1 ~ AC-13)
> **상태**: Approved
> **프레임워크**: pytest (Backend), Vitest (Frontend), Playwright (E2E)

---

## 0. 테스트 계층 문서 체계

| Layer | 문서 | 실행 환경 | 실행 시간 |
|-------|------|----------|----------|
| **Layer 1: FE Unit** | `FRONTEND_TEST_SPEC.md` | Vitest + MSW (BE 불필요) | <30s |
| **Layer 2: BE Unit** | `BACKEND_TEST_SPEC.md` | pytest + mock (DB/Kafka 불필요) | <30s |
| **Layer 3: Integration** | **이 문서** 섹션 2 | pytest + testcontainers (실제 DB/Kafka) | <3m |
| **Layer 4: E2E** | **이 문서** 섹션 2 (AC-7, AC-10) | Playwright (FE + BE 전체) | <5m |

> Layer 1~2는 **독립 실행** 가능 (상대 레이어 불필요).
> Layer 3~4는 **전체 스택** 필요 (DB + Kafka + BE + FE).

---

## 1. 테스트 피라미드

```
        ╱╲
       ╱ E2E ╲          Playwright (3~5 시나리오) → 이 문서
      ╱────────╲
     ╱Integration╲      pytest + testcontainers   → 이 문서
    ╱──────────────╲
   ╱ BE Unit ╱ FE Unit╲  pytest / Vitest          → 별도 문서
  ╱════════════════════╲
```

| Layer | Framework | Coverage Target | 실행 시간 | 문서 |
|-------|-----------|----------------|----------|------|
| FE Unit | Vitest + RTL + MSW | >80% line | <30s | `FRONTEND_TEST_SPEC.md` |
| BE Unit | pytest + mock | >80% line | <30s | `BACKEND_TEST_SPEC.md` |
| Integration | pytest + testcontainers | 모든 API 엔드포인트 | <3m | 이 문서 |
| E2E | Playwright | 핵심 플로우 5개 | <5m | 이 문서 |

---

## 2. MVP 인수 기준 → 테스트 매핑

### AC-1: PostgreSQL 10대 동시 수집 (누락률 <1%)

```python
# tests/integration/test_metric_collection.py

async def test_concurrent_10_instance_collection():
    """10개 PostgreSQL 인스턴스에서 1초 메트릭 동시 수집"""
    # Given: 10개 테스트 PostgreSQL 인스턴스 등록
    instances = [await create_test_instance(f"pg-test-{i}") for i in range(10)]

    # When: 60초간 수집 실행
    await run_collector_for(seconds=60)

    # Then: 각 인스턴스 60개 샘플 (누락률 <1% → 최소 59개)
    for inst in instances:
        count = await count_metric_samples(inst.id, last_seconds=60)
        assert count >= 59, f"{inst.name}: {count}/60 samples (누락률 {(60-count)/60*100:.1f}%)"
```

### AC-2: ASH 히트맵 실시간 표시

```python
# tests/integration/test_ash_collection.py

async def test_ash_sampling_and_heatmap():
    """1초 ASH 샘플링 → 히트맵 API 데이터 정합성"""
    # Given: 대상 DB에서 인위적 Lock 생성
    await create_artificial_lock(instance_id)

    # When: 10초 대기 후 히트맵 조회
    await asyncio.sleep(10)
    response = await client.get(f"/api/v1/instances/{instance_id}/ash/heatmap")

    # Then: Lock 카테고리에 0 이상의 값 존재
    data = response.json()["data"]
    lock_values = [d["Lock"] for d in data]
    assert any(v > 0 for v in lock_values)
```

### AC-3: AI 베이스라인 이상 탐지 (오탐률 <10%)

```python
# tests/integration/test_baseline_detection.py

async def test_anomaly_detection_accuracy():
    """정상 패턴 학습 후 이상 주입 → 탐지율 검증"""
    # Given: 2주치 정상 메트릭 시드 데이터 (CPU 40~60%)
    await seed_normal_metrics(instance_id, days=14, cpu_range=(40, 60))
    await trigger_baseline_training(instance_id)

    # When: 비정상 메트릭 주입 (CPU 95%)
    anomaly_samples = generate_anomaly_metrics(cpu=95.0, count=10)
    normal_samples = generate_normal_metrics(cpu=50.0, count=90)
    all_samples = anomaly_samples + normal_samples

    results = [await detect_anomaly(s) for s in all_samples]

    # Then: 이상 10개 중 9개 이상 탐지, 정상 90개 중 오탐 9개 이하
    true_positives = sum(1 for r, s in zip(results, all_samples) if r.is_anomaly and s.is_anomaly)
    false_positives = sum(1 for r, s in zip(results, all_samples) if r.is_anomaly and not s.is_anomaly)
    assert true_positives >= 9   # 탐지율 >= 90%
    assert false_positives <= 9  # 오탐률 <= 10%
```

### AC-4: Slack 알림 30초 이내 발송

```python
# tests/integration/test_alert_dispatch.py

async def test_slack_alert_within_30_seconds():
    """이상 탐지 → Slack 발송까지 30초 이내"""
    # Given: Slack webhook mock 서버
    mock_slack = await start_mock_webhook_server()
    await register_alert_channel("slack", mock_slack.url)

    # When: 인위적 이상 메트릭 주입
    start_time = time.monotonic()
    await inject_anomaly_metric(instance_id, cpu=99.0)

    # Then: mock 서버에 30초 이내 요청 도착
    received = await mock_slack.wait_for_request(timeout=30)
    elapsed = time.monotonic() - start_time
    assert received is not None
    assert elapsed < 30
    assert "CRITICAL" in received.body["text"]
```

### AC-5: NL2SQL 성공률 >80%

```python
# tests/integration/test_nl2sql.py

NL2SQL_TEST_CASES = [
    ("현재 가장 느린 쿼리 5개", "ORDER BY", True),
    ("활성 커넥션 수", "pg_stat_activity", True),
    ("오늘 발생한 인시던트", "incidents", True),
    ("CPU 사용률 추이", "cpu_usage", True),
    ("Lock 대기 중인 세션", "wait_event", True),
    ("테이블별 디스크 사용량", "pg_stat_user_tables", True),
    ("최근 1시간 TPS 평균", "tps", True),
    ("Replication Lag 상태", "pg_stat_replication", True),
    ("인덱스 사용률 낮은 테이블", "idx_scan", True),
    ("어제 대비 쿼리 실행 시간 변화", "mean_exec_time", True),
]

async def test_nl2sql_accuracy():
    """10개 자연어 질의 → SQL 변환 성공률 >80%"""
    success = 0
    for question, expected_keyword, _ in NL2SQL_TEST_CASES:
        response = await client.post("/api/v1/nl2sql/query", json={
            "question": question,
            "instance_id": instance_id,
            "execute": False,
        })
        sql = response.json()["generated_sql"]
        if expected_keyword.lower() in sql.lower():
            success += 1

    assert success >= 8, f"NL2SQL 성공률: {success}/10 ({success*10}%)"
```

### AC-6: RBAC 역할 기반 인가

```python
# tests/integration/test_rbac.py

@pytest.mark.parametrize("role,method,path,expected", [
    ("viewer", "GET", "/api/v1/instances", 200),
    ("viewer", "POST", "/api/v1/instances", 403),
    ("viewer", "DELETE", "/api/v1/instances/{id}", 403),
    ("operator", "GET", "/api/v1/instances", 200),
    ("operator", "PUT", "/api/v1/incidents/{id}/status", 200),
    ("operator", "DELETE", "/api/v1/instances/{id}", 403),
    ("db_admin", "POST", "/api/v1/instances", 200),
    ("db_admin", "DELETE", "/api/v1/users/{id}", 403),
    ("super_admin", "DELETE", "/api/v1/users/{id}", 200),
    ("api_user", "GET", "/api/v1/instances", 200),
    ("api_user", "POST", "/api/v1/users", 403),
])
async def test_rbac_permission(role, method, path, expected):
    token = await login_as(role)
    response = await client.request(method, path, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == expected
```

### AC-7: 대시보드 로딩 <3초, WebSocket <1초

```typescript
// tests/e2e/dashboard.spec.ts (Playwright)

test('dashboard loads within 3 seconds', async ({ page }) => {
  const start = Date.now();
  await page.goto('/dashboard');
  await page.waitForSelector('[data-testid="metric-card"]');
  const elapsed = Date.now() - start;
  expect(elapsed).toBeLessThan(3000);
});

test('websocket metric updates within 1 second', async ({ page }) => {
  await page.goto('/dashboard');
  const metricValue = page.locator('[data-testid="cpu-metric"]');
  const initial = await metricValue.textContent();

  // 1초 대기 후 값 변경 확인
  await page.waitForTimeout(1500);
  const updated = await metricValue.textContent();
  expect(updated).not.toBe(initial);
});
```

### AC-8: DDL 변경 감지

```python
# tests/integration/test_schema_tracking.py

async def test_ddl_change_detection():
    """대상 DB에서 DDL 실행 → schema_changes 테이블 기록 확인"""
    # When: 대상 DB에서 ALTER TABLE 실행
    await execute_on_target_db("ALTER TABLE orders ADD COLUMN tax_id VARCHAR(20)")

    # Then: 10초 이내 schema_changes에 기록
    await asyncio.sleep(10)
    changes = await client.get(f"/api/v1/instances/{instance_id}/schema-changes")
    assert len(changes.json()["items"]) > 0
    assert changes.json()["items"][0]["change_type"] == "ALTER"
    assert "tax_id" in changes.json()["items"][0]["ddl_command"]
```

### AC-9: 감사 로그 기록

```python
# tests/integration/test_audit_log.py

async def test_audit_log_on_state_change():
    """인스턴스 생성/수정/삭제 시 감사 로그 기록"""
    # When: 인스턴스 CRUD
    create_resp = await client.post("/api/v1/instances", json={...})
    instance_id = create_resp.json()["id"]
    await client.put(f"/api/v1/instances/{instance_id}", json={"name": "renamed"})
    await client.delete(f"/api/v1/instances/{instance_id}")

    # Then: 3건의 감사 로그
    logs = await client.get("/api/v1/audit-logs", params={"resource_id": instance_id})
    actions = [l["action"] for l in logs.json()["items"]]
    assert "create" in actions
    assert "update" in actions
    assert "delete" in actions
```

### AC-10: Docker Compose 한 줄 기동

```bash
# tests/e2e/test_docker_compose.sh

#!/bin/bash
set -e

cd infra/docker
docker compose up -d

# 60초 내 모든 서비스 healthy
for i in $(seq 1 60); do
  healthy=$(docker compose ps --format json | jq '[.[] | select(.Health == "healthy")] | length')
  total=$(docker compose ps --format json | jq 'length')
  if [ "$healthy" -eq "$total" ]; then
    echo "All $total services healthy in ${i}s"
    exit 0
  fi
  sleep 1
done

echo "FAIL: Not all services healthy after 60s"
docker compose ps
exit 1
```

### v3.3 신규 기능 테스트 시나리오

#### TS-RAG: 경량 RAG 테스트
| ID | 시나리오 | AC 참조 | 검증 방법 |
|----|---------|---------|----------|
| TS-RAG-001 | 인시던트 생성 시 pgvector 임베딩 자동 생성 | AC-13 | 인시던트 POST → 5초 후 rag_documents 행 존재 확인 |
| TS-RAG-002 | 유사 인시던트 검색 정확도 | AC-13 | 동일 유형 인시던트 3건 생성 → 검색 시 similarity ≥ 0.85 |
| TS-RAG-003 | 검색 성능 | AC-13 | 1000건 임베딩 상태에서 검색 < 200ms |

#### TS-MTL: MTL Lite 테스트
| ID | 시나리오 | AC 참조 | 검증 방법 |
|----|---------|---------|----------|
| TS-MTL-001 | MTL 4-Head 동시 응답 | AC-12 | POST /mtl/predict → anomaly_type, root_cause, severity, suggested_actions 4개 필드 모두 존재 |
| TS-MTL-002 | Confidence Score 범위 | AC-12 | 응답의 confidence가 0.0~1.0 범위 |
| TS-MTL-003 | Reasoning Chain 최소 단계 | AC-12 | reasoning_chain 배열 길이 ≥ 3 |
| TS-MTL-004 | LLM 실패 시 graceful degradation | AC-12 | LLM 타임아웃 시뮬레이션 → confidence: 0.0, anomaly_type: unknown |

#### TS-RCA: 경량 RCA 테스트
| ID | 시나리오 | AC 참조 | 검증 방법 |
|----|---------|---------|----------|
| TS-RCA-001 | 인시던트 → RCA 자동 생성 | AC-11 | 인시던트 생성 후 30초 이내 mtl_predictions 행 존재 |
| TS-RCA-002 | Confidence 기반 실행 차단 | AC-11 | confidence < 0.5인 예측 → 자동 실행 차단 확인 |
| TS-RCA-003 | 운영자 피드백 저장 | AC-11 | POST feedback → feedback_correct 필드 저장 확인 |

---

## 3. 테스트 인프라

### 3.1 테스트용 PostgreSQL

```python
# tests/conftest.py
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

@pytest_asyncio.fixture(scope="session")
async def test_db():
    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        yield postgres.get_connection_url()
```

### 3.2 테스트용 Kafka

```python
@pytest_asyncio.fixture(scope="session")
async def test_kafka():
    with KafkaContainer("confluentinc/cp-kafka:7.6.0") as kafka:
        yield kafka.get_bootstrap_server()
```

### 3.3 Mock 서비스

| Mock 대상 | 용도 | 라이브러리 |
|-----------|------|-----------|
| LLM API | NL2SQL 테스트 시 고정 응답 반환 | `responses` / `respx` |
| Slack Webhook | 알림 발송 검증 | `aiohttp` mock server |
| 대상 DB pg_stat_* | Adapter 단위 테스트 | SQLAlchemy in-memory fixtures |

---

## 4. CI 파이프라인

```yaml
# .woodpecker.yml
# Layer 1~2: 병렬 실행 (외부 의존 없음)
# Layer 3~4: 순차 실행 (인프라 필요)

pipeline:
  # ─── Layer 1: Frontend (독립) ───
  frontend-lint:
    image: node:22-slim
    commands:
      - cd frontend && npm ci && npm run lint

  frontend-unit:                          # FRONTEND_TEST_SPEC.md
    image: node:22-slim
    commands:
      - cd frontend && npm ci && npm run test -- --coverage
    depends_on: [frontend-lint]

  # ─── Layer 2: Backend (독립, 병렬) ───
  backend-lint:
    image: python:3.12-slim
    commands:
      - pip install uv && uv sync --dev
      - uv run ruff check .
      - uv run mypy app/

  backend-unit:                           # BACKEND_TEST_SPEC.md
    image: python:3.12-slim
    commands:
      - pip install uv && uv sync --dev
      - uv run pytest tests/unit/ tests/api/ -v --cov=app --cov-report=xml
    depends_on: [backend-lint]

  # ─── Layer 3: Integration (인프라 필요) ───
  backend-integration:                    # TEST_SPEC.md (이 문서)
    image: python:3.12-slim
    commands:
      - pip install uv && uv sync --dev
      - uv run pytest tests/integration/ -v
    services:
      - postgres:pgvector/pgvector:pg16
      - valkey:valkey/valkey:8-alpine
      - kafka:bitnami/kafka:3.8
    depends_on: [backend-unit]

  # ─── Layer 4: E2E (전체 스택) ───
  e2e:                                    # TEST_SPEC.md (이 문서)
    image: mcr.microsoft.com/playwright:v1.44.0
    commands:
      - cd frontend && npx playwright test
    depends_on: [frontend-unit, backend-integration]
```

### 실행 흐름

```
frontend-lint ──► frontend-unit ──────────────────┐
                                                   ├──► e2e
backend-lint  ──► backend-unit ──► backend-integration ─┘
```

> **Layer 1(FE)과 Layer 2(BE)는 완전 병렬.** 서로 기다리지 않음.
> **Layer 3(Integration)은 BE Unit 통과 후**, Layer 4(E2E)는 FE + Integration 모두 통과 후 실행.

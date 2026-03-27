# Feature Spec: System Health 모니터링

## 메타데이터
- **Spec ID**: FS-SELF-001
- **PRD 참조**: FR-SELF-001, FR-SELF-002, FR-SELF-003
- **우선순위**: P0 (MVP)
- **상태**: Implemented
- **구현 파일**:
  - Backend: `backend/app/api/v1/system.py` (기존 — 확장 필요)
  - Frontend: `frontend/src/components/dashboard/SystemHealth.tsx` (기존)

---

## 1. 개요

NeuralDB **자체 시스템**의 가용성과 성능을 모니터링합니다. 대상 DB 메트릭(자체 Adapter 수집)과 구분되는 **자체 인프라 헬스 체크**입니다.

> **대상 DB 메트릭** ≠ **자체 시스템 메트릭**
> - 대상 DB: Adapter → `metric_samples` 저장 (Prometheus 미사용)
> - 자체 시스템: OTel SDK → Prometheus `/metrics` 노출 + Health API

---

## 2. Health Check 대상

### 2.1 컴포넌트 상태 (MVP)

| 컴포넌트 | 체크 방법 | 정상 기준 | 영향도 |
|---------|----------|----------|--------|
| **PostgreSQL (시스템 DB)** | `SELECT 1` | 응답 < 1초 | Critical — DB 다운 시 전체 장애 |
| **Valkey** | `PING` | 응답 < 500ms | High — 캐시/Celery 브로커 불가 |
| **Celery Workers** | `inspect.ping()` | 1개 이상 응답 | High — 수집/분석 태스크 중단 |
| **FastAPI** | 자기 자신 | 요청 처리 가능 | Critical — API 불가 |

### 2.2 상세 메트릭 (Phase 2 — FR-SELF-004)

| 메트릭 | 소스 | Phase |
|--------|------|-------|
| FastAPI 요청 지연 P50/P95/P99 | prometheus-fastapi-instrumentator | Phase 2 |
| FastAPI 에러율 (4xx/5xx) | prometheus-fastapi-instrumentator | Phase 2 |
| Celery Worker 큐 깊이 | celery-exporter | Phase 2 |
| Celery 태스크 처리량/실패율 | celery-exporter | Phase 2 |
| Valkey 메모리 사용량/히트율 | redis_exporter | Phase 2 |
| 시스템 DB 커넥션 풀 사용률 | SQLAlchemy pool stats | Phase 2 |

---

## 3. API

### 3.1 Health Check (MVP — 기존 구현)

- **Method**: GET
- **Path**: `/api/v1/system/health`
- **Auth**: 불필요 (공개)
- **Response**:

```python
# Spec: FR-SELF-001
class HealthStatus(BaseModel):
    db: str           # "up" | "down"
    valkey: str       # "up" | "down"
    celery: str       # "up" | "down"
    status: str       # "healthy" | "degraded" | "unhealthy"
```

### 3.2 상세 Health (MVP 확장)

- **Method**: GET
- **Path**: `/api/v1/system/health/detail`
- **Auth**: JWT (Operator 이상)
- **Response**:

```python
# Spec: FR-SELF-001
class HealthDetail(BaseModel):
    status: str                     # healthy | degraded | unhealthy
    uptime_seconds: int             # FastAPI 프로세스 가동 시간
    version: str                    # NeuralDB 버전

    components: dict[str, ComponentHealth]

class ComponentHealth(BaseModel):
    status: str                     # up | down
    latency_ms: int | None         # 체크 소요 시간
    details: dict | None           # 컴포넌트별 상세 (pool_size, worker_count 등)
    last_checked_at: datetime
```

### 3.3 Prometheus 메트릭 (MVP — FR-SELF-002)

- **Path**: `/metrics`
- **Auth**: 불필요 (Prometheus scrape 대상)
- **구현**: `prometheus-fastapi-instrumentator` 자동 노출
- **노출 메트릭**:
  - `http_requests_total` (method, status, path)
  - `http_request_duration_seconds` (histogram)
  - `http_requests_in_progress`

---

## 4. 판정 로직

```python
# Spec: FR-SELF-001
def determine_overall_status(components: dict[str, str]) -> str:
    """컴포넌트 상태로 전체 시스템 상태 판정"""
    if components["db"] == "down":
        return "unhealthy"          # DB 다운 = 전체 장애
    if all(v == "up" for v in components.values()):
        return "healthy"            # 전부 정상
    return "degraded"               # 일부 장애 (Valkey/Celery)
```

### 심각도 매핑

| 전체 상태 | 의미 | 프론트엔드 표시 |
|----------|------|---------------|
| `healthy` | 모든 컴포넌트 정상 | 초록 뱃지 |
| `degraded` | 일부 장애 (비핵심) | 노란 뱃지 + 경고 |
| `unhealthy` | 핵심 컴포넌트 장애 | 빨간 뱃지 + 긴급 알림 |

---

## 5. Frontend 연동

### SystemHealth 컴포넌트 (기존)

`frontend/src/components/dashboard/SystemHealth.tsx`에서:
- `/api/v1/system/health` 30초 간격 폴링
- 컴포넌트별 up/down 표시
- 전체 status에 따른 색상 뱃지

---

## 6. 인수 기준 (Acceptance Criteria) — MVP

- [ ] **AC-1**: GET `/api/v1/system/health` 호출 시 DB/Valkey/Celery 상태 + 전체 status 반환
- [ ] **AC-2**: DB 다운 시 `status: "unhealthy"` 반환 (< 3초 응답)
- [ ] **AC-3**: Valkey 다운 시 `status: "degraded"` 반환
- [ ] **AC-4**: GET `/metrics`에서 Prometheus 형식 메트릭 노출
- [ ] **AC-5**: 프론트엔드 Dashboard에 SystemHealth 컴포넌트가 상태 배지 표시
- [ ] **AC-6**: GET `/api/v1/system/health/detail`에서 uptime, version, 컴포넌트별 latency 반환

---

## 7. 의존성

- **선행 Spec**: 없음 (독립적)
- **연동 Spec**: COMPONENT_SPEC (SystemHealth 프론트엔드), CELERY_TASKS_SPEC (Worker 상태 확인)
- **Phase 2 확장**: FR-SELF-004 (System Health 대시보드), FR-SELF-005 (자체 이상 탐지 알림)

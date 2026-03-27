# Feature Spec: Auto-Baselining & Anomaly Detection

## 메타데이터
- **Spec ID**: FS-AI-001
- **PRD 참조**: FR-AI-001, FR-ALERT-003
- **우선순위**: P0 (MVP)
- **상태**: Implemented (MVP)
- **선행 Spec**: DM-001 (ERD — `baselines`, `metric_samples`, `incidents`)
- **후행 Spec**: FS-AI-010 (MTL RCA — 이상 탐지 결과를 입력으로 사용)
- **구현 파일**:
  - Backend: `backend/app/analyzers/baseline.py`, `backend/app/analyzers/anomaly.py`
  - Tasks: `backend/app/tasks/analyze.py`
  - API: `backend/app/api/v1/baselines.py`
  - Schemas: `backend/app/schemas/baseline.py`
  - Test: `backend/tests/unit/test_baseline_analyzer.py`, `backend/tests/unit/test_anomaly_detector.py`

---

## 1. 개요

2주 이상 축적된 메트릭 데이터로 **시간대별 정상 패턴**을 학습하고, 실시간 메트릭을 베이스라인과 비교하여 **동적 이상 탐지**를 수행하는 시스템. 수동 임계값과 병행하여 2중 방어선을 구성합니다.

### 학습 파이프라인

```
2주 메트릭 축적 → STL 분해 (Trend / Seasonal / Residual)
  → Isolation Forest 학습 (contamination=0.05)
  → 시간대별 베이스라인 생성 (weekday_business / night / weekend)
  → Valkey에 캐싱 (실시간 비교용)
  → 6시간마다 재학습 (Celery Beat)
```

---

## 2. 인터페이스 계약

### 2.1 베이스라인 학습 API

#### 재학습 트리거
- **Method**: POST
- **Path**: `/api/v1/instances/{id}/baselines/retrain`
- **Auth**: JWT (DB Admin 이상)

#### 베이스라인 조회
- **Method**: GET
- **Path**: `/api/v1/instances/{id}/baselines`
- **Query**: `metric_type`, `time_bucket`
- **Response**:

```python
# Spec: FR-AI-001
class BaselineResponse(BaseModel):
    instance_id: UUID
    metric_type: str        # cpu_usage, connections, tps 등
    time_bucket: str        # weekday_business, weekday_night, weekend
    normal_min: float
    normal_max: float
    mean: float
    stddev: float
    model_type: str         # stl, isolation_forest
    last_trained_at: datetime
    training_samples: int
```

### 2.2 데이터 모델

`baselines` 테이블 (ERD DM-001 §2.10 참조):

| Column | Type | Description |
|--------|------|-------------|
| `instance_id` | UUID FK | 대상 인스턴스 |
| `metric_type` | VARCHAR(50) | 메트릭 유형 |
| `time_bucket` | VARCHAR(20) | 시간대 구분 |
| `normal_min/max` | FLOAT | 정상 범위 |
| `mean/stddev` | FLOAT | 통계 값 |
| `model_type` | VARCHAR(20) | stl / isolation_forest |
| `model_params` | JSONB | 모델 하이퍼파라미터 |
| `training_samples` | INTEGER | 학습 샘플 수 |
| `last_trained_at` | TIMESTAMPTZ | 마지막 학습 시각 |

---

## 3. 동작 규격

### 3.1 STL 분해 (Seasonal-Trend Decomposition)

```python
# Spec: FR-AI-001
from statsmodels.tsa.seasonal import STL

def train_baseline(metrics: pd.DataFrame, metric_type: str) -> Baseline:
    """2주 메트릭으로 시간대별 베이스라인 학습"""
    stl = STL(metrics[metric_type], period=86400)  # 1일 주기
    result = stl.fit()

    # 시간대별 분류
    for bucket in ["weekday_business", "weekday_night", "weekend"]:
        bucket_data = filter_by_time_bucket(result.resid, bucket)
        baseline = Baseline(
            metric_type=metric_type,
            time_bucket=bucket,
            mean=bucket_data.mean(),
            stddev=bucket_data.std(),
            normal_min=bucket_data.mean() - 2 * bucket_data.std(),
            normal_max=bucket_data.mean() + 2 * bucket_data.std(),
            model_type="stl",
        )
        await save_baseline(baseline)
```

### 3.2 Isolation Forest 이상 탐지

```python
# Spec: FR-AI-001, FR-ALERT-003
from sklearn.ensemble import IsolationForest

def detect_anomaly(
    sample: MetricSample,
    baseline: Baseline,
) -> bool:
    """실시간 메트릭을 베이스라인과 비교하여 이상 여부 판단"""

    # 1차: 통계적 범위 검사 (σ 기반)
    if sample.value < baseline.normal_min or sample.value > baseline.normal_max:
        # 2차: Isolation Forest 확인 (오탐 방지)
        clf = load_isolation_forest(baseline.instance_id, baseline.metric_type)
        prediction = clf.predict([[sample.value]])
        if prediction[0] == -1:  # anomaly
            return True

    return False
```

### 3.3 이상 탐지 → 인시던트 생성

```
이상 탐지
    → 심각도 판단 (deviation 크기 기반)
        > 3σ: CRITICAL
        > 2σ: WARNING
        > 1.5σ: NOTICE
    → incidents 테이블에 자동 생성
    → MTL Lite에 전달 (FS-AI-010)
    → Slack 알림 발송 (MVP-ALERT-001)
```

### 3.4 시간대 구분

| Time Bucket | 요일 | 시간 |
|-------------|------|------|
| `weekday_business` | 월~금 | 09:00~18:00 |
| `weekday_night` | 월~금 | 18:00~09:00 |
| `weekend` | 토~일 | 전 시간 |

### 3.5 재학습 스케줄

| 항목 | 값 |
|------|-----|
| 최소 학습 데이터 | 2주 (336시간) |
| 재학습 주기 | 6시간 (Celery Beat) |
| 캐시 | Valkey (TTL=6h) |
| Contamination | 0.05 (5% 이상치 허용) |

### 3.6 수동 임계값 병행

| 구분 | 역할 |
|------|------|
| AI 베이스라인 | 1차 방어선 — 동적 패턴 기반 탐지 |
| 수동 임계값 | 2차 안전망 — 절대 임계값 (CPU>95% 등) |

두 방식 모두 인시던트를 생성하며, `incidents.source` 필드로 구분:
- `ai_baseline`: AI 베이스라인에 의한 탐지
- `threshold`: 수동 임계값에 의한 탐지

---

## 4. 성능 요구사항

| 메트릭 | 목표 |
|--------|------|
| 베이스라인 학습 | < 30초 / 인스턴스 / 메트릭 유형 |
| 이상 탐지 판단 | < 100ms / 샘플 |
| 오탐률 (False Positive) | < 10% |
| 미탐률 (False Negative) | < 5% (CRITICAL 기준) |
| 캐시 적중률 | > 95% (Valkey) |

---

## 5. 인수 기준 (Acceptance Criteria)

- [ ] **AC-1**: 2주 메트릭 데이터로 시간대별 베이스라인이 자동 생성됨
- [ ] **AC-2**: GET `/api/v1/instances/{id}/baselines`에서 학습된 베이스라인 조회 가능
- [ ] **AC-3**: POST `/api/v1/instances/{id}/baselines/retrain`으로 수동 재학습 트리거 가능
- [ ] **AC-4**: 베이스라인 이탈 시 인시던트가 자동 생성되고 `source: "ai_baseline"` 기록
- [ ] **AC-5**: Celery Beat에 의해 6시간마다 자동 재학습 실행
- [ ] **AC-6**: Valkey에 베이스라인이 캐싱되어 실시간 비교 시 < 100ms 응답
- [ ] **AC-7**: 수동 임계값과 AI 베이스라인이 병행 동작하여 이중 방어선 구성

---

## 6. 의존성

- **선행 Spec**: DM-001 (ERD — `baselines`, `metric_samples`, `incidents` 테이블)
- **후행 Spec**: FS-AI-010 (MTL RCA — 이상 탐지로 생성된 인시던트를 진단)
- **연동 Spec**: MVP-ALERT-001 (Slack 알림), MVP-COLLECT-001 (Hot 메트릭 수집)

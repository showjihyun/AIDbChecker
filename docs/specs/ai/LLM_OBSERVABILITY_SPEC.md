# Feature Spec: LLM Observability (AI 파이프라인 자체 모니터링)

## 메타데이터
- **Spec ID**: FS-AI-013
- **PRD 참조**: FR-AI-013
- **우선순위**: P1 (Phase 2)
- **상태**: Implemented (Phase 2)
- **선행 Spec**: FS-AI-010 (MTL RCA), FS-AI-011 (Confidence Score)
- **참조**: OpenObserve + OpenLIT, 2026 AIOps Market Gap Analysis

---

## 1. 개요

대상 DB만 모니터링하는 것이 아니라, NeuralDB 내부의 **LLM/AI 파이프라인 자체**를 모니터링하는 메타 옵저버빌리티 레이어. 토큰 사용량, 응답 지연, RCA 정확도, 할루시네이션 비율, 모델 드리프트, API 비용을 추적합니다.

> **Phase 2에서 본격 구현**. MVP에서는 `tokens_used`, `inference_time_ms`를 `mtl_predictions` 테이블에 기록하는 수준만 구현.

---

## 2. 수집 메트릭

### 2.1 메트릭 정의

| 메트릭 | 수집 주기 | 저장 | 알림 기준 | 단위 |
|--------|----------|------|----------|------|
| **token_usage_input** | 매 LLM 호출 | `llm_metrics` | 일 예산 초과 | tokens |
| **token_usage_output** | 매 LLM 호출 | `llm_metrics` | 일 예산 초과 | tokens |
| **response_latency** | 매 LLM 호출 | `llm_metrics` | P95 > 10초 | ms |
| **rca_accuracy** | 피드백 수신 시 | `llm_metrics` | 주간 < 70% | % |
| **hallucination_rate** | 매 RCA 결과 | `llm_metrics` | > 15% | % |
| **model_drift** | 1시간 | `model_drift_metrics` | KL-div > 임계값 | float |
| **api_cost** | 매 LLM 호출 | `llm_metrics` | 월 예산 80% | USD |
| **error_rate** | 매 LLM 호출 | `llm_metrics` | > 5% | % |

### 2.2 파생 메트릭

| 파생 메트릭 | 계산 | 주기 |
|-----------|------|------|
| daily_token_total | SUM(input + output) per day | 1일 |
| weekly_accuracy | correct / total feedback | 1주 |
| monthly_cost | SUM(api_cost) per month | 1월 |
| avg_confidence_trend | AVG(confidence) 7일 이동평균 | 1일 |

---

## 3. 인터페이스 계약

### 3.1 API 엔드포인트

#### LLM 메트릭 요약 조회
- **Method**: GET
- **Path**: `/api/v1/llm-observability/summary`
- **Auth**: JWT (Super Admin / DB Admin)
- **Query Params**: `from`, `to`, `model_version`, `agent_type`
- **Response**:

```python
# Spec: FR-AI-013
class LLMObservabilitySummary(BaseModel):
    period: str
    total_calls: int
    total_tokens: int  # input + output
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    accuracy_rate: float | None  # 피드백 기반
    hallucination_rate: float
    error_rate: float
    estimated_cost_usd: float
    model_breakdown: list[ModelUsage]

class ModelUsage(BaseModel):
    model: str  # "gpt-4o" | "mistral:7b"
    calls: int
    tokens: int
    avg_latency_ms: float
    cost_usd: float
```

#### LLM 메트릭 시계열 조회
- **Method**: GET
- **Path**: `/api/v1/llm-observability/timeseries`
- **Query Params**: `metric`, `from`, `to`, `interval` (1h/1d)
- **Response**: 시계열 데이터 (ECharts 호환)

#### 할루시네이션 로그 조회
- **Method**: GET
- **Path**: `/api/v1/llm-observability/hallucinations`
- **Query Params**: `from`, `to`, `limit`

#### 비용 예산 설정
- **Method**: PUT
- **Path**: `/api/v1/llm-observability/budget`
- **Auth**: JWT (Super Admin)
- **Request**:

```python
class LLMBudgetRequest(BaseModel):
    daily_token_limit: int = 500_000
    monthly_cost_limit_usd: float = 500.0
    offline_fallback_at_percent: int = 80  # 예산 80% 시 Offline 전환
```

### 3.2 데이터 모델

#### `llm_metrics` 테이블

```sql
-- Spec: FR-AI-013
CREATE TABLE llm_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type      VARCHAR(30) NOT NULL,
    -- 'monitoring' | 'diagnosis' | 'remediation' | 'reporting' | 'copilot'
    operation       VARCHAR(30) NOT NULL,
    -- 'mtl_predict' | 'nl2sql' | 'explain_plan' | 'generate_report' | 'tot_branch'

    model           VARCHAR(50) NOT NULL,  -- 'gpt-4o' | 'mistral:7b' | 'mtl-transformer-v2'
    model_provider  VARCHAR(20) NOT NULL,  -- 'openai' | 'ollama' | 'local'

    tokens_input    INT NOT NULL,
    tokens_output   INT NOT NULL,
    latency_ms      INT NOT NULL,

    -- 비용 (Cloud LLM만)
    cost_usd        FLOAT,  -- 토큰 단가 × 사용량

    -- 품질
    confidence_score FLOAT,  -- 이 호출의 Confidence Score
    has_hallucination BOOLEAN DEFAULT FALSE,
    hallucination_type VARCHAR(30),  -- 'no_evidence' | 'contradicts_data' | 'fabricated_entity'

    -- 에러
    is_error        BOOLEAN DEFAULT FALSE,
    error_type      VARCHAR(30),  -- 'timeout' | 'invalid_json' | 'rate_limit' | 'model_error'

    -- 컨텍스트
    incident_id     UUID REFERENCES incidents(id),
    instance_id     UUID REFERENCES db_instances(id),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- 일별 파티션 (pg_partman)
SELECT create_parent('public.llm_metrics', 'created_at', 'native', 'daily');

CREATE INDEX idx_llm_metrics_agent ON llm_metrics(agent_type);
CREATE INDEX idx_llm_metrics_model ON llm_metrics(model);
CREATE INDEX idx_llm_metrics_created ON llm_metrics(created_at);
```

#### `model_drift_metrics` 테이블

```sql
-- Spec: FR-AI-013
CREATE TABLE model_drift_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_version   VARCHAR(30) NOT NULL,
    metric_name     VARCHAR(50) NOT NULL,
    -- 'anomaly_type_distribution' | 'severity_distribution' | 'confidence_distribution'

    baseline_distribution JSONB NOT NULL,  -- 학습 시점 분포
    current_distribution  JSONB NOT NULL,  -- 현재 분포
    kl_divergence   FLOAT NOT NULL,        -- KL-divergence
    is_drifted      BOOLEAN NOT NULL,      -- 임계값 초과 여부
    threshold       FLOAT NOT NULL DEFAULT 0.3,

    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_model_drift_checked ON model_drift_metrics(checked_at);
```

---

## 4. 수집 구현

### 4.1 OpenLIT 자동 계측

```python
# Spec: FR-AI-013
# backend/app/middleware/llm_observability.py

import openlit

# FastAPI 시작 시 초기화
openlit.init(
    otlp_endpoint="http://localhost:4318",  # OTel Collector
    application_name="neuraldb",
    collect_gpu_stats=False,  # MVP: CPU only
)

# OpenLIT가 자동으로 계측하는 항목:
# - LangChain 호출 (토큰, 지연)
# - OpenAI API 호출
# - Ollama 호출
# → Prometheus /metrics로 자동 노출
```

### 4.2 할루시네이션 탐지

```python
# Spec: FR-AI-013
def detect_hallucination(
    prediction: MTLPredictResponse,
    rag_results: list[RAGSearchResult],
    metrics_snapshot: dict
) -> tuple[bool, str | None]:
    """RAG 근거 및 실제 메트릭과 LLM 출력 비교"""

    # 1. 존재하지 않는 엔티티 참조 확인
    if prediction.root_cause_detail:
        table = prediction.root_cause_detail.get("identifier", "")
        if table and not table_exists(table):
            return True, "fabricated_entity"

    # 2. 메트릭 수치 불일치 확인
    # (LLM이 "CPU 95%"라고 했는데 실제 50%인 경우)
    for step in prediction.reasoning_chain:
        if contains_metric_claim(step):
            if not verify_metric_claim(step, metrics_snapshot):
                return True, "contradicts_data"

    # 3. RAG 근거 없이 확신적 결론
    if prediction.confidence > 0.8 and not rag_results:
        # 과거 사례 없이 높은 확신 → 의심
        return True, "no_evidence"

    return False, None
```

### 4.3 비용 추적

```python
# Spec: FR-AI-013
# 모델별 토큰 단가 (2026년 기준)
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "claude-sonnet-4-6": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
    "mistral:7b": {"input": 0, "output": 0},  # 로컬, 비용 0
    "qwen2.5:14b": {"input": 0, "output": 0},
}

def calculate_cost(model: str, tokens_input: int, tokens_output: int) -> float:
    pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
    return tokens_input * pricing["input"] + tokens_output * pricing["output"]
```

---

## 5. 자동 조치

| 조건 | 자동 조치 |
|------|----------|
| 일일 토큰 예산 초과 | Offline LLM 자동 전환 + 관리자 알림 |
| 월 비용 예산 80% | 경고 알림 + Offline 전환 권고 |
| P95 지연 > 10초 (1시간 지속) | 모델 다운그레이드 권고 (4o→4o-mini) |
| 주간 정확도 < 70% | 재학습 트리거 (Phase 3 MTL) + 관리자 알림 |
| 할루시네이션 > 15% | RAG 파이프라인 점검 알림 + Confidence 가중치 하향 |
| 모델 드리프트 감지 | 재학습 트리거 + 관리자 알림 |
| 에러율 > 5% (1시간) | LLM provider 헬스 체크 + 폴백 전환 |

---

## 6. UI — AI Health 대시보드 탭

```
┌─ AI Health ──────────────────────────────────────────────┐
│                                                           │
│  ┌─ 토큰 사용량 ──────┐  ┌─ 응답 지연 ──────────────────┐ │
│  │ Today: 42,305      │  │ P50: 1.2s  P95: 4.8s       │ │
│  │ Budget: 500,000    │  │ P99: 8.3s                    │ │
│  │ ████░░░░ 8.4%      │  │ [시계열 차트]                 │ │
│  └────────────────────┘  └──────────────────────────────┘ │
│                                                           │
│  ┌─ 정확도 ───────────┐  ┌─ 할루시네이션 ────────────────┐ │
│  │ This Week: 84.2%   │  │ Rate: 3.2%                   │ │
│  │ [📈 트렌드 차트]    │  │ [최근 탐지 목록]              │ │
│  └────────────────────┘  └──────────────────────────────┘ │
│                                                           │
│  ┌─ 모델별 사용 현황 ───────────────────────────────────┐  │
│  │ Model        │ Calls │ Tokens  │ Latency │ Cost     │  │
│  │ gpt-4o       │  142  │ 38,200  │ 3.2s    │ $0.48    │  │
│  │ mistral:7b   │  891  │ 124,500 │ 1.8s    │ $0.00    │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

---

## 7. 인수 기준 (Acceptance Criteria)

- [ ] **AC-1**: 모든 LLM 호출에 대해 `llm_metrics`에 토큰/지연/비용이 자동 기록
- [ ] **AC-2**: GET `/api/v1/llm-observability/summary`에서 기간별 집계 조회 가능
- [ ] **AC-3**: 할루시네이션 탐지 시 `has_hallucination: true` 플래그 저장
- [ ] **AC-4**: 일일 토큰 예산 초과 시 Offline LLM 자동 전환 동작
- [ ] **AC-5**: 주간 정확도 < 70% 시 관리자 알림 발송
- [ ] **AC-6**: AI Health 대시보드 탭에서 모든 메트릭 실시간 시각화
- [ ] **AC-7**: 모델 드리프트 감지 시 `model_drift_metrics` 기록 + 알림

---

## 8. 의존성

- **선행 Spec**: FS-AI-010 (MTL 호출 메트릭), FS-AI-011 (Confidence Score)
- **사용 Spec**: FR-SELF-001~005 (System Health 대시보드와 통합)

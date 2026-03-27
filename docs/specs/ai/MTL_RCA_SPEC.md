# Feature Spec: MTL 기반 통합 RCA (Multi-Task Learning)

## 메타데이터
- **Spec ID**: FS-AI-010
- **PRD 참조**: FR-AI-010, FR-AI-014
- **우선순위**: P0 (MVP)
- **상태**: Implemented (MVP)
- **선행 Spec**: FS-AI-001 (Auto-Baselining), DM-001 (ERD)
- **사용 Spec**: FS-AI-011 (Confidence Score), FS-AI-RAG-001 (Lightweight RAG)
- **구현 파일**:
  - Backend: `backend/app/services/mtl_lite.py`, `backend/app/api/v1/mtl.py`
  - Test: `backend/tests/unit/test_ai_010_spec.py`

---

## 1. 개요

하나의 Shared Encoder가 DB 메트릭/로그/쿼리/ASH 데이터를 통합 표현으로 인코딩하고, 4개의 Task Head가 **이상 분류 / 근본 원인 식별 / 심각도 평가 / 액션 추천**을 단일 추론에서 동시에 수행하는 Multi-Task Learning RCA 시스템.

### 단계적 구현

| Phase | 구현 방식 | 모델 |
|-------|----------|------|
| **Phase 1 (MVP)** | MTL Lite — LLM Few-shot Prompting | GPT-4o / Mistral:7b |
| Phase 2 | Transformer Encoder Fine-tuning | PyTorch custom model |
| Phase 3 | Full MTL + Continual Learning | PyTorch + online learning |

---

## 2. 인터페이스 계약

### 2.1 API 엔드포인트

#### MTL 추론 실행
- **Method**: POST
- **Path**: `/api/v1/mtl/predict`
- **Auth**: JWT (DB Admin / Operator 이상)
- **Request Schema**:

```python
# Spec: FR-AI-010
class MTLPredictRequest(BaseModel):
    incident_id: UUID
    instance_id: UUID
    include_reasoning: bool = True  # Reasoning Chain 포함 여부
```

- **Response Schema**:

```python
# Spec: FR-AI-010, FR-AI-011
class MTLPredictResponse(BaseModel):
    prediction_id: UUID
    incident_id: UUID
    timestamp: datetime

    # Head 1: 이상 분류
    anomaly_type: AnomalyType  # enum
    anomaly_confidence: float  # 0.0~1.0

    # Head 2: 근본 원인
    root_cause: str  # 자연어 설명
    root_cause_detail: RootCauseDetail  # 구조화된 원인
    root_cause_confidence: float

    # Head 3: 심각도
    severity: SeverityLevel  # CRITICAL / WARNING / NOTICE / INFO
    severity_score: float  # 0.0~1.0

    # Head 4: 액션 추천
    suggested_actions: list[SuggestedAction]  # max 3개

    # Explainable AI (FS-AI-011)
    confidence: float  # 종합 Confidence Score
    reasoning_chain: list[str]  # 추론 단계
    evidence_links: list[str]  # 근거 데이터 API 링크

    # 메타
    model_version: str  # "mtl-lite-v1" | "mtl-transformer-v2"
    inference_time_ms: int
    tokens_used: int | None  # LLM 사용 시
```

#### MTL 예측 이력 조회
- **Method**: GET
- **Path**: `/api/v1/mtl/predictions`
- **Query Params**: `instance_id`, `from`, `to`, `min_confidence`, `limit`

#### MTL 피드백 제출 (운영자)
- **Method**: POST
- **Path**: `/api/v1/mtl/predictions/{prediction_id}/feedback`
- **Request Schema**:

```python
class MTLFeedbackRequest(BaseModel):
    is_correct: bool  # 👍/👎
    correct_anomaly_type: AnomalyType | None  # 오답 시 정답
    correct_root_cause: str | None
    notes: str | None
```

- **Error Codes**: 400 (잘못된 입력), 401, 403, 404 (인시던트 없음), 500, 503 (LLM 불가)

### 2.2 데이터 모델

#### `mtl_predictions` 테이블

```sql
-- Spec: FR-AI-010
CREATE TABLE mtl_predictions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID NOT NULL REFERENCES incidents(id),
    instance_id     UUID NOT NULL REFERENCES db_instances(id),

    -- Head 1: 이상 분류
    anomaly_type    VARCHAR(50) NOT NULL,
    anomaly_confidence FLOAT NOT NULL CHECK (anomaly_confidence BETWEEN 0 AND 1),

    -- Head 2: 근본 원인
    root_cause      TEXT NOT NULL,
    root_cause_detail JSONB,  -- {"query_id": "...", "table": "...", "index": "..."}

    -- Head 3: 심각도
    severity        VARCHAR(10) NOT NULL,  -- CRITICAL/WARNING/NOTICE/INFO
    severity_score  FLOAT NOT NULL CHECK (severity_score BETWEEN 0 AND 1),

    -- Head 4: 액션 추천
    suggested_actions JSONB NOT NULL DEFAULT '[]',
    -- [{"action": "CREATE INDEX ...", "confidence": 0.91, "risk": "LOW"}]

    -- Explainable AI
    confidence      FLOAT NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    reasoning_chain JSONB NOT NULL DEFAULT '[]',  -- ["Step 1: ...", ...]
    evidence_links  JSONB NOT NULL DEFAULT '[]',  -- ["/api/v1/..."]

    -- 메타
    model_version   VARCHAR(30) NOT NULL,
    inference_time_ms INT,
    tokens_used     INT,
    prompt_hash     VARCHAR(64),  -- 프롬프트 변경 추적용

    -- 피드백
    feedback_correct BOOLEAN,
    feedback_notes   TEXT,
    feedback_at      TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_mtl_predictions_incident ON mtl_predictions(incident_id);
CREATE INDEX idx_mtl_predictions_instance ON mtl_predictions(instance_id);
CREATE INDEX idx_mtl_predictions_confidence ON mtl_predictions(confidence);
CREATE INDEX idx_mtl_predictions_created ON mtl_predictions(created_at);
```

### 2.3 Enum 정의

```python
# Spec: FR-AI-010
class AnomalyType(str, Enum):
    QUERY_PERFORMANCE = "query_performance_degradation"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    LOCK_CONTENTION = "lock_contention"
    REPLICATION_LAG = "replication_lag"
    CONNECTION_SATURATION = "connection_saturation"
    VACUUM_BLOAT = "vacuum_bloat"
    SCHEMA_REGRESSION = "schema_regression"
    SECURITY_ANOMALY = "security_anomaly"
    UNKNOWN = "unknown"

class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    NOTICE = "NOTICE"
    INFO = "INFO"

class ActionRisk(str, Enum):
    LOW = "LOW"        # 읽기 전용, 영향 없음
    MEDIUM = "MEDIUM"  # 설정 변경, 인덱스 생성
    HIGH = "HIGH"      # DDL, 세션 킬, 파라미터 변경
    CRITICAL = "CRITICAL"  # 데이터 변경, 페일오버
```

---

## 3. MTL Lite 구현 사양 (Phase 1 / MVP)

### 3.1 프롬프트 템플릿

```python
# Spec: FR-AI-010
# backend/app/agents/diagnosis/mtl_prompt.py

MTL_SYSTEM_PROMPT = """You are NeuralDB's Multi-Task RCA engine.
Given a database incident context, you MUST respond with a JSON object
containing ALL of the following fields simultaneously.

IMPORTANT:
- Be specific about root causes (name exact queries, tables, indexes)
- Confidence scores must reflect actual certainty (don't inflate)
- Reasoning chain must show step-by-step logic
- Suggested actions must be executable SQL or config changes
"""

MTL_USER_PROMPT = """## Incident Context

### Current Metrics (last 5 minutes)
{metrics_snapshot}

### Active Sessions (ASH)
{ash_summary}

### Top Queries (pg_stat_statements)
{top_queries}

### Wait Events
{wait_events}

### Similar Past Incidents (RAG, Top-3)
{rag_results}

### Recent Schema Changes
{schema_changes}

---

Respond ONLY with valid JSON:
{{
  "anomaly_type": "<one of: query_performance_degradation, resource_exhaustion, lock_contention, replication_lag, connection_saturation, vacuum_bloat, schema_regression, security_anomaly, unknown>",
  "root_cause": "<specific root cause in natural language>",
  "root_cause_detail": {{
    "component": "<query|table|index|parameter|connection|replication>",
    "identifier": "<specific query hash / table name / param name>",
    "evidence": "<key metric or log entry>"
  }},
  "severity": "<CRITICAL|WARNING|NOTICE|INFO>",
  "severity_score": <0.0-1.0>,
  "suggested_actions": [
    {{
      "action": "<executable SQL or config command>",
      "description": "<what this does and why>",
      "confidence": <0.0-1.0>,
      "risk": "<LOW|MEDIUM|HIGH|CRITICAL>"
    }}
  ],
  "confidence": <0.0-1.0>,
  "reasoning_chain": [
    "Step 1: <observation>",
    "Step 2: <hypothesis>",
    "Step 3: <evidence>",
    "Step 4: <conclusion>"
  ]
}}"""
```

### 3.2 Context Builder 상세

각 프롬프트 변수의 포맷을 정의합니다.

#### `{metrics_snapshot}` (최대 800 토큰)
```text
=== Current Metrics (last 5 min avg) ===
CPU Usage: 95.2% (baseline: 40-60%)
Memory Usage: 72.1% (baseline: 65-75%)
Active Connections: 42/100 (baseline: 20-35)
TPS: 1240 (baseline: 800-1200)
Buffer Hit Ratio: 99.2% (baseline: 99.0-99.9%)
Disk I/O Read: 45 MB/s (baseline: 10-20 MB/s)
WAL Generation: 12 MB/s (baseline: 5-8 MB/s)
```
**구성**: MetricService.get_latest() → 베이스라인 대비 포맷

#### `{ash_summary}` (최대 600 토큰)
```text
=== Active Sessions (top 5 by duration) ===
PID 8829 | State: active | Wait: LWLock/buffer_mapping | Duration: 12.3s
  Query: SELECT * FROM orders WHERE created_at > '2026-03-20'...
PID 9012 | State: active | Wait: Lock/relation | Duration: 8.7s
  Query: UPDATE inventory SET quantity = quantity - 1 WHERE...
...

=== Wait Event Breakdown ===
Lock: 45% (1234 samples) | I/O: 30% (823) | CPU: 25% (675)
```
**구성**: ASHService.get_sessions(top=5) + ASHService.get_wait_breakdown()

#### `{top_queries}` (최대 800 토큰)
```text
=== Top 5 Slow Queries (pg_stat_statements) ===
#1 QueryHash: 1234567890 | Avg: 12.8s | Calls: 452 | Total: 5785.6s
   SELECT * FROM orders WHERE created_at > $1 AND status = $2
#2 QueryHash: 9876543210 | Avg: 3.2s | Calls: 1203 | Total: 3849.6s
   UPDATE inventory SET quantity = quantity - $1 WHERE product_id = $2
...
```
**구성**: pg_stat_statements TOP 5 by mean_exec_time

#### `{wait_events}` (최대 400 토큰)
```text
=== Wait Event Detail (last 5 min) ===
LWLock/buffer_mapping: 234 events (spike at 14:32:01)
Lock/relation: 189 events (sustained)
IO/DataFileRead: 156 events (normal)
```

#### `{rag_results}` (최대 800 토큰)
**구성**: RAGService.search_similar() → LIGHTWEIGHT_RAG_SPEC.md §3.3 format_rag_for_mtl()

#### `{schema_changes}` (최대 300 토큰)
```text
=== Schema Changes (last 24h) ===
[2026-03-21 10:15:00] ALTER TABLE orders ADD COLUMN discount DECIMAL(5,2)
[2026-03-21 10:16:00] CREATE INDEX idx_orders_discount ON orders(discount)
(none if no changes)
```

### 토큰 초과 시 트리밍 우선순위
1. schema_changes (없으면 0 토큰)
2. wait_events (요약으로 축소)
3. rag_results (Top-3 → Top-1)
4. top_queries (Top-5 → Top-3)
5. ash_summary (Top-5 → Top-3)
6. metrics_snapshot (절대 축소 안함)

### 3.3 종합 Confidence Score 계산

```python
# Spec: FR-AI-010, FR-AI-011
def compute_overall_confidence(prediction: dict) -> float:
    """4개 Head의 개별 신뢰도를 가중 평균하여 종합 Score 산출"""
    weights = {
        "anomaly_confidence": 0.25,   # 이상 유형 분류
        "root_cause_confidence": 0.35, # 근본 원인 (가장 중요)
        "severity_accuracy": 0.15,     # 심각도 평가
        "action_confidence": 0.25,     # 액션 추천
    }

    # 액션 Confidence = 추천 액션들의 평균
    action_conf = mean([a["confidence"] for a in prediction["suggested_actions"]]) \
                  if prediction["suggested_actions"] else 0.0

    overall = (
        weights["anomaly_confidence"] * prediction.get("anomaly_confidence", 0) +
        weights["root_cause_confidence"] * prediction.get("root_cause_confidence", 0) +
        weights["severity_accuracy"] * prediction.get("severity_score", 0) +
        weights["action_confidence"] * action_conf
    )
    return round(min(max(overall, 0.0), 1.0), 3)
```

### 3.4 Evidence Links 생성

```python
# Spec: FR-AI-010
def build_evidence_links(instance_id: UUID, incident: Incident) -> list[str]:
    """인시던트와 관련된 메트릭/ASH/쿼리 데이터 링크 생성"""
    base = f"/api/v1/instances/{instance_id}"
    time_range = f"from={incident.detected_at - 5min}&to={incident.detected_at + 5min}"
    return [
        f"{base}/metrics?{time_range}",
        f"{base}/ash?{time_range}",
        f"{base}/ash/wait-breakdown?{time_range}",
        f"/api/v1/incidents/{incident.id}",
    ]
```

### 3.5 LLM 모델 선택 로직

```python
# Spec: FS-AI-010
def select_llm_model(settings: Settings) -> LLMClient:
    if settings.LLM_MODE == "online":
        if settings.OPENAI_API_KEY:
            return OpenAIClient(model=settings.OPENAI_MODEL, temperature=settings.OPENAI_TEMPERATURE)
        elif settings.ANTHROPIC_API_KEY:
            return AnthropicClient(model=settings.ANTHROPIC_MODEL)
        else:
            raise NeuralDBError("AI_LLM_UNAVAILABLE", "No API key configured", 503)
    elif settings.LLM_MODE == "offline":
        return OllamaClient(host=settings.OLLAMA_HOST, model=settings.OLLAMA_MODEL)
    else:  # "auto"
        try:
            return OpenAIClient(...)  # online 먼저 시도
        except Exception:
            return OllamaClient(...)  # 실패 시 offline 폴백
```

### 3.6 JSON 파싱 에러 기본값

```python
MTL_FALLBACK_RESPONSE = {
    "anomaly_type": "unknown",
    "root_cause": "AI analysis failed. Manual investigation required.",
    "root_cause_detail": None,
    "severity": "NOTICE",
    "severity_score": 0.5,
    "suggested_actions": [],
    "confidence": 0.0,
    "reasoning_chain": ["AI analysis was unable to complete. Please review manually."],
}
```

---

## 4. 동작 규격

### 4.1 정상 시나리오

1. Monitoring Agent가 이상 탐지 → `incidents` 테이블에 인시던트 생성
2. MTL 서비스가 인시던트를 수신하여 Context Builder로 컨텍스트 구성
3. Lightweight RAG로 유사 과거 사례 Top-3 검색 (FS-AI-RAG-001)
4. LLM에 MTL 프롬프트 전송 → JSON 응답 수신
5. JSON 파싱 + Confidence Score 계산
6. `mtl_predictions` 테이블에 저장
7. Confidence Score에 따라 후속 처리:
   - ≥ 0.8: Autonomy Level에 따라 자동 실행 가능
   - 0.5~0.8: 관리자 확인 필수 알림
   - < 0.5: 추천만 표시, 실행 차단
8. 대시보드에 결과 WebSocket 푸시 (`incident:rca_complete`)

### 4.2 예외 시나리오

| 시나리오 | 처리 |
|---------|------|
| LLM 응답이 유효하지 않은 JSON | 최대 2회 재시도 → 실패 시 `confidence: 0.0` + `anomaly_type: unknown` |
| LLM 타임아웃 (>30초) | Offline LLM 폴백 시도 → 실패 시 수동 분석 알림 |
| RAG 검색 결과 0건 | `rag_results: "No similar past incidents found"` → LLM이 메트릭만으로 분석 |
| Confidence Score < 0.3 | 인시던트에 `needs_manual_review` 플래그 설정 + 관리자 알림 |
| LLM 할루시네이션 의심 | RAG 근거와 LLM 출력 비교 → 불일치 시 `hallucination_flag: true` |

### 4.3 경계 조건

- 동시 다발 인시던트 (5건+): Celery 큐로 순차 처리, 우선순위는 severity 기준
- LLM API 비용 제한: 일일 토큰 예산 초과 시 Offline LLM 자동 전환
- 컨텍스트 토큰 초과: CONTEXT_TOKEN_BUDGET에 따라 자동 트리밍

---

## 5. 인수 기준 (Acceptance Criteria)

- [ ] **AC-1**: POST `/api/v1/mtl/predict` 호출 시 4개 Head 결과가 포함된 JSON이 반환됨
- [ ] **AC-2**: 종합 Confidence Score가 0.0~1.0 범위이며 가중 평균 공식에 부합
- [ ] **AC-3**: Reasoning Chain이 최소 3단계 이상의 논리적 추론 과정을 포함
- [ ] **AC-4**: Evidence Links가 유효한 API 엔드포인트를 가리키며 접근 가능
- [ ] **AC-5**: LLM 응답 실패 시 2회 재시도 후 graceful degradation (unknown + 0.0)
- [ ] **AC-6**: RAG 검색 결과가 프롬프트에 포함되어 RCA 정확도 향상에 기여
- [ ] **AC-7**: 운영자 피드백(👍/👎) 저장 및 주간 정확도 집계 가능
- [ ] **AC-8**: 인시던트 발생부터 MTL 예측 완료까지 30초 이내 (Cloud LLM 기준)
- [ ] **AC-9**: `mtl_predictions` 테이블에 모든 필드가 정상 저장

---

## 6. 의존성

- **선행 Spec**: FS-AI-001 (이상 탐지가 인시던트를 생성해야 MTL 트리거)
- **사용 Spec**: FS-AI-011 (Confidence Score 정책), FS-AI-RAG-001 (RAG 검색)
- **후행 Spec**: FS-AUTO-001 (Self-Healing이 MTL 결과를 소비)

# Feature Spec: Explainable AI — Confidence Score & Reasoning Chain

## 메타데이터
- **Spec ID**: FS-AI-011
- **PRD 참조**: FR-AI-011, FR-AI-014
- **우선순위**: P0 (MVP)
- **상태**: Implemented (MVP)
- **선행 Spec**: FS-AI-010 (MTL RCA)
- **사용 Spec**: FS-AUTO-002 (Adaptive Autonomy)

---

## 1. 개요

모든 AI 판단(MTL RCA, NL2SQL, Auto-Tuning, Playbook 추천)에 **Confidence Score(0.0~1.0)** + **Reasoning Chain** + **Evidence Links**를 필수 포함하여, 운영자가 AI 판단을 검증하고 신뢰할 수 있도록 하는 Explainable AI 시스템.

---

## 2. 인터페이스 계약

### 2.1 공통 응답 스키마 (모든 AI 출력에 적용)

```python
# Spec: FR-AI-011
class ExplainableOutput(BaseModel):
    """모든 AI 응답에 반드시 포함되는 XAI 필드"""
    confidence: float = Field(..., ge=0.0, le=1.0, description="종합 신뢰도")
    reasoning_chain: list[str] = Field(
        ..., min_length=1,
        description="추론 과정 단계별 설명 (최소 1단계)"
    )
    evidence_links: list[str] = Field(
        default_factory=list,
        description="근거 데이터 API 경로"
    )
```

### 2.2 Confidence Score 정책

#### 점수 범위별 행동 규칙

| 범위 | 등급 | 자동 실행 | 대시보드 표시 | 알림 |
|------|------|----------|-------------|------|
| **0.8 ~ 1.0** | HIGH | Autonomy Level에 따라 허용 | 🟢 녹색 배지 | 일반 |
| **0.5 ~ 0.79** | MEDIUM | **관리자 확인 필수** (Level 강제 L2 이상) | 🟡 노란 배지 | "확인 필요" 알림 |
| **0.3 ~ 0.49** | LOW | **실행 차단** (추천만 표시) | 🟠 주황 배지 | "수동 분석 필요" 알림 |
| **0.0 ~ 0.29** | VERY_LOW | **실행 차단** + 수동 리뷰 플래그 | 🔴 빨간 배지 | "AI 판단 불확실" 경고 |

#### Autonomy Level 강제 조정

```python
# Spec: FR-AI-011, FR-AUTO-002
def adjust_autonomy_by_confidence(
    base_level: int,  # 0~4
    confidence: float,
    action_risk: ActionRisk
) -> int:
    """Confidence Score에 따라 Autonomy Level 하향 조정"""
    if confidence < 0.3:
        return 0  # 알림만
    if confidence < 0.5:
        return min(base_level, 1)  # 추천까지만
    if confidence < 0.8:
        return min(base_level, 2)  # 승인 후 실행
    if action_risk == ActionRisk.CRITICAL:
        return min(base_level, 2)  # 위험 액션은 항상 승인 필요
    return base_level  # 원래 Level 유지
```

### 2.3 API 엔드포인트

#### Confidence 통계 조회
- **Method**: GET
- **Path**: `/api/v1/confidence/stats`
- **Query Params**: `instance_id`, `from`, `to`, `model_version`
- **Response**:

```python
# Spec: FR-AI-011
class ConfidenceStatsResponse(BaseModel):
    period: str
    total_predictions: int
    avg_confidence: float
    confidence_distribution: dict[str, int]  # {"HIGH": 45, "MEDIUM": 30, ...}
    accuracy_rate: float | None  # 피드백 기반 (피드백 있는 경우만)
    false_positive_rate: float | None
```

#### Reasoning Chain 상세 조회
- **Method**: GET
- **Path**: `/api/v1/mtl/predictions/{prediction_id}/reasoning`
- **Response**:

```python
# Spec: FR-AI-011
class ReasoningDetailResponse(BaseModel):
    prediction_id: UUID
    reasoning_chain: list[ReasoningStep]
    evidence_links: list[EvidenceLink]

class ReasoningStep(BaseModel):
    step: int
    description: str
    evidence_type: str  # "metric" | "ash" | "query" | "rag" | "schema"
    data_point: str | None  # "CPU: 95%" 등

class EvidenceLink(BaseModel):
    url: str
    label: str  # "CPU 메트릭 (최근 1시간)"
    data_type: str  # "metric" | "ash" | "query_stats"
```

### 2.4 데이터 모델

#### `reasoning_chains` 테이블

```sql
-- Spec: FR-AI-011
CREATE TABLE reasoning_chains (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id   UUID NOT NULL REFERENCES mtl_predictions(id) ON DELETE CASCADE,
    step_number     INT NOT NULL,
    description     TEXT NOT NULL,
    evidence_type   VARCHAR(20),  -- metric / ash / query / rag / schema
    data_point      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(prediction_id, step_number)
);

CREATE INDEX idx_reasoning_chains_prediction ON reasoning_chains(prediction_id);
```

#### `evidence_links` 테이블

```sql
-- Spec: FR-AI-011
CREATE TABLE evidence_links (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id   UUID NOT NULL REFERENCES mtl_predictions(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    label           TEXT NOT NULL,
    data_type       VARCHAR(20) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_evidence_links_prediction ON evidence_links(prediction_id);
```

### 2.5 UI 컴포넌트

#### Confidence Badge

```
디자인 토큰 참조: FRONTEND_DESIGN.md

┌──────────────────────┐
│ 🟢 0.87 HIGH         │  ← confidence >= 0.8
│ 🟡 0.65 MEDIUM       │  ← 0.5 <= confidence < 0.8
│ 🟠 0.42 LOW          │  ← 0.3 <= confidence < 0.5
│ 🔴 0.18 VERY_LOW     │  ← confidence < 0.3
└──────────────────────┘

색상 매핑:
  HIGH     → tertiary (#4edea3)
  MEDIUM   → warning (#ffcc02)
  LOW      → error-dim (#ff8a65)
  VERY_LOW → error (#ffb4ab)
```

#### Reasoning Chain 컴포넌트

```
┌─ Reasoning Chain ────────────────────────────────┐
│                                                   │
│  ① CPU 사용률 95% (베이스라인: 40~60%)              │
│     └─ 📊 metric  "CPU 95%, baseline +40%"        │
│                                                   │
│  ② Top 쿼리 응답시간 3.2s → 12.8s (+300%)          │
│     └─ 📋 query   "SELECT * FROM orders ..."      │
│                                                   │
│  ③ EXPLAIN: Seq Scan on orders (cost=45000)       │
│     └─ 🔍 ash     "Wait: ClientRead → IO"         │
│                                                   │
│  ④ 과거 유사 사례 3건 → 인덱스 생성으로 해결          │
│     └─ 📚 rag     "similarity: 0.92"              │
│                                                   │
│  [근거 데이터 보기]  [피드백: 👍 👎]                  │
└───────────────────────────────────────────────────┘
```

---

## 3. 동작 규격

### 3.1 정상 시나리오

1. MTL 추론 완료 → ExplainableOutput 필드가 응답에 포함
2. 대시보드 인시던트 상세 페이지에 Confidence Badge 표시
3. 배지 클릭 → Reasoning Chain 확장 패널 표시
4. Evidence Links 클릭 → 해당 메트릭/ASH 페이지로 네비게이션
5. 운영자가 피드백 제출 (👍/👎) → `mtl_predictions.feedback_*` 업데이트
6. 주간 정확도 집계 → LLM Observability로 전달

### 3.2 예외 시나리오

| 시나리오 | 처리 |
|---------|------|
| Reasoning Chain 빈 배열 | 최소 1단계 기본 메시지 자동 생성: "AI가 분석을 수행했으나 상세 추론을 생성하지 못했습니다" |
| Evidence Link 404 | 링크 옆에 "(데이터 만료)" 표시, 클릭 차단 |
| Confidence 계산 실패 | 기본값 0.0 + `confidence_error: true` 플래그 |

### 3.3 경계 조건

- Confidence Score는 항상 소수점 3자리까지 표시 (0.871)
- Reasoning Chain은 최대 10단계
- Evidence Links는 최대 10개
- 오래된 Evidence Links (7일+): 데이터 보관 정책에 따라 만료 표시

---

## 4. 인수 기준 (Acceptance Criteria)

- [ ] **AC-1**: 모든 MTL 응답에 `confidence`, `reasoning_chain`, `evidence_links` 필드 포함
- [ ] **AC-2**: Confidence < 0.5인 경우 자동 실행이 차단되고 "추천만 표시" 상태로 전환
- [ ] **AC-3**: Confidence 0.5~0.8인 경우 Autonomy Level이 L2 이하로 강제 하향
- [ ] **AC-4**: 대시보드에 Confidence Badge가 색상 코딩으로 표시 (4단계)
- [ ] **AC-5**: Reasoning Chain 클릭 시 단계별 추론 과정이 펼침 패널로 표시
- [ ] **AC-6**: Evidence Links 클릭 시 해당 데이터 페이지로 네비게이션 성공
- [ ] **AC-7**: 운영자 피드백 (👍/👎) 저장 및 `/api/v1/confidence/stats`에서 집계
- [ ] **AC-8**: Confidence Score 계산이 가중 평균 공식에 부합 (오차 ±0.001)

---

## 5. 의존성

- **선행 Spec**: FS-AI-010 (MTL이 Confidence Score를 산출)
- **사용 Spec**: FS-AUTO-002 (Autonomy Level 조정에 사용)
- **후행 Spec**: FS-AI-013 (LLM Observability가 정확도 추적)

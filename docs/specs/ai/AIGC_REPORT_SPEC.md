# Feature Spec: AIGC 리포트 자동 생성

## 메타데이터
- **Spec ID**: FS-AI-005
- **PRD 참조**: FR-AI-005
- **우선순위**: P1 (Phase 2)
- **상태**: Approved
- **선행 Spec**: FS-AI-001 (Auto-Baseline), FS-AI-RAG-001 (RAG), DM-001 (ERD), FS-AI-LLM-001 (LLM Provider)
- **연동 Spec**: FS-AI-011 (Confidence Score), FS-ADMIN-004 (AI Decision Log)
- **구현 파일**:
  - Backend: `backend/app/services/report_generator.py`, `backend/app/api/v1/reports.py`
  - Schemas: `backend/app/schemas/report.py`
  - Tasks: `backend/app/tasks/report.py`
  - Test: `backend/tests/unit/test_ai_005_spec.py`

---

## 1. 개요

사용자가 자연어로 리포트를 요청하면("이번 주 DB 건강 리포트 만들어줘"), LLM이 수집된 메트릭/인시던트/ASH 데이터를 분석하여 **구조화된 건강 리포트**를 자동 생성하는 AIGC(AI-Generated Content) 시스템.

### 리포트 유형

| 유형 | 트리거 | 내용 | Phase |
|------|--------|------|-------|
| **On-Demand** | 사용자 요청 (API/UI) | 지정 기간의 DB 건강 분석 | Phase 2 |
| **Scheduled** | Celery Beat (주간/월간) | 정기 건강 리포트 자동 발송 | Phase 2 |
| **Incident** | 인시던트 해결 후 | 인시던트 사후 분석 리포트 | Phase 3 |

---

## 2. 인터페이스 계약

### 2.1 API Endpoints

#### 리포트 생성
- **Method**: POST
- **Path**: `/api/v1/reports/generate`
- **Auth**: JWT (DB Admin / Operator 이상)

```python
# Spec: FR-AI-005
class ReportGenerateRequest(BaseModel):
    instance_id: UUID | None = None      # None이면 전체 인스턴스 요약
    period: str = "7d"                    # 1d, 7d, 30d, custom
    period_start: datetime | None = None  # custom일 때
    period_end: datetime | None = None
    report_type: str = "health"           # health | performance | incident
    format: str = "html"                  # html | json (Phase 3: pdf)
    language: str = "ko"                  # ko | en
    custom_prompt: str | None = None      # 추가 분석 요청 ("인덱스 효율에 집중해줘")
```

- **Response**:

```python
# Spec: FR-AI-005
class ReportGenerateResponse(BaseModel):
    report_id: UUID
    instance_id: UUID | None
    report_type: str
    period: str
    status: str                           # completed | failed
    format: str

    # 리포트 본문
    title: str                            # AI 생성 제목
    executive_summary: str                # 1~3문장 요약
    sections: list[ReportSection]         # 분석 섹션들
    recommendations: list[Recommendation] # AI 추천 사항

    # 메타데이터
    generated_at: datetime
    generation_time_ms: int
    ai_model: str
    tokens_used: int
    confidence: float                     # 0.0~1.0

class ReportSection(BaseModel):
    title: str                            # 섹션 제목
    content: str                          # 마크다운 본문
    severity: str | None = None           # good | warning | critical
    metrics: dict | None = None           # 섹션 관련 수치 데이터
    chart_data: dict | None = None        # 프론트엔드 차트 렌더링용

class Recommendation(BaseModel):
    priority: str                         # high | medium | low
    title: str
    description: str
    action: str | None = None             # 구체적 SQL/명령
    confidence: float
```

#### 리포트 조회
- **Method**: GET
- **Path**: `/api/v1/reports/{report_id}`

#### 리포트 목록
- **Method**: GET
- **Path**: `/api/v1/reports`
- **Query**: `instance_id`, `report_type`, `from`, `to`, `limit`

---

## 3. 리포트 구조 (Health Report)

### 섹션 구성

```
📊 DB Health Report — pg-prod-01 (2026-03-19 ~ 2026-03-26)
│
├── 1. Executive Summary
│   "지난 7일간 전반적으로 안정적이나, 수요일 CPU 급증(92%) 이벤트 1건 발생.
│    인덱스 추가로 해결됨. Vacuum 지연 추세 관찰 필요."
│
├── 2. Resource Usage Trends
│   ├── CPU: 평균 35%, 최대 92% (3/22 14:30)
│   ├── Memory: 평균 68%, 안정적
│   ├── Connections: 평균 45/200, 피크 120/200
│   └── Disk: 78% 사용, 월 증가율 2.1%
│
├── 3. Query Performance
│   ├── Top 5 Slow Queries (avg_time 기준)
│   ├── Seq Scan 비율: 12% → 주의 필요
│   └── 쿼리 지연 P95: 450ms (베이스라인: 200ms)
│
├── 4. Incidents & Anomalies
│   ├── 총 3건 (CRITICAL:1, WARNING:2)
│   ├── MTTR: 평균 15분
│   └── 해결율: 100%
│
├── 5. ASH Analysis
│   ├── Top Wait Events: CPU(45%), IO(30%), Lock(15%)
│   └── 활성 세션 추세: 안정적
│
├── 6. Schema Changes
│   └── 1건: CREATE INDEX idx_orders_created_at (3/22)
│
├── 7. AI Recommendations
│   ├── [HIGH] dead_tuples 증가 추세 — VACUUM ANALYZE 권장
│   ├── [MED] shared_buffers 90% 사용 — 256MB→512MB 증설 검토
│   └── [LOW] 미사용 인덱스 3개 발견 — DROP 검토
│
└── 8. Confidence & Evidence
    ├── Overall Confidence: 0.85
    └── Data Sources: metric_samples, active_sessions, incidents, baselines
```

---

## 4. 동작 규격

### 4.1 데이터 수집 단계

```python
# Spec: FR-AI-005
async def gather_report_context(
    instance_id: UUID | None,
    period_start: datetime,
    period_end: datetime,
) -> ReportContext:
    """리포트에 필요한 데이터를 병렬 수집"""

    context = await asyncio.gather(
        # 메트릭 통계 (1분 집계 MV 활용)
        fetch_metric_summary(instance_id, period_start, period_end),
        # 인시던트 목록
        fetch_incidents(instance_id, period_start, period_end),
        # ASH Wait Event 집계
        fetch_ash_summary(instance_id, period_start, period_end),
        # 스키마 변경 이력
        fetch_schema_changes(instance_id, period_start, period_end),
        # 베이스라인 대비 현황
        fetch_baseline_comparison(instance_id),
        # Top Slow Queries
        fetch_slow_queries(instance_id, period_start, period_end),
    )

    return ReportContext(*context)
```

### 4.2 LLM 프롬프트

```python
# Spec: FR-AI-005
REPORT_SYSTEM_PROMPT = """You are a senior DBA writing a database health report.

Analyze the provided metrics, incidents, and session data to produce a structured report.

Rules:
- Be specific with numbers and timestamps
- Compare current values against baselines
- Prioritize actionable recommendations
- Use {language} language for all text content
- Rate each section: good (green), warning (yellow), critical (red)
- Provide confidence score (0.0-1.0) for the overall analysis

Output format: JSON matching the ReportSection schema."""

REPORT_USER_PROMPT = """Generate a {report_type} report for instance '{instance_name}'.
Period: {period_start} to {period_end}

=== Metric Summary ===
{metric_summary}

=== Incidents ({incident_count} total) ===
{incidents_text}

=== ASH Top Wait Events ===
{ash_summary}

=== Schema Changes ===
{schema_changes}

=== Baseline Comparison ===
{baseline_comparison}

=== Top Slow Queries ===
{slow_queries}

{custom_prompt}"""
```

### 4.3 생성 파이프라인

```
요청 수신
    → 기간/인스턴스 검증
    → 데이터 수집 (병렬 6종)
    → 프롬프트 구성
    → LLM 호출 (LLMProviderManager)
    → JSON 파싱 + 검증
    → AI Decision Log 기록 (FS-ADMIN-004)
    → 응답 반환
```

### 4.4 스케줄 리포트 (Celery)

```python
# Spec: FR-AI-005
# backend/app/tasks/report.py

@celery_app.task(name="generate_scheduled_report")
def generate_scheduled_report():
    """주간 리포트 자동 생성 (매주 월요일 09:00)"""
    # 모든 활성 인스턴스에 대해 7일 리포트 생성
    # Slack으로 리포트 링크 발송
```

Celery Beat 스케줄:
- 주간: 매주 월요일 09:00 KST
- 월간: 매월 1일 09:00 KST (Phase 3)

---

## 5. 성능 요구사항

| 메트릭 | 목표 |
|--------|------|
| 리포트 생성 시간 | < 30초 (단일 인스턴스 7일) |
| LLM 토큰 사용 | < 4000 tokens / 리포트 |
| 데이터 수집 | < 5초 (MV 활용) |
| 동시 생성 | 최대 3건 |

---

## 6. 인수 기준 (Acceptance Criteria)

- [ ] **AC-1**: POST `/api/v1/reports/generate`로 7일 건강 리포트 생성 시 30초 이내 응답
- [ ] **AC-2**: 응답에 executive_summary, sections(5개 이상), recommendations 포함
- [ ] **AC-3**: 각 section에 severity(good/warning/critical) 포함
- [ ] **AC-4**: recommendations에 priority + 구체적 action 포함
- [ ] **AC-5**: confidence score 0.0~1.0 포함
- [ ] **AC-6**: GET `/api/v1/reports`에서 기간/인스턴스별 리포트 목록 조회
- [ ] **AC-7**: AI Decision Log에 리포트 생성 이력 자동 기록 (model, tokens, cost)
- [ ] **AC-8**: Celery Beat으로 주간 리포트 자동 생성 동작
- [ ] **AC-9**: `instance_id: null`일 때 전체 인스턴스 요약 리포트 생성
- [ ] **AC-10**: `language: "ko"` / `"en"` 전환 동작

---

## 7. 의존성

- **선행 Spec**: DM-001 (메트릭/인시던트 테이블), FS-AI-LLM-001 (LLM Provider), FS-AI-001 (Baseline 비교)
- **연동 Spec**: FS-AI-011 (Confidence Score), FS-ADMIN-004 (AI Decision Log), CELERY_TASKS_SPEC (스케줄)
- **데이터 소스**: `metric_samples`, `active_sessions`, `incidents`, `baselines`, `schema_changes`, `mv_metrics_1m`

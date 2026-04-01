# Feature Spec: DBA 정기 리포트 (Daily/Weekly/Monthly)

## 메타데이터
- **Spec ID**: FS-AI-REPORT-001
- **PRD 참조**: FR-AI-005, FR-ALERT-001
- **우선순위**: P0 (MVP)
- **상태**: Approved
- **선행 Spec**: FS-AI-005 (AIGC Report), FS-DBA-003 (Proactive Agent)

---

## 1. 개요

DBA가 매일/매주/매월 받아보는 정기 DB 운영 리포트. 인시던트 요약, 성능 트렌드, Slow Query 상세 분석, 스키마 변경 이력을 **한국어**로 Slack에 자동 발송합니다.

**핵심 차별점**: Slow Query 섹션에서 개별 쿼리의 **실행 계획, 호출 횟수, 평균 실행 시간, 영향도**를 상세히 보여줌.

---

## 2. 리포트 유형

| 유형 | 주기 | Celery Beat | 내용 범위 |
|------|------|-------------|----------|
| **Daily** | 매일 09:00 | `daily-dba-report` | 24시간 |
| **Weekly** | 매주 월요일 09:00 | `weekly-dba-report` | 7일 |
| **Monthly** | 매월 1일 09:00 | `monthly-dba-report` | 30일 |

---

## 3. 리포트 구조

### 3.1 공통 섹션

```
📊 NeuralDB {Daily|Weekly|Monthly} DBA 리포트
인스턴스: {instance_name} | 기간: {start_date} ~ {end_date}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 📈 핵심 지표 요약
   ┌─────────────┬────────┬────────┬────────┐
   │ 지표         │ 평균   │ 최대   │ 상태   │
   ├─────────────┼────────┼────────┼────────┤
   │ CPU 사용률   │ 45%    │ 92%    │ ⚠️     │
   │ 메모리 사용률 │ 62%    │ 78%    │ 🟢     │
   │ 커넥션 수    │ 85     │ 195    │ 🟢     │
   │ TPS         │ 1,240  │ 3,450  │ 🟢     │
   │ 버퍼히트율   │ 99.2%  │ 99.8%  │ 🟢     │
   └─────────────┴────────┴────────┴────────┘

2. 🚨 인시던트 요약
   총 {count}건 (Critical: {c}, Warning: {w}, Notice: {n})
   • [CRITICAL] 2026-03-30 14:23 — CPU 스파이크 95% (5분간)
   • [WARNING]  2026-03-30 18:45 — 커넥션 풀 포화 (190/200)
   해결률: {resolved}/{total} ({percent}%)

3. 🐌 Slow Query 상세 (Top 10)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   #1 | 평균 실행시간: 2,340ms | 호출: 1,250회 | 총 소요: 48.8분
   Query: SELECT o.*, u.name FROM orders o JOIN users u ON ...
   Wait Event: LWLock (buffer_mapping)
   실행 계획: Seq Scan on orders (rows=125,000, cost=15,234)
   💡 권장: CREATE INDEX idx_orders_user_id ON orders(user_id)
   ─────────────────────────────
   #2 | 평균 실행시간: 1,890ms | 호출: 430회 | 총 소요: 13.5분
   Query: UPDATE inventory SET stock = stock - 1 WHERE ...
   Wait Event: Lock (transactionid)
   실행 계획: Index Scan using pk_inventory (rows=1)
   💡 권장: 트랜잭션 격리 수준 확인, 배치 업데이트 검토
   ─────────────────────────────
   ...

4. 🔄 스키마 변경 이력
   {count}건의 DDL 변경 감지
   • [ALTER] 2026-03-28 — orders 테이블 컬럼 추가 (delivery_date)
   • [CREATE] 2026-03-29 — idx_orders_status 인덱스 생성

5. 🤖 AI 분석 요약 (LLM 생성)
   {LLM이 위 데이터를 종합하여 한국어로 작성한 분석 요약}
   - 주요 발견사항
   - 성능 트렌드 (개선/악화)
   - 우선 조치 권장사항

6. 📊 기간별 트렌드 (Weekly/Monthly만)
   CPU: ↗ 15% 증가 추세
   TPS: ↘ 5% 감소 (정상 범위)
   Slow Query: ↗ 신규 2건 추가
```

### 3.2 Slow Query 상세 섹션 (핵심)

**데이터 소스**: `pg_stat_statements` + `active_sessions` (ASH)

```python
# Spec: FS-AI-REPORT-001 §3.2
class SlowQueryDetail:
    rank: int                    # Top N 순위
    query: str                   # SQL 텍스트 (최대 500자)
    query_hash: int              # pg_stat_statements queryid
    calls: int                   # 호출 횟수
    mean_exec_time_ms: float     # 평균 실행 시간
    total_exec_time_ms: float    # 총 소요 시간
    rows_returned: int           # 반환된 행 수
    shared_blks_hit: int         # 버퍼 히트
    shared_blks_read: int        # 디스크 읽기
    wait_event: str | None       # 주요 Wait Event (ASH 기반)
    plan_summary: str | None     # 실행 계획 요약 (Seq Scan, Index Scan 등)
    recommendation: str          # AI 권장 조치 (한국어)
```

**수집 쿼리**:
```sql
-- Slow Query Top 10 (기간 내)
SELECT
    queryid,
    LEFT(query, 500) AS query,
    calls,
    mean_exec_time AS mean_exec_time_ms,
    total_exec_time AS total_exec_time_ms,
    rows,
    shared_blks_hit,
    shared_blks_read
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
ORDER BY mean_exec_time DESC
LIMIT 10;
```

---

## 4. API 엔드포인트

### 수동 리포트 생성
- **Method**: POST
- **Path**: `/api/v1/reports/dba`
- **Auth**: JWT (DB Admin 이상)

```python
class DBAReportRequest(BaseModel):
    instance_id: UUID
    period: Literal["daily", "weekly", "monthly"] = "daily"
    send_slack: bool = True
    slow_query_limit: int = Field(default=10, ge=1, le=50)

class DBAReportResponse(BaseModel):
    report_id: UUID
    instance_name: str
    period: str
    generated_at: datetime
    summary: str              # 핵심 지표 1줄 요약
    metrics_summary: dict     # CPU/Memory/TPS avg/max
    incident_count: int
    slow_queries: list[SlowQueryDetail]
    schema_changes: int
    ai_analysis: str          # LLM 분석 요약 (한국어)
    slack_sent: bool
```

### 리포트 이력 조회
- **Method**: GET
- **Path**: `/api/v1/reports/dba`
- **Query**: `instance_id`, `period`, `from`, `to`, `limit`

---

## 5. Celery Beat 스케줄

```python
# Spec: FS-AI-REPORT-001 §5
CELERY_BEAT_SCHEDULE = {
    "daily-dba-report": {
        "task": "app.tasks.reports.generate_dba_report",
        "schedule": crontab(hour=9, minute=0),  # 매일 09:00
        "args": ("daily",),
    },
    "weekly-dba-report": {
        "task": "app.tasks.reports.generate_dba_report",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),  # 월요일 09:00
        "args": ("weekly",),
    },
    "monthly-dba-report": {
        "task": "app.tasks.reports.generate_dba_report",
        "schedule": crontab(hour=9, minute=0, day_of_month=1),  # 매월 1일 09:00
        "args": ("monthly",),
    },
}
```

---

## 6. Slack 메시지 포맷

### Daily (간결)
```
📊 *NeuralDB Daily DBA 리포트* — pg-prod-01
기간: 2026-03-30 09:00 ~ 2026-03-31 09:00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 핵심 지표: CPU 45%(max 92%) | TPS 1,240 | 커넥션 85
🚨 인시던트: 3건 (Critical 1, Warning 2) | 해결률 67%
🐌 Slow Query Top 3:
  1. SELECT orders... — 2,340ms × 1,250회
  2. UPDATE inventory... — 1,890ms × 430회
  3. SELECT products... — 1,120ms × 2,100회
🔄 스키마 변경: 2건
🤖 AI 요약: CPU 스파이크는 orders 테이블 풀스캔이 원인. idx_orders_user_id 인덱스 생성 권장.
```

### Weekly (상세)
Daily 포맷 + 트렌드 차트 링크 + Slow Query Top 10 상세

### Monthly (종합)
Weekly 포맷 + 월간 SLA 달성률 + 용량 증가 추세 + 인덱스 사용률 통계

---

## 7. 인수 기준 (Acceptance Criteria)

- [ ] **AC-1**: POST `/api/v1/reports/dba` 호출 시 지정된 기간의 DBA 리포트 JSON 반환
- [ ] **AC-2**: Daily 리포트에 핵심 지표 요약 (CPU/Memory/TPS/Connection avg/max) 포함
- [ ] **AC-3**: Slow Query Top N에 query, calls, mean_exec_time, recommendation 포함
- [ ] **AC-4**: 리포트 AI 분석 요약이 한국어로 생성됨
- [ ] **AC-5**: Celery Beat에 daily/weekly/monthly 스케줄 등록
- [ ] **AC-6**: Slack Webhook으로 리포트 자동 발송
- [ ] **AC-7**: Weekly/Monthly 리포트에 기간별 트렌드 (증가/감소) 포함
- [ ] **AC-8**: 스키마 변경 이력이 리포트에 포함됨

---

## 8. 의존성

- **선행 Spec**: FS-AI-005 (AIGC Report), FS-DBA-003 (Proactive Agent)
- **데이터 소스**: `metric_samples`, `active_sessions`, `incidents`, `schema_changes`, `pg_stat_statements`
- **외부**: Slack Webhook URL (settings)

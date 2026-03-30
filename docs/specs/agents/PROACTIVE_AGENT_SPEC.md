# Feature Spec: Proactive DBA Agent (Tier 3 — 자율 운영)

## 메타데이터
- **Spec ID**: FS-DBA-003
- **PRD 참조**: FR-AUTO-001, FR-ALERT-001
- **우선순위**: P1 (Sprint 3)
- **상태**: Approved
- **선행 Spec**: FS-DBA-001 (Execution Layer), FS-DBA-002 (Orchestrator), FS-AI-001 (Auto Baseline)
- **구현 파일**:
  - Backend: `backend/app/agents/proactive_agent.py`
  - Task: `backend/app/tasks/proactive.py` (Celery Beat)
  - Test: `backend/tests/unit/test_dba_003_spec.py`

---

## 1. 개요

DBA Agent가 **사람의 요청 없이도** 주기적으로 DB를 점검하고, 이상 발견 시 자동으로 분석 + 알림 + 조치 추천을 수행하는 자율 운영 모드.

> **현재 (Reactive)**: 사용자가 "DB 느려"라고 물어야 분석 시작
> **목표 (Proactive)**: Agent가 알아서 점검 → 이상 시 Slack 리포트 → Autonomy Level에 따라 자동 조치

```
┌─ Proactive Agent (Celery Beat 스케줄) ─────────────────┐
│                                                         │
│  매 30분: Quick Health Check                            │
│    ├─ CPU > 80%? → DBA Agent analyze                    │
│    ├─ Connections > 90%? → DBA Agent analyze             │
│    ├─ Deadlocks > 0? → DBA Agent diagnose               │
│    ├─ Replication lag > 30s? → Alert                     │
│    └─ All OK → silent (로그만)                           │
│                                                         │
│  매 6시간: Deep Analysis                                │
│    ├─ Slow query top 10 분석                             │
│    ├─ Index 추천 생성                                    │
│    ├─ Table bloat 점검                                   │
│    ├─ Vacuum 상태 점검                                   │
│    └─ 결과 → Slack + agent_actions에 suggested 저장     │
│                                                         │
│  매일 09:00: Morning Report                             │
│    ├─ 지난 24시간 요약 (인시던트, 메트릭 트렌드)         │
│    ├─ AI 추천 사항 (인덱스, 파라미터 튜닝)              │
│    └─ Slack 채널로 자동 발송                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 점검 스케줄

| 스케줄 | 이름 | 내용 | 소요 시간 |
|--------|------|------|----------|
| 매 30분 | Quick Check | KPI 임계값 점검 (CPU, Conn, Deadlock, Lag) | < 5초 |
| 매 6시간 | Deep Analysis | Slow query + Index + Bloat + Vacuum 분석 | < 60초 |
| 매일 09:00 | Morning Report | 24시간 요약 + AI 추천 | < 30초 (LLM 미사용) |

### 2.1 Quick Check 규칙

| 메트릭 | 임계값 | 액션 |
|--------|--------|------|
| CPU usage | > 80% | DBA Agent analyze (성능 분석) |
| Active connections | > 90% of max | DBA Agent analyze (커넥션 분석) |
| Deadlocks/min | > 0 | DBA Agent diagnose (락 분석) |
| Replication lag | > 30초 | Slack CRITICAL alert |
| Long running query | > 300초 | DBA Agent analyze + kill 추천 |

### 2.2 Deep Analysis 항목

| 분석 | DBA Tool | 결과 |
|------|---------|------|
| Slow query top 10 | `slow_queries()` | agent_actions에 suggested 저장 |
| Missing index 추천 | `index_recommendations()` | create_index ActionRequest 생성 |
| Table bloat > 30% | `table_bloat()` | vacuum ActionRequest 생성 |
| Vacuum overdue | `table_bloat()` | vacuum ActionRequest 생성 |
| Parameter tuning | `parameter_tuning()` | alter_parameter 추천 |

### 2.3 Self-Healing (Autonomy L3+)

```
Quick Check 이상 감지
    ↓
DBA Agent 분석
    ↓
ActionRequest 생성 (ops_tools)
    ↓
SafetyGuard 분류
    ↓
Autonomy Level 확인
    ├─ L0~L1: 알림 + 추천만
    ├─ L2: agent_actions에 pending 저장 → 사람 승인 대기
    └─ L3+: ExecutionEngine 자동 실행 → 결과 보고
```

---

## 3. API

| Method | Path | Auth | 설명 |
|--------|------|------|------|
| GET | `/api/v1/proactive/status` | JWT | Proactive Agent 상태 (last_check, next_check) |
| GET | `/api/v1/proactive/history` | JWT | 점검 이력 |
| POST | `/api/v1/proactive/trigger` | JWT (Admin) | 수동 점검 트리거 |

---

## 4. Slack 알림 형식

### Quick Check Alert
```
🔴 [NeuralDB Proactive] pg-prod-01
CPU 92% (baseline: 40-60%)
Active connections: 185/200 (93%)
Recommended: Analyze slow queries + check connection pool

DBA Agent 분석 결과:
- Slow query: SELECT * FROM large_table WHERE... (120s)
- 추천: CREATE INDEX CONCURRENTLY idx_large_table_user_id
```

### Morning Report
```
📊 [NeuralDB Daily Report] 2026-03-30
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Instances: 2 (all healthy)
Incidents (24h): 0 new, 0 resolved
Metrics: TPS avg 45, Hit% 99.6, Conn avg 12/200
AI Recommendations:
  - pg-prod-01: Consider index on orders(created_at)
  - pg-staging-01: Vacuum overdue on metric_samples (3 days)
```

---

## 5. 인수 기준 (Acceptance Criteria)

### Proactive Check

- [ ] **AC-1**: Celery Beat에 30분 Quick Check 스케줄 등록
- [ ] **AC-2**: Quick Check에서 CPU > 80% 감지 시 DBA Agent analyze 자동 호출
- [ ] **AC-3**: Quick Check 결과가 Slack 채널로 자동 발송
- [ ] **AC-4**: Deep Analysis (6시간)에서 slow query + index + bloat 분석 수행

### Self-Healing

- [ ] **AC-5**: Autonomy L3 인스턴스에서 이상 감지 시 ActionRequest 자동 생성 + 실행
- [ ] **AC-6**: 실행 결과가 agent_actions + audit_logs에 자동 기록
- [ ] **AC-7**: 실패 시 Autonomy Level 자동 격하 (L3→L2)

### Morning Report

- [ ] **AC-8**: 매일 09:00에 24시간 요약 리포트 자동 생성
- [ ] **AC-9**: 리포트가 Slack 채널로 발송

### API

- [ ] **AC-10**: GET /proactive/status에서 last_check, next_check 조회 가능

---

## 6. 의존성

- **선행**: FS-DBA-001 (ExecutionEngine), FS-DBA-002 (DBA Agent), FS-AI-001 (Baseline)
- **연동**: FS-SELF-001 (System Health), FS-KPI-001 (KPI 임계값)
- **알림**: Slack webhook (기존 alert task 재사용)

# Feature Spec: DBA Agent Orchestrator — 단일 인터페이스

## 메타데이터
- **Spec ID**: FS-DBA-002
- **PRD 참조**: FR-AI-012, FR-AUTO-001
- **우선순위**: P0
- **상태**: Approved
- **선행 Spec**: FS-DBA-001 (Execution Layer), FS-AI-TUNE-001, FS-AI-012 (Copilot)
- **구현 파일**:
  - Agent: `backend/app/agents/dba_agent.py`
  - API: `backend/app/api/v1/dba.py`
  - Schema: `backend/app/schemas/dba.py`
  - Test: `backend/tests/unit/test_dba_002_spec.py`

---

## 1. 개요

사용자는 **단일 DBA Agent**와 대화합니다. 내부적으로 Intent를 분류하여 적절한 서브 Agent(Tuning/Copilot/Execution/NL2SQL)로 라우팅합니다.

```
사용자: "DB가 느려"
    ↓
POST /api/v1/dba/ask
    ↓
DBAAgent.ask()
    ↓ Intent Classification (키워드 + LLM fallback)
    ├─ "analyze"  → DBTuningAgent.analyze()     → 분석 + 추천
    ├─ "diagnose" → DBCopilotAgent.diagnose()   → ToT 진단
    ├─ "execute"  → ExecutionEngine.execute()    → 승인/실행
    ├─ "query"    → NL2SQL (GraphRAG)            → SQL 결과
    └─ "status"   → System Health + KPI          → 상태 요약
    ↓
통합 DBAResponse
```

### 설계 원칙

- **라우터 패턴** — LangGraph/CrewAI 프레임워크 없이 단순 분기
- **LLM 호출 최소화** — 키워드 매칭 우선, 모호할 때만 LLM intent 분류 (1회)
- **세션 컨텍스트** — 이전 대화 참조 가능 (최근 5개 턴)
- **통합 응답 포맷** — 어떤 서브 Agent가 처리하든 동일한 DBAResponse 구조

---

## 2. Intent Classification

### 2.1 키워드 기반 (빠름, LLM 불필요)

| Intent | 키워드 | 서브 Agent |
|--------|--------|-----------|
| `analyze` | 느린, slow, 성능, performance, 쿼리, query, index, vacuum, bloat, 튜닝, tuning, explain | DBTuningAgent |
| `diagnose` | 장애, 원인, rca, 진단, diagnose, incident, 이상, anomaly, why | DBCopilotAgent |
| `execute` | 실행, execute, create index, vacuum, kill, alter, 만들어, 생성 | ExecutionEngine |
| `query` | 조회, select, 보여줘, show, list, count, 몇 개, how many | NL2SQL |
| `status` | 상태, health, status, 정상, 점검, check | System Health |

### 2.2 LLM Fallback (키워드 매칭 실패 시)

```python
INTENT_PROMPT = """You are a DBA Agent intent classifier.
Classify the user's question into exactly one category:
- analyze: performance analysis, slow query, index recommendation, tuning
- diagnose: incident investigation, root cause, anomaly explanation
- execute: run a specific DB operation (create index, vacuum, kill session)
- query: data retrieval, show/list/count database information
- status: system health check, DB status overview

Question: {question}
Answer with one word only: analyze, diagnose, execute, query, or status"""
```

### 2.3 분류 전략

```
1. 키워드 매칭 (0ms) → 확실하면 바로 라우팅
2. 키워드 2개 이상 매칭 (모호) → LLM intent 분류 (~1초)
3. 키워드 0개 매칭 → LLM intent 분류 (~1초)
```

---

## 3. API

### 3.1 통합 DBA Agent API

| Method | Path | Auth | 설명 |
|--------|------|------|------|
| POST | `/api/v1/dba/ask` | JWT (Operator+) | DBA Agent에게 질문 |
| GET | `/api/v1/dba/sessions/{id}` | JWT (Operator+) | 세션 상세 (대화 이력) |
| GET | `/api/v1/dba/sessions` | JWT (Operator+) | 세션 목록 |

### 3.2 Request / Response

```python
# Spec: FS-DBA-002
class DBARequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    instance_id: UUID
    session_id: UUID | None = None  # 기존 세션 이어가기 (None이면 새 세션)

class DBAResponse(BaseModel):
    session_id: UUID
    intent: str                     # analyze | diagnose | execute | query | status
    answer: str                     # 사람이 읽을 수 있는 답변 텍스트
    data: dict | None = None        # 구조화된 데이터 (차트, 테이블 등)
    actions: list[ActionSummary] | None = None  # 실행 가능한 액션 목록
    model: str                      # 사용된 LLM 모델
    processing_time_ms: int

class ActionSummary(BaseModel):
    action_id: UUID | None = None   # pending action ID (승인 필요 시)
    action_type: str                # create_index, vacuum, ...
    sql: str
    risk_level: str                 # safe, warning, dangerous, critical
    status: str                     # suggested | pending | executed
    description: str
```

---

## 4. 세션 컨텍스트

### 4.1 대화 이력 (최근 5턴)

```python
class DBASession:
    session_id: UUID
    instance_id: UUID
    turns: list[DBASessionTurn]     # 최근 5개
    created_at: datetime

class DBASessionTurn:
    role: str                       # "user" | "agent"
    content: str
    intent: str | None              # agent 턴에서 분류된 intent
    timestamp: datetime
```

### 4.2 컨텍스트 활용

```
Turn 1: "DB 느려" → analyze → "CPU 90%, slow query 3개 발견"
Turn 2: "인덱스 만들어줘" → execute → create_index ActionRequest (이전 분석 참조)
Turn 3: "결과 보여줘" → query → SELECT from agent_actions WHERE ...
```

세션 저장: **Valkey** (TTL 30분, 최대 5턴). DB 영속화 불필요 (임시 대화).

---

## 5. 인수 기준 (Acceptance Criteria)

- [ ] **AC-1**: POST `/api/v1/dba/ask`가 question + instance_id를 받아 DBAResponse 반환
- [ ] **AC-2**: 키워드 기반 intent 분류가 5가지 intent를 정확히 구분
- [ ] **AC-3**: 키워드 모호 시 LLM fallback으로 intent 분류
- [ ] **AC-4**: intent="analyze" → DBTuningAgent.analyze() 호출
- [ ] **AC-5**: intent="diagnose" → DBCopilotAgent.diagnose() 호출
- [ ] **AC-6**: intent="execute" → ops_tools → ExecutionEngine 연결
- [ ] **AC-7**: intent="query" → NL2SQL (GraphRAG) 호출
- [ ] **AC-8**: intent="status" → System Health + KPI 요약 반환
- [ ] **AC-9**: session_id로 이전 대화 이어가기 가능
- [ ] **AC-10**: DBAResponse에 actions 필드로 실행 가능한 액션 목록 제공

### 답변 품질 (AC-14~16)

- [ ] **AC-14**: 사용자 답변에 ReAct 내부 추론(Action:/Action Input:/Observation:)이 노출되지 않음
- [ ] **AC-15**: LLM이 Final Answer 없이 max_iterations 도달 시, 수집된 tool 결과를 별도 LLM 호출로 한국어 요약 합성
- [ ] **AC-16**: DBA Agent 응답의 answer 필드가 사람이 읽을 수 있는 자연어 형태

---

## 5.2 답변 품질 보장 전략

### 문제: ReAct 내부 추론 노출

TuningAgent는 ReAct 패턴(Thought→Action→Observation 반복)으로 동작합니다.
LLM이 `Final Answer:` 포맷을 따르지 않고 `max_iterations`에 도달하면,
마지막 LLM 출력(내부 추론)이 사용자에게 그대로 노출될 수 있습니다.

### 해결: 2단계 방어

```
ReAct Loop (max 5 iterations)
    ↓
LLM이 "Final Answer: {...}" 반환? ─Yes─→ JSON 파싱 → 정상 응답
    │
    No (max_iterations 도달)
    ↓
_synthesize_from_observations()
    ├─ 수집된 tool 결과 (Observation) 추출 (최대 5개)
    ├─ 별도 LLM 호출: "이 결과를 한국어 요약으로 합성해줘"
    └─ 실패 시 Fallback: tool 이름 + 첫 줄 요약 (LLM 미사용)
    ↓
_clean_react_output()
    ├─ Action: / Action Input: / Observation: / Thought: 패턴 제거
    └─ 빈 결과면 원본 유지 (안전 fallback)
    ↓
사용자에게 깨끗한 자연어 응답 반환
```

### 대화 맥락 유지 (AC-17~18)

- [ ] **AC-17**: session_id 기반 대화 이어가기 — Valkey에 최근 5턴 저장 (TTL 30분)
- [ ] **AC-18**: 이전 대화 컨텍스트가 LLM 프롬프트에 포함되어 "아까 그 테이블" 참조 가능

**구현:**
```
Turn 1: "DB 느려" → analyze → "slow query 3개, orders 테이블 문제"
Turn 2: "인덱스 만들어줘" → execute → (session context에서 orders 참조)
         → create_index(orders, [created_at])
```

세션 저장: Valkey `dba:session:{session_id}` (TTL 30분, JSON, 최근 5턴)

### 사용자 피드백 (AC-19~20)

- [ ] **AC-19**: DBA Agent 응답에 👍/👎 피드백 버튼 표시 (미니 위젯 + /dba 페이지)
- [ ] **AC-20**: 피드백 클릭 시 POST `/api/v1/dba/feedback` → audit_logs에 기록

**구현:**
- Frontend: 각 agent 응답 하단에 👍/👎 아이콘 버튼
- Backend: `POST /api/v1/dba/feedback {session_id, message_id, feedback: "positive"|"negative"}`
- 저장: audit_logs (action="dba_feedback", details={feedback, question, intent})
---

## 5.1 Frontend — 미니 채팅 위젯 (AC-11~13)

### 위젯 형태

DBA Agent는 **우측 하단 미니 채팅 위젯**으로 모든 페이지에 상시 표시됩니다.
기존 NL2SQLChat 플로팅 위젯을 대체합니다.

```
┌─ Dashboard / ASH / Incidents / ... ────────────────────┐
│                                                         │
│  (메인 콘텐츠)                                          │
│                                                         │
│                              ┌─ DBA Agent ────────────┐│
│                              │ ▼ Instance: pg-prod-01  ││
│                              │─────────────────────────││
│                              │ 🤖 DBA Agent Ready      ││
│                              │                         ││
│                              │ User: DB 상태 알려줘     ││
│                              │ Agent: System healthy... ││
│                              │                         ││
│                              │ [입력창] [전송]          ││
│                              └─────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### 인스턴스 선택

- 위젯 상단에 **인스턴스 드롭다운** 표시
- 등록된 모든 DB 인스턴스 목록 (GET `/api/v1/instances`)
- 선택 시 `instance_id`가 DBA Agent 요청에 자동 포함
- **인스턴스 미선택 시 채팅 비활성화** + "인스턴스를 선택하세요" 안내

### 위젯 동작

- **접힌 상태**: 우하단에 🤖 아이콘 버튼만 표시 (기존 NL2SQL 위치)
- **펼친 상태**: 400×500px 미니 채팅 창 (크기 조절 불가, 위치 고정)
- `/dba` 전체 페이지와 동일한 채팅 로직 공유 (DBAResponse 렌더링)
- query intent의 결과 테이블, action 카드 모두 위젯 내에서 표시

### AC

- [ ] **AC-11**: DBA Agent 미니 채팅 위젯이 모든 인증 페이지 우하단에 표시됨
- [ ] **AC-12**: 위젯 상단 드롭다운으로 DB 인스턴스 선택 후 채팅 가능
- [ ] **AC-13**: 인스턴스 미선택 시 입력 비활성화 + 안내 메시지 표시

---

## 6. 의존성

- **선행**: FS-DBA-001 (ExecutionEngine), FS-AI-TUNE-001, FS-AI-012, FS-AI-NL2SQL-001
- **연동**: FS-SELF-001 (System Health), FS-KPI-001 (KPI)

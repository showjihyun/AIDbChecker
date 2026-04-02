# Feature Spec: DB Performance Tuning Agent (LangChain ReAct)

## 메타데이터
- **Spec ID**: FS-AI-TUNE-001
- **PRD 참조**: FR-AUTO-001~005, FR-AI-012
- **우선순위**: P0 (Phase 2)
- **상태**: Implemented (Phase 2)
- **선행 Spec**: FS-AI-LLM-001 (LLM Provider), DM-001 (ERD), AG-001 (Adapter)
- **구현 파일**:
  - Backend: `backend/app/agents/tuning_agent.py`, `backend/app/agents/native_tool_agent.py`, `backend/app/agents/tools/`, `backend/app/api/v1/tuning.py`
  - Config: `backend/app/config.py` (`TUNING_REQUEST_TIMEOUT`, `TUNING_POOL_COMMAND_TIMEOUT`)
  - Test: `backend/tests/unit/test_tuning_agent_spec.py`

---

## 1. 개요

LangChain ReAct Agent가 **PostgreSQL 성능 분석 도구 7개**를 사용하여 자율적으로 장애 원인을 분석하고 튜닝 액션을 추천합니다. 사용자는 자연어로 질의하면 Agent가 필요한 도구를 선택하여 실행합니다.

> Phase 3의 MCP Server로 확장 시, 같은 Tool 함수를 MCP Tool로 노출합니다 (코드 재사용 100%).

---

## 2. Agent 아키텍처

```
사용자 질의: "이 쿼리가 느린 이유를 분석해줘"
    ↓
ReAct Agent (LLM + Tools)
    ↓ Thought → Action → Observation 루프
    ├── explain_query() → EXPLAIN ANALYZE 실행
    ├── slow_queries() → pg_stat_statements Top N
    ├── index_recommendations() → missing index 분석
    ├── parameter_tuning() → pg_settings 최적화 제안
    ├── table_bloat() → dead tuple + bloat 분석
    ├── lock_analysis() → blocking session 식별
    └── connection_analysis() → idle 세션 + 풀 상태
    ↓
최종 응답: 원인 분석 + 추천 액션 (SQL 포함)
```

---

## 3. Tool 정의 (7개)

### 3.1 explain_query

```python
@tool
def explain_query(sql: str) -> str:
    """EXPLAIN ANALYZE 실행 → 실행 계획 반환.

    Seq Scan, Nested Loop, Sort 등 비용이 높은 노드를 식별합니다.
    읽기 전용 — SELECT만 허용, statement_timeout 5초.
    """
```

- 입력: SQL 쿼리문
- 출력: EXPLAIN ANALYZE 결과 텍스트
- 안전: SELECT만 허용 (NL2SQL과 같은 _validate_sql_readonly 적용)

### 3.2 slow_queries

```python
@tool
def slow_queries(top_n: int = 10) -> str:
    """pg_stat_statements에서 가장 느린 쿼리 Top N 조회.

    mean_exec_time 기준 정렬. calls, total_time, rows 포함.
    pg_stat_statements 미설치 시 에러 메시지 반환.
    """
```

- 입력: top_n (기본 10)
- 출력: 쿼리 목록 (query, calls, mean_time, total_time)

### 3.3 index_recommendations

```python
@tool
def index_recommendations(table_name: str | None = None) -> str:
    """인덱스 추천 — Seq Scan 비율이 높은 테이블 분석.

    pg_stat_user_tables의 seq_scan vs idx_scan 비교.
    특정 테이블 지정 시 해당 테이블의 컬럼별 인덱스 현황.
    """
```

- 입력: table_name (선택)
- 출력: 추천 CREATE INDEX 문 목록

### 3.4 parameter_tuning

```python
@tool
def parameter_tuning() -> str:
    """PostgreSQL 파라미터 최적화 제안.

    현재 pg_settings 값과 시스템 리소스(shared_buffers, work_mem,
    effective_cache_size, maintenance_work_mem) 비교.
    """
```

- 출력: 현재 값 + 추천 값 + ALTER SYSTEM SET 문

### 3.5 table_bloat

```python
@tool
def table_bloat(table_name: str | None = None) -> str:
    """테이블 bloat(비대화) 분석.

    n_dead_tup, n_live_tup, last_vacuum, last_autovacuum 확인.
    dead tuple 비율이 높은 테이블에 VACUUM ANALYZE 추천.
    """
```

- 출력: bloat 분석 + VACUUM 추천

### 3.6 lock_analysis

```python
@tool
def lock_analysis() -> str:
    """현재 Lock 상태 분석 — blocking session 식별.

    pg_stat_activity에서 wait_event_type='Lock'인 세션과
    pg_blocking_pids()로 차단 원인 세션 식별.
    """
```

- 출력: blocking chain + pg_terminate_backend 추천 (위험도 표시)

### 3.7 connection_analysis

```python
@tool
def connection_analysis() -> str:
    """연결 상태 분석 — idle 세션 + 풀 효율.

    state별 세션 수, idle in transaction 세션 지속시간,
    max_connections 대비 사용률.
    """
```

- 출력: 연결 분석 + idle 세션 정리 추천

---

## 4. API 엔드포인트

### 4.1 Tuning Agent 실행

- **Method**: POST
- **Path**: `/api/v1/tuning/analyze`
- **Auth**: JWT (db_admin+ role)
- **Request**:

```python
class TuningRequest(BaseModel):
    instance_id: UUID
    question: str           # 자연어 질문
    max_iterations: int = 5 # Agent 최대 반복 횟수
```

- **Response**:

```python
class TuningResponse(BaseModel):
    instance_id: UUID
    question: str
    analysis: str           # Agent 최종 분석 결과
    actions: list[TuningAction]  # 추천 액션 목록
    tools_used: list[str]   # 사용된 도구 목록
    iterations: int         # 실제 반복 횟수
    model_used: str         # 사용된 LLM 모델
    duration_ms: int        # 전체 실행 시간

class TuningAction(BaseModel):
    action_type: str        # CREATE_INDEX / VACUUM / ALTER_SYSTEM / KILL_SESSION / REWRITE_QUERY
    description: str        # 액션 설명
    sql: str | None         # 실행할 SQL (있는 경우)
    risk_level: str         # low / medium / high
    estimated_impact: str   # 예상 효과
```

### 4.2 Tuning 이력 조회

- **Method**: GET
- **Path**: `/api/v1/tuning/history`
- **Auth**: JWT (operator+)
- **Query**: instance_id, limit

---

## 4.3 Agent 라우팅 및 타임아웃

```python
# Spec: FS-AI-TUNE-001 §4.3

# 환경변수 (config.py)
TUNING_REQUEST_TIMEOUT = 300      # LLM 요청 타임아웃 (5분, 기본값)
TUNING_POOL_COMMAND_TIMEOUT = 30  # 대상 DB 개별 쿼리 타임아웃 (30초)
```

#### Agent 선택 우선순위

| 조건 | Agent | 근거 |
|------|-------|------|
| `ANTHROPIC_API_KEY` 설정됨 | **NativeToolAgent** (Claude Tool Use) | 구조화된 tool_use, 8개 도구(7진단+query_database) |
| API Key 없음 | **DBTuningAgent** (LangChain ReAct) | Ollama/OpenAI 등 LangChain 호환 LLM |

- NativeToolAgent는 `settings.AI_MODEL`에 설정된 Claude 모델 사용
- ReAct 폴백 시 `LLMProviderManager`가 설정된 provider/model 자동 선택
- 양쪽 모두 동일한 7개 db_tools 함수 + query_database 공유

---

## 5. 안전 장치

| 규칙 | 구현 |
|------|------|
| **읽기 전용** | 모든 Tool의 DB 쿼리는 read-only 커넥션 사용 |
| **statement_timeout** | Tool 쿼리 `TUNING_POOL_COMMAND_TIMEOUT` (기본 30초) |
| **LLM 타임아웃** | `TUNING_REQUEST_TIMEOUT` (기본 300초 = 5분) |
| **Agent 반복 제한** | max_iterations (기본 5, 최대 10) |
| **실행 금지** | Tool은 분석/추천만, 직접 ALTER/CREATE/DROP 실행 금지 |
| **Autonomy Level** | 추천만 제공 (Level 1), 실행은 사용자 승인 필요 |

---

## 6. 인수 기준

- [ ] AC-1: POST /api/v1/tuning/analyze에서 자연어 질의로 분석 결과 반환
- [ ] AC-2: 7개 Tool이 모두 정상 동작 (각 Tool 개별 테스트)
- [ ] AC-3: Agent가 질의에 따라 적절한 Tool을 자동 선택
- [ ] AC-4: 추천 액션에 실행 가능한 SQL 포함
- [ ] AC-5: 모든 Tool 쿼리가 read-only (write 시도 시 에러)
- [ ] AC-6: max_iterations 초과 시 중간 결과 반환 + 경고
- [ ] AC-7: LLMProviderManager를 통해 현재 설정된 LLM 사용
- [ ] AC-8: GET /api/v1/tuning/history에서 분석 이력 조회 가능

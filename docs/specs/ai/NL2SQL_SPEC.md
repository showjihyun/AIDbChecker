# Feature Spec: NL2SQL — 자연어 DB 질의 시스템

## 메타데이터
- **Spec ID**: FS-AI-NL2SQL-001
- **PRD 참조**: FR-AI-003, MVP-AI-004, MVP-AI-005
- **우선순위**: P0 (MVP)
- **상태**: Implemented (v0.6.0)
- **선행 Spec**: FS-AI-LLM-001 (LLM Provider), DM-001 (ERD)
- **구현 파일**:
  - Backend: `backend/app/services/nl2sql.py`, `backend/app/api/v1/nl2sql.py`
  - Frontend: `frontend/src/components/nl2sql/NL2SQLChat.tsx`
  - Test: `backend/tests/unit/test_nl2sql_spec.py`
  - Skill: `.claude/skills/gen-nl2sql/SKILL.md`

---

## 1. 개요

사용자가 자연어로 질문하면 LLM이 PostgreSQL SELECT 쿼리로 변환하고, 읽기 전용으로 실행하여 결과를 반환하는 시스템. 5계층 안전 장치로 write/injection을 완전 차단합니다.

---

## 2. 아키텍처

```
사용자 질의: "오늘 가장 느린 쿼리 5개 보여줘"
    ↓
┌─ Layer 1: LLM SQL 생성 ─────────────────────────┐
│  System Prompt (§3.1)                             │
│  + Schema Context (시스템 테이블 구조)              │
│  + Question                                       │
│  → LLM (Ollama/OpenAI/Claude/Gemini)             │
│  → Raw SQL output                                 │
└───────────────────────────────────────────────────┘
    ↓
┌─ Layer 2: SQL 정제 ──────────────────────────────┐
│  _clean_sql(): markdown 펜스 제거, 세미콜론 제거   │
└───────────────────────────────────────────────────┘
    ↓
┌─ Layer 3: 5계층 안전 검증 (§4) ──────────────────┐
│  ① Write 키워드 차단 (INSERT/UPDATE/DELETE/DROP...) │
│  ② 위험 함수 차단 (pg_read_file, dblink...)       │
│  ③ 민감 테이블 차단 (users, audit_logs...)        │
│  ④ Multi-statement 차단 (세미콜론)                │
│  ⑤ SELECT/WITH 강제 (첫 키워드 검증)              │
└───────────────────────────────────────────────────┘
    ↓
┌─ Layer 4: 읽기 전용 실행 ────────────────────────┐
│  SET LOCAL default_transaction_read_only = on     │
│  SET LOCAL statement_timeout = '5000'             │
│  LIMIT 1000 rows                                  │
└───────────────────────────────────────────────────┘
    ↓
┌─ Layer 5: 결과 반환 + 이력 저장 ─────────────────┐
│  NL2SQLQueryResponse (sql, columns, rows, time)   │
│  nl2sql_histories 테이블에 저장                    │
└───────────────────────────────────────────────────┘
```

---

## 3. LLM 프롬프트 설계

### 3.1 System Prompt

```
You are a PostgreSQL SQL expert for NeuralDB monitoring system.
Convert the user's natural language question into a single read-only SQL query.

RULES:
- Generate ONLY SELECT statements. NEVER generate INSERT, UPDATE, DELETE, DROP, ALTER.
- Use PostgreSQL 16 syntax.
- Always include reasonable LIMIT (default 100).
- Use explicit column names instead of SELECT *.
- Return ONLY the SQL query, no explanations or markdown.
```

### 3.2 Schema Context

시스템 DB의 주요 테이블 구조를 프롬프트에 포함:

| 테이블 | 주요 컬럼 | NL2SQL 쿼리 대상 |
|--------|----------|-----------------|
| `db_instances` | name, host, port, environment | ✅ |
| `metric_samples` | instance_id, sampled_at, category, metrics(JSONB) | ✅ |
| `active_sessions` | instance_id, pid, query, wait_event, duration_ms | ✅ |
| `incidents` | severity, status, title, detected_at | ✅ |
| `baselines` | metric_type, normal_min, normal_max, mean | ✅ |
| `schema_changes` | change_type, object_name, detected_at | ✅ |
| `users` | — | ❌ 차단 |
| `audit_logs` | — | ❌ 차단 |

### 3.3 쿼리 대상 DB

| Phase | 쿼리 대상 | 설명 |
|-------|----------|------|
| **MVP (현재)** | 시스템 DB | NeuralDB 자체 메타/메트릭 테이블 |
| **Phase 3** | 대상 DB | 모니터링 대상 PostgreSQL에 직접 쿼리 |

> MVP에서는 `instance_id`로 특정 인스턴스의 데이터를 필터링합니다.
> Phase 3에서는 adapter를 통해 대상 DB에 직접 SELECT를 실행합니다.

---

## 4. 5계층 안전 장치

### 4.1 Layer 1 — Write 키워드 차단

```python
_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|"
    r"COPY|VACUUM|REINDEX|CLUSTER|COMMENT|LOCK|DISCARD|REASSIGN|"
    r"DO|EXECUTE|CALL|PERFORM)\b",
    re.IGNORECASE,
)
```

### 4.2 Layer 2 — 위험 함수 차단

```python
_DANGEROUS_FUNCTIONS = re.compile(
    r"\b(pg_read_file|pg_read_binary_file|pg_stat_file|lo_get|lo_export|"
    r"dblink|pg_execute_server_program|query_to_xml|xpath)\b",
    re.IGNORECASE,
)
```

### 4.3 Layer 3 — 민감 테이블 차단

```python
_BLOCKED_TABLES = re.compile(
    r"\b(users|audit_logs|alert_channels|alert_policies|rag_documents)\b",
    re.IGNORECASE,
)
```

### 4.4 Layer 4 — Multi-statement 차단

세미콜론이 포함된 SQL은 거부 (연쇄 SQL injection 방지).

### 4.5 Layer 5 — SELECT/WITH 강제

첫 키워드가 `SELECT` 또는 `WITH` (CTE)가 아니면 거부.

### 4.6 실행 시 안전장치

| 설정 | 값 | 목적 |
|------|-----|------|
| `default_transaction_read_only` | `on` | DB 레벨 write 차단 |
| `statement_timeout` | `5000` (5초) | 무한 실행 방지 |
| max_rows | 1000 | 결과 크기 제한 |

---

## 5. API 엔드포인트

### 5.1 구현 완료

| Method | Path | Auth | 상태 |
|--------|------|------|------|
| POST | `/api/v1/nl2sql/query` | operator+ | ✅ 구현 |

### 5.2 미구현 (Phase 2+)

| Method | Path | Auth | 설명 | Phase |
|--------|------|------|------|-------|
| POST | `/api/v1/nl2sql/explain` | operator+ | EXPLAIN ANALYZE 자연어 해석 | Phase 2 |
| POST | `/api/v1/nl2sql/optimize` | operator+ | SQL 최적화 제안 | Phase 2 |
| GET | `/api/v1/nl2sql/history` | operator+ | 질의 이력 조회 | Phase 2 |
| POST | `/api/v1/nl2sql/feedback` | operator+ | 결과 정확도 피드백 (👍/👎) | Phase 2 |

### 5.3 Request / Response

```python
# POST /api/v1/nl2sql/query
class NL2SQLQueryRequest(BaseModel):
    question: str           # 자연어 질문 (3~1000자)
    instance_id: UUID       # 대상 인스턴스 (메트릭 필터링용)

class NL2SQLQueryResponse(BaseModel):
    sql: str                # 생성된 SQL
    result_rows: list[list] # 실행 결과 행
    result_columns: list[str] # 컬럼명
    execution_time_ms: int  # 실행 시간
    ai_model: str           # 사용 LLM 모델
    warning: str | None     # 경고 (결과 잘림 등)
```

---

## 6. 프론트엔드 — NL2SQL Chat Widget

### 6.1 위치

대시보드 우하단 플로팅 💬 버튼 → 400px 채팅 패널

### 6.2 기능

| 기능 | 상태 |
|------|------|
| 자연어 입력 → SQL 생성 → 결과 테이블 | ✅ |
| 세션 히스토리 (최근 5건) | ✅ |
| 인스턴스 자동 선택 (Dashboard 선택 연동) | ✅ |
| AI 모델명 + 실행시간 표시 | ✅ |
| 인스턴스 미선택 시 안내 메시지 | ✅ |
| 결과 행 수 제한 (20행 표시, 전체 수 표기) | ✅ |
| EXPLAIN 해석 버튼 | ❌ Phase 2 |
| SQL 최적화 제안 버튼 | ❌ Phase 2 |
| 👍/👎 피드백 버튼 | ❌ Phase 2 |

### 6.3 에러 처리

| 에러 | 표시 메시지 |
|------|-----------|
| 인스턴스 미선택 | "인스턴스를 먼저 선택하세요" |
| Write SQL 감지 | "Only SELECT queries are allowed." |
| 위험 함수 감지 | "Generated SQL contains restricted functions." |
| 민감 테이블 접근 | "Generated SQL references restricted tables." |
| LLM 호출 실패 | "SQL execution failed. Try rephrasing your question." |
| 타임아웃 (5초) | "SQL execution failed." |

---

## 7. 데이터 모델

### 7.1 nl2sql_histories 테이블

```sql
CREATE TABLE nl2sql_histories (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    instance_id UUID REFERENCES db_instances(id),
    natural_query TEXT NOT NULL,
    generated_sql TEXT NOT NULL,
    execution_result JSONB,      -- {rows: N, columns: [...]}
    is_correct BOOLEAN,          -- 사용자 피드백
    ai_model VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 8. 예시 질의 + 기대 SQL

| 자연어 질의 | 기대 SQL |
|-----------|---------|
| "현재 등록된 인스턴스 보여줘" | `SELECT name, host, port, environment FROM db_instances WHERE deleted_at IS NULL LIMIT 100` |
| "오늘 발생한 critical 인시던트" | `SELECT title, severity, detected_at FROM incidents WHERE severity = 'critical' AND detected_at >= CURRENT_DATE LIMIT 100` |
| "가장 오래 실행 중인 쿼리" | `SELECT pid, query, duration_ms FROM active_sessions WHERE state = 'active' ORDER BY duration_ms DESC LIMIT 10` |
| "neuraldb-system의 최근 메트릭" | `SELECT sampled_at, metrics FROM metric_samples WHERE instance_id = '...' ORDER BY sampled_at DESC LIMIT 10` |

---

## 9. LLM 프로바이더별 최적화

| Provider | 특이사항 | 권장 설정 |
|----------|---------|----------|
| **Ollama** | 로컬, 느림 (2-10초), 정확도 중간 | temperature=0, max_tokens=500 |
| **OpenAI** | 빠름 (<2초), 정확도 높음 | gpt-4o, temperature=0 |
| **Anthropic** | 빠름, SQL 생성 정확도 매우 높음 | claude-sonnet-4-20250514, temperature=0 |
| **Google** | 빠름, 가끔 markdown 펜스 포함 | gemini-2.0-flash, temperature=0 |

모든 프로바이더에서 `_clean_sql()`이 markdown 펜스를 자동 제거합니다.

---

## 10. 인수 기준

- [ ] AC-1: POST /api/v1/nl2sql/query에서 자연어 → SQL → 결과 반환
- [ ] AC-2: Write 키워드 (INSERT/DELETE/DROP) 포함 SQL 생성 시 400 에러
- [ ] AC-3: 위험 함수 (pg_read_file, dblink) 포함 시 400 에러
- [ ] AC-4: 민감 테이블 (users, audit_logs) 접근 시 400 에러
- [ ] AC-5: statement_timeout 5초 적용 확인
- [ ] AC-6: 결과 1000행 제한 + 초과 시 warning 메시지
- [ ] AC-7: nl2sql_histories 테이블에 질의 이력 저장
- [ ] AC-8: LLMProviderManager를 통해 현재 설정된 LLM 사용
- [ ] AC-9: 프론트엔드에서 instance_id 전달 + 미선택 시 안내
- [ ] AC-10: AI 모델명 + 실행시간이 결과에 표시

---

## 11. Phase 2 확장 계획

| 기능 | 설명 | 의존성 |
|------|------|--------|
| EXPLAIN 해석 | SQL 실행 계획을 자연어로 설명 | Tuning Agent tools |
| SQL 최적화 | 느린 쿼리의 개선안 제안 | index_recommendations tool |
| 대상 DB 직접 쿼리 | adapter를 통해 모니터링 대상에 SELECT | Adapter pool 연동 |
| 피드백 학습 | 👍/👎 → Few-shot 예시 자동 추가 | RAG pipeline |
| 질의 이력 API | GET /nl2sql/history + 검색/필터 | nl2sql_histories 테이블 |

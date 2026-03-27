# Feature Spec: DBA Agent Execution Layer (Tier 1)

## 메타데이터
- **Spec ID**: FS-DBA-001
- **PRD 참조**: FR-AUTO-001~005, FR-AI-012 (Copilot)
- **우선순위**: P0 (DBA Agent 핵심)
- **상태**: Approved
- **선행 Spec**: AG-001 (Agent Architecture), FS-AUTO-002 (Adaptive Autonomy), FS-AI-012 (Copilot)
- **참조**: `docs/etc/DBA Agent 기능.txt` (Agent Harness Engineering 원칙)
- **구현 파일**:
  - Engine: `backend/app/agents/execution_engine.py`
  - Tools: `backend/app/agents/tools/ops_tools.py`
  - Safety: `backend/app/agents/safety_guard.py`
  - API: `backend/app/api/v1/agent_actions.py`
  - Test: `backend/tests/unit/test_dba_001_spec.py`

---

## 1. 개요

DBA Agent가 "분석 → 추천"에서 멈추지 않고, **"추천 → 승인 → 실행 → 검증 → 보고"** 전체 루프를 완성하는 실행 레이어.

> **핵심 원칙 (DBA Agent 기능.txt):**
> - LLM 20%, Harness 80%
> - LLM이 직접 SQL을 실행하면 안 됨 → Execution Engine을 통해서만 실행
> - 모든 쓰기 작업은 Risk Classification + Autonomy Gate 통과 필수

```
현재:  감지 → 분석 → 추천 → (여기서 끝)
목표:  감지 → 분석 → 추천 → [승인] → 실행 → 검증 → 보고
                              ↑ E3       ↑ E1    ↑ E4    ↑ E4
```

---

## 2. E1: Execution Engine

### 2.1 아키텍처

```
Agent (Copilot/Tuning)
    ↓ ActionRequest
Safety Guard (E3)
    ↓ RiskLevel + Policy Decision
    ├─ SAFE      → 즉시 실행
    ├─ WARNING   → 로그 + 실행
    ├─ DANGEROUS → Human Approval 필요
    └─ CRITICAL  → 차단 (실행 불가)
    ↓
Execution Engine
    ├─ Pre-check: EXPLAIN cost estimate
    ├─ Execute: statement_timeout 적용
    ├─ Post-check: 결과 검증
    └─ Audit: AI Decision Log 기록
    ↓
Result → Agent → User
```

### 2.2 ActionRequest / ActionResult

```python
# Spec: FS-DBA-001
class ActionRequest(BaseModel):
    """Agent가 실행을 요청하는 구조체."""
    instance_id: UUID
    action_type: str          # "create_index" | "vacuum" | "kill_session" | "alter_param" | "reindex" | "custom_sql"
    sql: str                  # 실행할 SQL
    description: str          # 사람이 읽을 수 있는 설명
    risk_level: str           # Safety Guard가 판정
    estimated_impact: str     # "이 인덱스 생성 시 ~2분 소요, 테이블 락 없음 (CONCURRENTLY)"
    requires_approval: bool
    requested_by: str         # "agent-tuning" | "agent-copilot" | "user"
    confidence: float         # 0.0~1.0

class ActionResult(BaseModel):
    """실행 결과."""
    action_id: UUID
    status: str               # "executed" | "approved" | "rejected" | "failed" | "rolled_back"
    execution_time_ms: int | None
    rows_affected: int | None
    before_state: dict | None # 실행 전 상태 (EXPLAIN cost 등)
    after_state: dict | None  # 실행 후 상태
    error: str | None
```

### 2.3 Execution Engine 구현

```python
# backend/app/agents/execution_engine.py
class ExecutionEngine:
    """DBA Agent의 안전한 SQL 실행 엔진.

    모든 쓰기 작업은 이 엔진을 통해서만 실행됨.
    직접 SQL 실행 금지 (AGENTS.md §3.7).
    """

    async def execute(self, request: ActionRequest, session, pool) -> ActionResult:
        """실행 파이프라인: classify → gate → pre-check → execute → post-check → audit."""

    async def _pre_check(self, pool, sql: str) -> dict:
        """EXPLAIN으로 예상 cost/rows 확인."""

    async def _execute_with_timeout(self, pool, sql: str, timeout_sec: int = 30) -> tuple:
        """statement_timeout 적용 실행."""

    async def _post_check(self, pool, action_type: str) -> dict:
        """실행 후 상태 확인 (인덱스 유효성, vacuum 결과 등)."""

    async def _audit_log(self, session, request, result) -> None:
        """AI Decision Log에 기록."""
```

---

## 3. E2: Ops Tools (쓰기 Tool 5개)

### 3.1 Tool 목록

| Tool | SQL | Risk Level | Autonomy 최소 | 비고 |
|------|-----|-----------|-------------|------|
| `create_index` | `CREATE INDEX CONCURRENTLY ...` | WARNING | L1 (추천) / L2 (실행) | 무중단. CONCURRENTLY 강제 |
| `vacuum_table` | `VACUUM (VERBOSE) table` | WARNING | L2 | Full Vacuum은 DANGEROUS |
| `vacuum_full` | `VACUUM FULL table` | DANGEROUS | L2 + approval | 테이블 락 발생 |
| `kill_session` | `SELECT pg_terminate_backend(pid)` | DANGEROUS | L2 + approval | 세션 강제 종료 |
| `alter_parameter` | `ALTER SYSTEM SET param = value` | DANGEROUS | L2 + approval | DB 파라미터 변경 |
| `reindex` | `REINDEX INDEX CONCURRENTLY ...` | WARNING | L2 | 무중단 |
| `analyze_table` | `ANALYZE table` | SAFE | L1 | 통계 갱신 (읽기에 가까움) |

### 3.2 Tool 인터페이스

```python
# backend/app/agents/tools/ops_tools.py

async def create_index(
    pool, table: str, columns: list[str], index_name: str | None = None
) -> ActionRequest:
    """CREATE INDEX CONCURRENTLY 생성 요청을 반환.

    직접 실행하지 않음 — ActionRequest를 반환하여 ExecutionEngine이 처리.
    """

async def vacuum_table(pool, table: str, full: bool = False) -> ActionRequest:
    """VACUUM 요청. full=True면 DANGEROUS 등급."""

async def kill_session(pool, pid: int, reason: str) -> ActionRequest:
    """pg_terminate_backend 요청."""

async def alter_parameter(pool, param: str, value: str) -> ActionRequest:
    """ALTER SYSTEM SET 요청."""

async def reindex(pool, index_name: str) -> ActionRequest:
    """REINDEX CONCURRENTLY 요청."""

async def analyze_table(pool, table: str) -> ActionRequest:
    """ANALYZE 요청 (SAFE 등급)."""
```

**핵심**: ops_tools는 SQL을 직접 실행하지 않음. `ActionRequest`를 반환하고, `ExecutionEngine`이 Safety Guard를 거쳐 실행.

---

## 4. E3: SQL Risk Classifier (4단계)

### 4.1 분류 체계

| Level | 이름 | 기준 | 정책 |
|-------|------|------|------|
| **SAFE** | 안전 | SELECT, EXPLAIN, ANALYZE (통계) | 즉시 실행 |
| **WARNING** | 주의 | CREATE INDEX CONCURRENTLY, REINDEX CONCURRENTLY, VACUUM | 로그 후 실행 |
| **DANGEROUS** | 위험 | VACUUM FULL, pg_terminate_backend, ALTER SYSTEM, UPDATE, DELETE (조건부) | **Human Approval 필수** |
| **CRITICAL** | 금지 | DROP TABLE, DROP DATABASE, TRUNCATE, DELETE (WHERE 없음) | **차단 (실행 불가)** |

### 4.2 분류 규칙

```python
# backend/app/agents/safety_guard.py

class SafetyGuard:
    """SQL Risk Classifier + Policy Engine.

    Spec: FS-DBA-001 E3 — 4단계 위험 분류.
    """

    def classify_risk(self, sql: str, action_type: str) -> RiskLevel:
        """SQL + action_type 기반 위험도 분류."""

    def check_policy(self, risk: RiskLevel, autonomy_level: int, confidence: float) -> PolicyDecision:
        """위험도 + 자율등급 + 신뢰도 → 실행 정책 결정.

        Returns: "execute" | "approve" | "block"
        """

class RiskLevel(str, Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGEROUS = "dangerous"
    CRITICAL = "critical"

class PolicyDecision(BaseModel):
    action: str             # "execute" | "approve_required" | "blocked"
    reason: str             # 사람이 읽을 수 있는 설명
    risk_level: RiskLevel
```

### 4.3 Policy Matrix

| Risk Level | Autonomy L0 | L1 | L2 | L3 | L4 |
|-----------|------------|-----|-----|-----|-----|
| SAFE | execute | execute | execute | execute | execute |
| WARNING | block | recommend | execute | execute | execute |
| DANGEROUS | block | recommend | **approve** | execute+report | execute |
| CRITICAL | block | block | block | block | **approve** |

---

## 5. E4: Agent Action API + Approval Flow

### 5.1 API 엔드포인트

| Method | Path | Auth | 설명 |
|--------|------|------|------|
| GET | `/api/v1/agent/actions` | JWT (Operator+) | 대기 중인 Action 목록 |
| GET | `/api/v1/agent/actions/{id}` | JWT (Operator+) | Action 상세 (SQL, risk, impact) |
| POST | `/api/v1/agent/actions/{id}/approve` | JWT (DB Admin+) | Action 승인 → 실행 |
| POST | `/api/v1/agent/actions/{id}/reject` | JWT (DB Admin+) | Action 거부 |
| GET | `/api/v1/agent/actions/history` | JWT (Operator+) | 실행 완료 이력 |

### 5.2 Approval Flow

```
Agent 분석 완료
    ↓
ActionRequest 생성 (ops_tool 반환)
    ↓
Safety Guard → classify_risk + check_policy
    ↓
┌─ "execute" → Execution Engine → 즉시 실행 → ActionResult
│
├─ "approve_required" → DB에 pending action 저장
│   ↓
│   UI에 승인 대기 배지 표시
│   ↓
│   DBA가 /approve 또는 /reject
│   ↓
│   approve → Execution Engine → 실행 → ActionResult
│   reject  → 거부 기록 → 종료
│
└─ "blocked" → 차단 기록 → Agent에게 "실행 불가" 반환
```

---

## 6. 데이터 모델

### `agent_actions` 테이블

```sql
CREATE TABLE agent_actions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id     UUID NOT NULL REFERENCES db_instances(id),
    action_type     VARCHAR(30) NOT NULL,    -- create_index, vacuum, kill_session, ...
    sql_command     TEXT NOT NULL,
    description     TEXT NOT NULL,
    risk_level      VARCHAR(15) NOT NULL,    -- safe, warning, dangerous, critical
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending, approved, rejected, executing, executed, failed, rolled_back
    requested_by    VARCHAR(50) NOT NULL,    -- agent-tuning, agent-copilot, user
    approved_by     UUID REFERENCES users(id),
    confidence      FLOAT,
    estimated_impact TEXT,
    execution_time_ms INT,
    rows_affected   INT,
    before_state    JSONB,
    after_state     JSONB,
    error           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at     TIMESTAMPTZ,
    executed_at     TIMESTAMPTZ
);

CREATE INDEX idx_agent_actions_instance ON agent_actions(instance_id);
CREATE INDEX idx_agent_actions_status ON agent_actions(status) WHERE status IN ('pending', 'executing');
CREATE INDEX idx_agent_actions_created ON agent_actions(created_at DESC);
```

---

## 7. 인수 기준 (Acceptance Criteria)

### E1: Execution Engine

- [ ] **AC-1**: ExecutionEngine.execute()가 ActionRequest를 받아 SQL을 실행하고 ActionResult를 반환
- [ ] **AC-2**: 실행 전 EXPLAIN으로 cost/rows를 pre_check하고 before_state에 기록
- [ ] **AC-3**: 실행 후 post_check로 결과 상태를 after_state에 기록
- [ ] **AC-4**: 모든 실행이 AI Decision Log (audit_logs)에 자동 기록

### E2: Ops Tools

- [ ] **AC-5**: create_index()가 CONCURRENTLY 강제하는 ActionRequest 반환
- [ ] **AC-6**: vacuum_table(full=True)이 DANGEROUS risk_level ActionRequest 반환
- [ ] **AC-7**: kill_session()이 DANGEROUS risk_level ActionRequest 반환
- [ ] **AC-8**: 모든 ops_tools가 SQL을 직접 실행하지 않고 ActionRequest만 반환

### E3: Safety Guard

- [ ] **AC-9**: classify_risk()가 SQL을 SAFE/WARNING/DANGEROUS/CRITICAL 4단계로 분류
- [ ] **AC-10**: DROP TABLE/TRUNCATE가 CRITICAL로 분류되어 모든 Autonomy Level에서 차단
- [ ] **AC-11**: check_policy()가 risk_level + autonomy_level + confidence 조합으로 정책 결정
- [ ] **AC-12**: Confidence < 0.5 시 DANGEROUS 이상 action 차단

### E4: API + Approval

- [ ] **AC-13**: GET /agent/actions에서 pending action 목록 조회 가능
- [ ] **AC-14**: POST /agent/actions/{id}/approve 후 ExecutionEngine이 실행
- [ ] **AC-15**: POST /agent/actions/{id}/reject 후 status가 "rejected"로 변경
- [ ] **AC-16**: agent_actions 테이블에 전체 이력(before/after state) 저장

---

## 8. 의존성

- **선행 Spec**: AG-001, FS-AUTO-002 (Autonomy Level), FS-ADMIN-004 (AI Decision Log)
- **연동 Spec**: FS-AI-012 (Copilot → ActionRequest 생성), FS-AI-TUNE-001 (Tuning → ActionRequest)
- **DB**: `agent_actions` 테이블 (Alembic migration 필요)

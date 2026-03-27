# Feature Spec: DB Copilot (Tree-of-Thought 자율 유지보수)

## 메타데이터
- **Spec ID**: FS-AI-012
- **PRD 참조**: FR-AI-012
- **우선순위**: P1 (Phase 2)
- **상태**: Implemented (Phase 2+3)
- **선행 Spec**: FS-AI-010 (MTL RCA), FS-AI-011 (Confidence Score), FS-AUTO-002 (Adaptive Autonomy)
- **참조**: GaussMaster (arXiv:2506.23322)

---

## 1. 개요

단순 알림/추천을 넘어, LLM이 **Tree-of-Thought(ToT) 추론**으로 수백 개 메트릭과 로그를 체계적으로 분석하여 근본 원인을 식별하고, 적절한 도구를 호출하여 문제를 해결하는 **자율 DB 유지보수 모드**. GaussMaster의 34개+ 자율 유지보수 시나리오를 멀티 DB 환경에서 구현합니다.

> **Phase 2에서 구현 시작**. MVP에서는 MTL Lite + 경량 RCA가 기본 진단을 담당.

---

## 2. Tree-of-Thought 추론 구조

### 2.1 아키텍처

```
트리거 이벤트 (인시던트 / 수동 요청)
    ↓
Context Gathering (메트릭/로그/ASH Top-K, RAG)
    ↓
┌─── Tree-of-Thought 분기 ────────────────────────┐
│                                                   │
│  Branch 1: Query Performance                      │
│  ├── EXPLAIN 분석                                  │
│  ├── Missing Index 감지                            │
│  └── Score: 0.87 ★ ← 최고 점수                     │
│                                                   │
│  Branch 2: Resource Bottleneck                    │
│  ├── CPU/Memory/Disk 분석                          │
│  ├── 파라미터 튜닝 필요 여부                         │
│  └── Score: 0.42                                  │
│                                                   │
│  Branch 3: Lock Contention                        │
│  ├── Deadlock 탐지                                 │
│  ├── Lock Wait Chain 분석                          │
│  └── Score: 0.23                                  │
│                                                   │
│  Branch 4: Replication / HA                       │
│  ├── Replication Lag 분석                          │
│  ├── Failover 필요 여부                             │
│  └── Score: 0.11                                  │
│                                                   │
└───────────────────────────────────────────────────┘
    ↓
Best Path 선택 (Score 최고 + Risk 최저)
    ↓
Autonomy Level 확인 → 실행 / 추천 / 알림
```

### 2.2 분기 정의

| Branch | 트리거 조건 | 분석 도구 | 가능한 액션 |
|--------|-----------|----------|-----------|
| **Query Performance** | slow_query, plan_regression, high_cpu | `analyze_query_plan`, `search_similar_incidents` | CREATE INDEX, REWRITE SQL, ANALYZE TABLE |
| **Resource Bottleneck** | cpu>90%, memory>90%, disk_full | `get_system_metrics`, `get_parameter_recommendations` | ALTER SYSTEM SET, VACUUM FULL |
| **Lock Contention** | deadlock, long_lock_wait | `get_lock_chains`, `get_blocking_sessions` | pg_terminate_backend, SET lock_timeout |
| **Replication / HA** | replication_lag>30s, primary_down | `get_replication_status`, `check_failover_readiness` | PROMOTE STANDBY, RESTART REPLICATION |
| **Vacuum / Bloat** | high_dead_tuples, table_bloat>30% | `get_vacuum_status`, `get_bloat_stats` | VACUUM ANALYZE, REINDEX CONCURRENTLY |
| **Connection** | conn>90%_max, connection_leak | `get_connection_stats`, `get_idle_connections` | pg_terminate_backend (idle), SET max_connections |
| **Schema Regression** | ddl_change + perf_degradation | `get_schema_changes`, `compare_before_after` | ROLLBACK DDL, CREATE INDEX |
| **Security** | unauthorized_access, privilege_escalation | `get_failed_logins`, `get_privilege_changes` | REVOKE, ALTER USER, alert only |

### 2.3 경로 점수 계산

```python
# Spec: FR-AI-012
class BranchScore(BaseModel):
    branch_name: str
    relevance_score: float   # 0.0~1.0: 현재 상황과의 관련성
    evidence_strength: float # 0.0~1.0: 근거 데이터 강도
    action_confidence: float # 0.0~1.0: 추천 액션 신뢰도
    risk_penalty: float      # 0.0~0.5: 액션 위험도 감산

    @property
    def final_score(self) -> float:
        """최종 점수 = (관련성×0.4 + 근거×0.3 + 액션신뢰×0.3) - 위험감산"""
        base = (self.relevance_score * 0.4 +
                self.evidence_strength * 0.3 +
                self.action_confidence * 0.3)
        return round(max(base - self.risk_penalty, 0.0), 3)
```

---

## 3. 인터페이스 계약

### 3.1 API 엔드포인트

#### Copilot 진단 실행
- **Method**: POST
- **Path**: `/api/v1/copilot/diagnose`
- **Auth**: JWT (DB Admin 이상)
- **Request**:

```python
# Spec: FR-AI-012
class CopilotDiagnoseRequest(BaseModel):
    instance_id: UUID
    incident_id: UUID | None = None  # 특정 인시던트 또는 수동 트리거
    max_branches: int = Field(default=4, ge=2, le=8)
    auto_execute: bool = False  # True면 Autonomy Level 확인 후 자동 실행
```

- **Response**:

```python
# Spec: FR-AI-012
class CopilotDiagnoseResponse(BaseModel):
    session_id: UUID
    instance_id: UUID
    branches_explored: int
    selected_branch: str
    branch_scores: list[BranchScore]

    # 선택된 경로의 MTL 결과
    diagnosis: MTLPredictResponse  # FS-AI-010 참조

    # Copilot 메타
    total_inference_time_ms: int
    total_tokens_used: int
    autonomy_level_applied: int
    execution_status: str  # "recommended" | "awaiting_approval" | "executed" | "blocked"
```

#### Copilot 액션 실행 (승인 후)
- **Method**: POST
- **Path**: `/api/v1/copilot/sessions/{session_id}/execute`
- **Auth**: JWT (DB Admin 이상, Autonomy L2+ 필요)

#### Copilot 세션 이력 조회
- **Method**: GET
- **Path**: `/api/v1/copilot/sessions`
- **Query Params**: `instance_id`, `from`, `to`, `limit`

### 3.2 데이터 모델

```sql
-- Spec: FR-AI-012
CREATE TABLE copilot_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id     UUID NOT NULL REFERENCES db_instances(id),
    incident_id     UUID REFERENCES incidents(id),
    prediction_id   UUID REFERENCES mtl_predictions(id),

    branches_explored INT NOT NULL,
    selected_branch   VARCHAR(50) NOT NULL,
    branch_scores     JSONB NOT NULL,  -- [{"branch_name": "...", "final_score": 0.87}]

    autonomy_level    INT NOT NULL,
    execution_status  VARCHAR(20) NOT NULL,  -- recommended/awaiting_approval/executed/blocked
    executed_actions  JSONB,  -- 실행된 액션 목록
    execution_result  JSONB,  -- 실행 결과 (success/failure, before/after metrics)

    total_inference_time_ms INT,
    total_tokens_used       INT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    executed_at     TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_copilot_sessions_instance ON copilot_sessions(instance_id);
CREATE INDEX idx_copilot_sessions_created ON copilot_sessions(created_at);
```

---

## 4. 대상 유지보수 시나리오 (34개 목표)

### Phase 2 (12개)
1. Missing Index → CREATE INDEX CONCURRENTLY
2. Seq Scan 제거 → 인덱스 추천 + 쿼리 리라이트
3. High CPU → work_mem / shared_buffers 튜닝
4. Connection Saturation → idle 세션 정리
5. Long Running Query → pg_cancel_backend
6. Deadlock 해소 → 블로킹 세션 킬
7. Table Bloat → VACUUM FULL / pg_repack 추천
8. Replication Lag → WAL 설정 조정
9. Parameter Misconfiguration → ALTER SYSTEM SET
10. DDL Regression → 롤백 추천
11. High WAL Generation → checkpoint_timeout 조정
12. Temp File Overflow → work_mem 증가

### Phase 3 (12개)
13~24: 복합 장애, 크로스 스택 분석, 자동 페일오버 등

### Phase 4 (10개)
25~34: MySQL/MSSQL 전용 시나리오

---

## 5. Playbook 하이브리드 연동 (ADR-008)

> DB Copilot과 Built-in Playbook은 위험 수준에 따라 역할을 분담합니다.

### 5.1 역할 분담

| 위험 수준 | 주 담당 | 보조 | 예시 |
|----------|---------|------|------|
| **고위험** (DDL, 파라미터 변경) | Built-in Playbook | Copilot이 Playbook 추천 | CREATE INDEX, ALTER SYSTEM |
| **중위험** (세션 kill, VACUUM) | DB Copilot 판단 | Playbook 절차 참조 | pg_terminate_backend, VACUUM |
| **저위험** (조회, 분석, 추천) | DB Copilot 자유 실행 | - | EXPLAIN, pg_stat 조회 |

### 5.2 Copilot → Playbook 연동 흐름

```python
# Spec: FR-AI-012, FR-AUTO-003 (Lite)
async def copilot_diagnose_with_playbook(
    instance_id: UUID,
    incident_id: UUID,
) -> CopilotDiagnoseResponse:
    """DB Copilot 진단 후 Playbook 매칭"""

    # 1. ToT 분기 분석
    diagnosis = await tree_of_thought(instance_id, incident_id)

    # 2. Built-in Playbook 매칭
    matched_playbook = match_builtin_playbook(
        anomaly_type=diagnosis.anomaly_type,
        risk_level=diagnosis.risk_level,
    )

    if matched_playbook:
        # 고위험: Playbook 추천/실행
        diagnosis.recommended_playbook = matched_playbook.name
        diagnosis.execution_status = "playbook_recommended"
    else:
        # Playbook 없는 신규 패턴: Copilot 추천만
        diagnosis.execution_status = "copilot_recommended"
        # Phase 3: 반복 패턴 → Playbook 승격 후보로 기록
        await record_playbook_candidate(diagnosis)

    return diagnosis
```

### 5.3 Playbook 승격 경로 (Phase 3 준비)

DB Copilot이 동일 패턴을 **3회 이상** 추천한 경우, 해당 패턴을 `playbook_candidates` 로그에 기록합니다. Phase 3에서 운영자가 이를 검토하여 커스텀 Playbook으로 승격할 수 있습니다.

```
Copilot 추천 패턴 반복 (≥3회)
    → playbook_candidates에 기록
    → Phase 3: 운영자 검토 → 커스텀 Playbook YAML 생성
```

---

## 6. 인수 기준 (Acceptance Criteria)

- [ ] **AC-1**: POST `/api/v1/copilot/diagnose` 호출 시 최소 2개 이상 Branch 탐색 결과 반환
- [ ] **AC-2**: 각 Branch에 `final_score`가 계산되어 최고 점수 경로가 `selected_branch`로 선택
- [ ] **AC-3**: `auto_execute: true` 시 Autonomy Level 확인 후 적절히 실행/차단
- [ ] **AC-4**: Confidence < 0.5인 경우 `execution_status: "blocked"` 반환
- [ ] **AC-5**: Phase 2 완료 시 12개 시나리오 중 10개 이상 자동 진단 가능
- [ ] **AC-6**: `copilot_sessions` 테이블에 전체 세션 이력 저장
- [ ] **AC-7**: 진단 결과에 매칭 Built-in Playbook이 있으면 `recommended_playbook` 필드에 포함
- [ ] **AC-8**: Playbook 없는 신규 패턴의 경우 `execution_status: "copilot_recommended"` 반환

---

## 7. 의존성

- **선행 Spec**: FS-AI-010 (MTL), FS-AI-011 (Confidence), FS-AUTO-002 (Autonomy)
- **사용 Spec**: FS-AI-RAG-001 (RAG 검색), FS-AUTO-003 (Playbook Lite — Built-in 매칭/실행)
- **ADR**: ADR-008 (경량 Playbook + DB Copilot 하이브리드)

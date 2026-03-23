# Agent Spec: NeuralDB Multi-Agent System

> **Spec ID**: AG-001
> **PRD 참조**: FR-AI-001~014, FR-AUTO-001~005, FR-ALERT-005
> **상태**: Approved
> **Frameworks**: LangGraph (상태 그래프), CrewAI (오케스트레이션), LangChain (도구)
> **Protocol**: A2A (Agent-to-Agent), MCP (Model Context Protocol)

---

## 1. Agent Architecture

```
                    ┌──────────────────────────┐
                    │   Task Orchestrator       │
                    │   (Autonomy Level Gate)   │
                    └─────────┬────────────────┘
                              │ A2A Protocol
        ┌─────────────────────┼─────────────────────┐
        │                     │                      │
  ┌─────▼──────┐      ┌──────▼───────┐      ┌──────▼──────────┐
  │ Monitoring  │─────▶│  Diagnosis   │─────▶│  Remediation    │
  │ Agent       │      │  Agent       │      │  Agent          │
  │             │      │              │      │                 │
  │ - Collect   │      │ - RCA        │      │ - Execute       │
  │ - Baseline  │      │ - RAG        │      │ - Rollback      │
  │ - Detect    │      │ - Topology   │      │ - Auto-Tune     │
  └─────────────┘      └──────────────┘      └────────┬────────┘
                                                       │
                                               ┌───────▼────────┐
                                               │  Reporting     │
                                               │  Agent         │
                                               │                │
                                               │ - NL2SQL       │
                                               │ - AIGC Report  │
                                               │ - EXPLAIN 해석  │
                                               └────────────────┘
```

---

## 2. Agent Definitions

### 2.1 Monitoring Agent

| Field | Value |
|-------|-------|
| **ID** | `agent-monitoring` |
| **Role** | 메트릭 수집, 베이스라인 학습, 이상 탐지 |
| **Input** | DB 인스턴스 설정, 수집 스케줄 |
| **Output** | `metric_samples`, `active_sessions`, `incidents` (이상 탐지 시) |
| **Autonomy** | Level 0~4 (탐지는 항상 자동, 알림 발송만 Level 제어) |
| **Framework** | Celery (주기적 수집) + scikit-learn/Prophet (분석) |

**State Machine**:
```
IDLE → COLLECTING → ANALYZING → [NORMAL | ANOMALY_DETECTED]
                                      ↓
                               ALERT_SENT → IDLE
```

**Tools**:
- `collect_metrics(instance_id)` — pg_stat_* 조회
- `collect_ash(instance_id)` — pg_stat_activity 1초 샘플링
- `update_baseline(instance_id, metric_type)` — STL + Isolation Forest
- `detect_anomaly(sample, baseline)` — 동적 임계값 비교

---

### 2.2 Diagnosis Agent

| Field | Value |
|-------|-------|
| **ID** | `agent-diagnosis` |
| **Role** | 근본 원인 분석 (RCA), 토폴로지 인식 영향도 분석, **MTL 통합 추론, Tree-of-Thought 진단** |
| **Input** | `incident` (Monitoring Agent가 A2A로 전달) |
| **Output** | `rca_results` |
| **Autonomy** | Level 0~4 (분석은 항상 자동, 추천 액션만 Level 제어) |
| **Framework** | LangGraph (상태 그래프) + RAG (pgvector) + **PyTorch (MTL, Phase 2+)** |

**State Machine**:
```
RECEIVED → GATHERING_CONTEXT → RAG_SEARCH → MTL_INFERENCE
    → [ANOMALY_TYPE + ROOT_CAUSE + SEVERITY + ACTIONS]
    → CONFIDENCE_CHECK → TOPOLOGY_IMPACT → RCA_COMPLETE
    → [RECOMMEND | AUTO_REMEDIATE]
```

**Tools**:
- `search_similar_incidents(description)` — pgvector RAG 검색
- `get_topology_impact(node_id)` — 업/다운스트림 영향 범위
- `analyze_query_plan(sql)` — EXPLAIN ANALYZE 실행 및 해석
- `get_schema_changes(instance_id, time_range)` — 최근 DDL 변경 조회
- `llm_rca(context)` — LLM 기반 근본 원인 추론
- `mtl_inference(context)` — MTL 4-Head 동시 추론 (이상분류/원인/심각도/액션). Phase 1: LLM Few-shot, Phase 2+: Transformer
- `tree_of_thought(trigger_event, metrics, logs)` — ToT 다중 진단 경로 탐색 (DB Copilot 모드)
- `compute_confidence(predictions)` — 각 Head의 Confidence Score 계산 + 종합 신뢰도

**Output Format (Explainable AI)**:
모든 진단 결과는 다음 필드를 필수 포함:
- `anomaly_type`: 이상 유형 분류 (MTL Head 1)
- `root_cause`: 근본 원인 식별 (MTL Head 2)
- `severity`: 심각도 점수 0.0~1.0 (MTL Head 3)
- `suggested_actions`: 추천 액션 리스트 (MTL Head 4)
- `confidence`: 종합 Confidence Score (0.0~1.0)
- `reasoning_chain`: 추론 과정 단계별 설명 리스트
- `evidence_links`: 근거 데이터 API 링크 리스트

---

### 2.3 Remediation Agent

| Field | Value |
|-------|-------|
| **ID** | `agent-remediation` |
| **Role** | 자가 치유 실행, Playbook 실행, 자동 쿼리 튜닝, 롤백 |
| **Input** | `rca_result` + `playbook` (Diagnosis Agent가 A2A로 전달) |
| **Output** | `remediation_logs` |
| **Autonomy** | **Level 제어 핵심 대상** — Level별 행동이 다름 |
| **Framework** | LangGraph (실행 그래프) + CrewAI (멀티 스텝) |

**Autonomy Behavior**:
```
Level 0: 알림만 발송 → 사람이 수동 실행
Level 1: Playbook 추천 표시 → 사람 승인 대기
Level 2: 사람 승인 후 실행 → 결과 보고
Level 3: 자동 실행 → 결과 보고 → 실패 시 자동 롤백
Level 4: 완전 자율 → 에스컬레이션 시에만 사람 개입
```

**State Machine**:
```
RECEIVED → AUTONOMY_CHECK → [WAIT_APPROVAL | EXECUTE]
    EXECUTE → STEP_1 → VALIDATE → STEP_2 → VALIDATE → ...
        → [SUCCESS | FAILURE]
    FAILURE → ROLLBACK → ESCALATE
    SUCCESS → SLO_CHECK → COMPLETE
```

**Tools**:
- `execute_sql(instance_id, sql, timeout)` — SQL 실행 (쓰기 커넥션)
- `create_index_concurrently(instance_id, table, columns)` — 무중단 인덱스 생성
- `kill_session(instance_id, pid)` — 프로세스 종료
- `adjust_parameter(instance_id, param, value)` — DB 파라미터 변경
- `rollback_action(remediation_log_id)` — 롤백 실행
- `check_slo(instance_id, metrics)` — SLO 달성 여부 검증

**Safety Rules (MUST)**:
1. 모든 쓰기 액션 전 `AUTONOMY_CHECK` 필수
2. `blast_radius` 평가 — 영향 범위가 큰 액션은 Level 자동 상향 요구
3. `statement_timeout` 설정 — 무한 실행 방지
4. `dry_run` 모드 지원 — 실제 실행 없이 시뮬레이션
5. 실패 시 **자동 롤백** + Autonomy Level 1단계 격하

---

### 2.4 Reporting Agent

| Field | Value |
|-------|-------|
| **ID** | `agent-reporting` |
| **Role** | NL2SQL, 실행 계획 해석, AIGC 리포트 생성 |
| **Input** | 사용자 자연어 질의, 리포트 생성 요청 |
| **Output** | SQL 결과, 자연어 해석, PDF/HTML 리포트 |
| **Autonomy** | Level 0~4 (읽기 전용이므로 Level 제어 최소) |
| **Framework** | LangChain (SQL Agent + RAG) |

**Tools**:
- `nl2sql(question, instance_id)` — 자연어 → SQL 변환
- `execute_readonly(instance_id, sql)` — 읽기 전용 실행
- `explain_plan(instance_id, sql)` — 실행 계획 자연어 해석
- `optimize_sql(sql)` — SQL 최적화 제안
- `generate_report(instance_id, period, format)` — AI 리포트 생성

---

## 3. Inter-Agent Communication (A2A)

### Message Format
```python
@dataclass
class A2AMessage:
    sender: str          # agent-monitoring
    receiver: str        # agent-diagnosis
    task_type: str       # "diagnose_incident"
    payload: dict        # {incident_id: "uuid", ...}
    priority: int        # 0=low, 1=normal, 2=high, 3=critical
    correlation_id: str  # 추적 ID
    timestamp: datetime
```

### Task Flow
```
Monitoring → (anomaly detected) → A2A → Diagnosis
Diagnosis  → (rca complete)     → A2A → Remediation (if autonomy allows)
Remediation → (action complete) → A2A → Reporting (audit + notification)
```

### gRPC 서비스 인터페이스 (Phase 3)

Phase 3에서 Multi-Agent 전환 시, 각 Agent는 gRPC 서비스를 노출하여 동기 RPC를 지원합니다.

| Agent | gRPC Service | 주요 RPC | 지연 목표 |
|-------|-------------|---------|----------|
| Diagnosis | `DiagnosisService` | `Diagnose`, `CopilotDiagnose`, `SearchSimilar` | < 10s |
| Remediation | `RemediationService` | `ExecutePlaybook`, `Rollback`, `DryRun` | < 30s |
| Reporting | `ReportingService` | `NL2SQL`, `ExplainPlan` | < 5s |
| All | `AgentHealthService` | `Check`, `GetAgentCard` | < 100ms |

#### 통신 경로 선택
```
동기 (gRPC):
  MCP Tool 호출 → gRPC → Agent → 즉시 응답
  Agent → Agent 직접 RPC (RCA 요청, EXPLAIN 분석)

비동기 (Kafka):
  메트릭 수집 → Kafka → 저장 서비스
  인시던트 이벤트 → Kafka → 알림/감사
  Playbook 실행 결과 → Kafka → 보고/로깅
```

#### Proto 파일 위치
```
backend/
├── proto/
│   ├── neuraldb_agents.proto    # 서비스 + 메시지 정의
│   └── buf.gen.yaml             # buf 빌드 설정
├── app/grpc/
│   ├── server.py                # gRPC 서버 시작
│   ├── interceptors.py          # Auth, OTel, Autonomy Gate
│   ├── generated/               # protoc 자동 생성 코드
│   └── servicers/
│       ├── diagnosis.py         # DiagnosisServiceServicer
│       ├── remediation.py       # RemediationServiceServicer
│       ├── reporting.py         # ReportingServiceServicer
│       └── health.py            # AgentHealthServiceServicer
```

---

## 4. MCP Tools (External AI Access)

MCP Server가 외부 AI 도구(Claude Code, Copilot 등)에 노출하는 도구:

| Tool | Read/Write | Description |
|------|-----------|-------------|
| `query_metrics` | Read | 메트릭 조회 |
| `get_active_sessions` | Read | ASH 조회 |
| `list_incidents` | Read | 인시던트 목록 |
| `analyze_query` | Read | 쿼리 분석 |
| `run_diagnosis` | Read | AI 진단 실행 |
| `nl2sql` | Read | 자연어 → SQL |
| `get_topology` | Read | 토폴로지 조회 |
| `execute_playbook` | Write | Playbook 실행 (dry_run 기본) |

---

## 5. LLM Observability

모든 에이전트의 LLM 호출은 다음 메트릭을 자동 수집합니다:

| 메트릭 | 수집 방법 | 알림 기준 |
|--------|----------|----------|
| 토큰 사용량 (input/output) | OpenLIT 자동 계측 | 일 예산 초과 시 WARNING |
| 응답 지연 (P50/P95/P99) | OpenTelemetry span | P95 > 10초 시 WARNING |
| RCA 정확도 | 운영자 피드백 (👍/👎) | 주간 정확도 < 70% 시 재학습 |
| 할루시네이션 비율 | RAG 근거 유무 체크 | > 15% 시 CRITICAL |
| 모델 드리프트 | KL-divergence 모니터링 | 임계값 초과 시 재학습 |
| API 비용 | 모델별 토큰 단가 × 사용량 | 월 예산 80% 시 Offline 전환 권고 |

---

## 6. Agent Configuration

```yaml
# backend/app/agents/config.yaml
agents:
  monitoring:
    collect_interval_hot: 1s
    collect_interval_warm: 10s
    collect_interval_cold: 60s
    baseline_retrain_interval: 6h
    anomaly_sensitivity: 0.95  # Isolation Forest contamination

  diagnosis:
    rag_top_k: 5
    rag_similarity_threshold: 0.7
    llm_model_online: "claude-sonnet-4-20250514"
    llm_model_offline: "mistral:7b"
    max_causal_chain_depth: 5

  remediation:
    default_statement_timeout: "30s"
    max_concurrent_actions: 3
    slo_check_wait: 60s
    auto_rollback_on_failure: true
    autonomy_downgrade_on_failure: true

  reporting:
    nl2sql_max_rows: 1000
    report_formats: ["html", "pdf"]
    llm_model_online: "gpt-4o"
    llm_model_offline: "mistral:7b"
```

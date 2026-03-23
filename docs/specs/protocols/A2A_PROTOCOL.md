# A2A Protocol Spec: Agent-to-Agent 통신 규격

> **Spec ID**: PROTO-A2A-001
> **PRD 참조**: FR-ALERT-005, FR-AUTO-001~002
> **상태**: Approved
> **적용 Phase**: Phase 3
> **선행 Spec**: AGENT_SPEC.md, KAFKA_SPEC.md
> **SDK**: Google A2A SDK (Apache 2.0)

---

## 1. Overview

A2A는 NeuralDB 내부 에이전트 간 Task 위임/협업 프로토콜입니다.

```
Monitoring Agent ──(anomaly detected)──► Diagnosis Agent
Diagnosis Agent  ──(rca complete)──────► Remediation Agent
Remediation Agent ──(action complete)──► Reporting Agent
```

**전송 계층 (하이브리드)**:
- **동기 (gRPC)**: Agent 간 직접 RPC — 저지연 요청/응답 (RCA 진단, Copilot, Health Check)
- **비동기 (Kafka)**: 이벤트 스트리밍 — 고빈도 메트릭, 인시던트 이벤트, 알림, 감사 로그

---

## 2. Agent Card (Discovery)

각 Agent는 시작 시 자신의 Agent Card를 등록합니다:

```json
{
  "agent_id": "agent-monitoring",
  "name": "Monitoring Agent",
  "version": "1.0.0",
  "capabilities": ["collect_metrics", "detect_anomaly", "update_baseline"],
  "accepts_tasks": ["monitor_instance", "retrain_baseline"],
  "status": "running",
  "registered_at": "2026-03-21T00:00:00Z",
  "heartbeat_interval_ms": 10000
}
```

**저장**: Valkey `a2a:agents:{agent_id}` (TTL = heartbeat × 3)
**Discovery**: `KEYS a2a:agents:*` 또는 `GET a2a:agents:{agent_id}`

---

## 3. Message Format

```python
@dataclass
class A2AMessage:
    # Header
    message_id: str          # UUID v4
    correlation_id: str      # 추적 ID (최초 트리거에서 생성, 전 체인 공유)
    timestamp: datetime      # UTC

    # Routing
    sender: str              # "agent-monitoring"
    receiver: str            # "agent-diagnosis" 또는 "*" (broadcast)
    reply_to: str | None     # 응답 토픽 (비동기 응답 시)

    # Task
    task_type: str           # "diagnose_incident", "execute_playbook" 등
    priority: int            # 0=low, 1=normal, 2=high, 3=critical
    payload: dict            # 태스크별 데이터

    # Control
    timeout_ms: int          # 태스크 타임아웃
    retry_count: int         # 현재 재시도 횟수
    max_retries: int         # 최대 재시도
```

### Kafka 직렬화
```json
{
  "message_id": "uuid-v4",
  "correlation_id": "uuid-v4",
  "timestamp": "2026-03-21T14:32:01.000Z",
  "sender": "agent-monitoring",
  "receiver": "agent-diagnosis",
  "reply_to": "neuraldb.a2a.results",
  "task_type": "diagnose_incident",
  "priority": 3,
  "payload": {
    "incident_id": "uuid",
    "instance_id": "uuid",
    "severity": "critical",
    "metric_type": "cpu_usage",
    "metric_value": 95.2
  },
  "timeout_ms": 30000,
  "retry_count": 0,
  "max_retries": 3
}
```

---

## 4. Kafka Topics

| Topic | Partition Key | Description |
|-------|-------------|-------------|
| `neuraldb.a2a.tasks` | `receiver` | 태스크 요청 |
| `neuraldb.a2a.results` | `correlation_id` | 태스크 결과 |
| `neuraldb.a2a.heartbeat` | `agent_id` | Agent 헬스 체크 |

---

## 5. Task Types

| task_type | Sender | Receiver | Payload | 응답 |
|-----------|--------|----------|---------|------|
| `diagnose_incident` | Monitoring | Diagnosis | `{incident_id}` | `{rca_result}` |
| `execute_playbook` | Diagnosis | Remediation | `{playbook_id, instance_id}` | `{remediation_log}` |
| `generate_report` | Remediation | Reporting | `{incident_id, actions}` | `{report_url}` |
| `retrain_baseline` | Task Orchestrator | Monitoring | `{instance_id, metric_type}` | `{baseline_id}` |
| `analyze_query` | any | Reporting | `{sql, instance_id}` | `{plan, suggestions}` |

---

## 6. Error Handling

### 재시도 정책
```python
retry_delays = [1s, 5s, 30s]  # Exponential backoff

if message.retry_count < message.max_retries:
    message.retry_count += 1
    await asyncio.sleep(retry_delays[message.retry_count - 1])
    await kafka.send("neuraldb.a2a.tasks", message)
else:
    await escalate_to_human(message)
```

### 에러 응답
```json
{
  "message_id": "uuid",
  "correlation_id": "original-correlation-id",
  "sender": "agent-diagnosis",
  "receiver": "agent-monitoring",
  "task_type": "diagnose_incident.error",
  "payload": {
    "error_code": "RCA_TIMEOUT",
    "error_message": "RCA analysis timed out after 30s",
    "original_task": { ... }
  }
}
```

### Error Codes
| Code | Description | Action |
|------|-------------|--------|
| `AGENT_UNAVAILABLE` | 수신 Agent 미등록 | 재시도 → 에스컬레이션 |
| `TASK_TIMEOUT` | 태스크 타임아웃 | 재시도 |
| `AUTONOMY_DENIED` | 자율 등급 부족 | 사람 승인 대기 |
| `EXECUTION_FAILED` | 실행 실패 | 롤백 → 에스컬레이션 |
| `INVALID_PAYLOAD` | 페이로드 검증 실패 | 재시도 안함, 로깅 |

---

## 7. Autonomy Gate

Task Orchestrator가 모든 A2A 메시지를 중개하며 Autonomy Level을 검증:

```python
async def route_task(message: A2AMessage):
    instance = await get_instance(message.payload.get("instance_id"))

    if message.task_type in WRITE_TASKS:
        required_level = get_required_autonomy(message.task_type)
        if instance.autonomy_level < required_level:
            await request_human_approval(message)
            return

    await kafka.send("neuraldb.a2a.tasks", message)
```

| task_type | 최소 Autonomy Level |
|-----------|-------------------|
| `diagnose_incident` | 0 (항상 허용) |
| `analyze_query` | 0 |
| `execute_playbook` (read-only) | 1 |
| `execute_playbook` (write) | 2 |
| `execute_playbook` (destructive) | 3 |
| `retrain_baseline` | 0 |

---

## 8. Observability

모든 A2A 메시지에 OpenTelemetry trace context를 전파:

```python
# W3C Trace Context propagation
headers = {
    "traceparent": f"00-{trace_id}-{span_id}-01",
    "correlation-id": message.correlation_id,
}
```

Audit Log에 기록:
- 메시지 송수신 (sender, receiver, task_type)
- Autonomy Gate 판정 결과
- 실행 시간/결과

---

## 9. gRPC 동기 통신 (Phase 3)

### 9.1 통신 경로 선택 기준

| 특성 | gRPC (동기) | Kafka (비동기) |
|------|------------|---------------|
| 지연 요구 | < 100ms 응답 필요 | 지연 허용 (수초~수분) |
| 패턴 | 요청 → 즉시 응답 (Unary RPC) | Fire-and-forget, Pub/Sub |
| 예시 | RCA 요청, Copilot 진단, Health Check | 메트릭 수집, 알림 발송, 감사 로그 |
| 직렬화 | Protocol Buffers (바이너리, ~10x 효율) | JSON (텍스트, 가독성 우선) |
| 실패 처리 | 즉시 에러 반환 + gRPC status code | 재시도 큐 + DLQ |

### 9.2 gRPC 서비스 정의

```protobuf
// proto/neuraldb_agents.proto
syntax = "proto3";
package neuraldb.agents;

import "google/protobuf/timestamp.proto";
import "google/protobuf/struct.proto";

// ─── Diagnosis Service ───────────────────────────
service DiagnosisService {
  // MTL 4-Head 동기 추론
  rpc Diagnose(DiagnoseRequest) returns (DiagnoseResponse);
  // Tree-of-Thought Copilot 진단
  rpc CopilotDiagnose(CopilotRequest) returns (CopilotResponse);
  // 유사 인시던트 RAG 검색
  rpc SearchSimilar(RAGSearchRequest) returns (RAGSearchResponse);
}

// ─── Remediation Service ─────────────────────────
service RemediationService {
  // Playbook 실행 (Autonomy Gate 포함)
  rpc ExecutePlaybook(PlaybookRequest) returns (PlaybookResponse);
  // 롤백
  rpc Rollback(RollbackRequest) returns (RollbackResponse);
  // Dry-run 시뮬레이션
  rpc DryRun(PlaybookRequest) returns (DryRunResponse);
}

// ─── Reporting Service ───────────────────────────
service ReportingService {
  // NL2SQL 동기 실행
  rpc NL2SQL(NL2SQLRequest) returns (NL2SQLResponse);
  // 실행 계획 해석
  rpc ExplainPlan(ExplainRequest) returns (ExplainResponse);
}

// ─── Agent Health ────────────────────────────────
service AgentHealthService {
  // 헬스 체크 (gRPC Health Checking Protocol 준수)
  rpc Check(HealthCheckRequest) returns (HealthCheckResponse);
  // Agent Card 조회
  rpc GetAgentCard(AgentCardRequest) returns (AgentCard);
}

// ─── Messages ────────────────────────────────────
message DiagnoseRequest {
  string incident_id = 1;
  string instance_id = 2;
  bool include_reasoning = 3;
}

message DiagnoseResponse {
  string prediction_id = 1;
  string anomaly_type = 2;
  float anomaly_confidence = 3;
  string root_cause = 4;
  google.protobuf.Struct root_cause_detail = 5;
  string severity = 6;
  float severity_score = 7;
  repeated SuggestedAction suggested_actions = 8;
  float confidence = 9;
  repeated string reasoning_chain = 10;
  repeated string evidence_links = 11;
  string model_version = 12;
  int32 inference_time_ms = 13;
}

message SuggestedAction {
  string action = 1;
  string description = 2;
  float confidence = 3;
  string risk = 4;  // LOW, MEDIUM, HIGH, CRITICAL
}

message CopilotRequest {
  string instance_id = 1;
  string incident_id = 2;  // optional
  int32 max_branches = 3;
  bool auto_execute = 4;
}

message CopilotResponse {
  string session_id = 1;
  int32 branches_explored = 2;
  string selected_branch = 3;
  repeated BranchScore branch_scores = 4;
  DiagnoseResponse diagnosis = 5;
  int32 autonomy_level_applied = 6;
  string execution_status = 7;
}

message BranchScore {
  string branch_name = 1;
  float relevance_score = 2;
  float evidence_strength = 3;
  float action_confidence = 4;
  float risk_penalty = 5;
  float final_score = 6;
}

message HealthCheckRequest {
  string agent_id = 1;
}

message HealthCheckResponse {
  string agent_id = 1;
  string status = 2;  // SERVING, NOT_SERVING
  int64 uptime_ms = 3;
  int32 active_tasks = 4;
}
```

### 9.3 gRPC 서버 구성

```python
# backend/app/grpc/server.py
# Spec: PROTO-A2A-001

import grpc
from concurrent import futures

GRPC_PORT = 50051
MAX_WORKERS = 10

async def serve():
    server = grpc.aio.server(
        futures.ThreadPoolExecutor(max_workers=MAX_WORKERS),
        interceptors=[
            AuthInterceptor(),          # JWT/API Key 인증
            OTelInterceptor(),          # OpenTelemetry 트레이싱
            AutonomyGateInterceptor(),  # Autonomy Level 검증
        ],
    )
    # 서비스 등록
    add_DiagnosisServiceServicer_to_server(DiagnosisServicer(), server)
    add_RemediationServiceServicer_to_server(RemediationServicer(), server)
    add_ReportingServiceServicer_to_server(ReportingServicer(), server)
    add_AgentHealthServiceServicer_to_server(HealthServicer(), server)

    # Reflection (디버깅/테스트)
    from grpc_reflection.v1alpha import reflection
    SERVICE_NAMES = [...]
    reflection.enable_server_reflection(SERVICE_NAMES, server)

    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    await server.start()
    await server.wait_for_termination()
```

### 9.4 gRPC + Kafka 라우팅 규칙

```python
# backend/app/a2a/router.py

async def route_task(message: A2AMessage):
    """태스크 유형에 따라 gRPC 또는 Kafka로 라우팅"""

    # 동기 처리 대상 (gRPC)
    GRPC_TASKS = {
        "diagnose_incident",    # MTL RCA → 즉시 응답 필요
        "copilot_diagnose",     # ToT 진단 → 즉시 응답 필요
        "analyze_query",        # EXPLAIN → 즉시 응답 필요
        "nl2sql",               # NL2SQL → 즉시 응답 필요
        "health_check",         # Agent 헬스 → 즉시 응답 필요
    }

    # 비동기 처리 대상 (Kafka)
    KAFKA_TASKS = {
        "execute_playbook",     # 실행 시간 미정, 비동기
        "generate_report",      # 리포트 생성 시간 미정
        "retrain_baseline",     # 재학습 수분 소요
        "dispatch_alert",       # 알림 발송
    }

    if message.task_type in GRPC_TASKS:
        return await grpc_dispatch(message)
    else:
        return await kafka_dispatch(message)
```

### 9.5 gRPC 에러 코드 매핑

| gRPC Status | A2A Error Code | 설명 |
|-------------|---------------|------|
| `OK` | - | 정상 |
| `UNAVAILABLE` | `AGENT_UNAVAILABLE` | Agent 미등록/다운 |
| `DEADLINE_EXCEEDED` | `TASK_TIMEOUT` | 타임아웃 |
| `PERMISSION_DENIED` | `AUTONOMY_DENIED` | 자율 등급 부족 |
| `INTERNAL` | `EXECUTION_FAILED` | 실행 실패 |
| `INVALID_ARGUMENT` | `INVALID_PAYLOAD` | 페이로드 검증 실패 |
| `RESOURCE_EXHAUSTED` | `RATE_LIMITED` | Rate limit 초과 |

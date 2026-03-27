# MCP Integration Spec: Model Context Protocol 서버

> **Spec ID**: PROTO-MCP-001
> **PRD 참조**: FR-ALERT-004
> **상태**: Implemented (Phase 3)
> **적용 Phase**: Phase 3
> **SDK**: @modelcontextprotocol/sdk (MIT) — Python 구현
> **선행 Spec**: API_SPEC.md, AGENT_SPEC.md

---

## 1. Overview

NeuralDB MCP Server는 외부 AI 도구(Claude Code, VS Code Copilot, ChatGPT 등)가 NeuralDB의 모니터링 데이터에 접근할 수 있도록 하는 표준 프로토콜 인터페이스입니다.

```
External AI Tool (Claude Code, Copilot, ChatGPT)
    ↓ MCP Protocol (stdio / HTTP)
NeuralDB MCP Server
    ├── ↓ REST API (읽기 전용 조회)
    │   FastAPI Backend → PostgreSQL 16 / Valkey
    │
    └── ↓ gRPC (Agent 직접 호출, Phase 3)
        Agent Layer (Diagnosis / Remediation / Reporting)
        ├── DiagnosisService.Diagnose() → MTL RCA 즉시 응답
        ├── DiagnosisService.CopilotDiagnose() → ToT 진단
        └── ReportingService.NL2SQL() → 자연어 SQL 변환
```

---

## 2. Server Configuration

```python
# backend/app/mcp/server.py
from mcp.server import Server

app = Server("neuraldb")

# Transport: stdio (CLI 도구용) 또는 HTTP (웹 도구용)
# 인증: API Key (X-NeuralDB-Token header)
```

### 실행
```bash
# stdio mode (Claude Code 등 CLI 도구)
uv run python -m app.mcp.server --transport stdio

# HTTP mode (웹 기반 도구)
uv run python -m app.mcp.server --transport http --port 3100
```

---

## 3. Resources

외부 AI 도구가 조회할 수 있는 데이터 리소스:

| URI | Description | MIME Type |
|-----|-------------|-----------|
| `neuraldb://instances` | 모니터링 중인 DB 인스턴스 목록 | application/json |
| `neuraldb://instances/{id}` | 인스턴스 상세 + 최신 메트릭 | application/json |
| `neuraldb://instances/{id}/metrics` | 최근 1시간 메트릭 | application/json |
| `neuraldb://incidents` | 활성 인시던트 목록 | application/json |
| `neuraldb://incidents/{id}` | 인시던트 상세 + RCA | application/json |
| `neuraldb://topology` | 현재 토폴로지 그래프 | application/json |
| `neuraldb://playbooks` | Playbook 목록 + YAML | application/json |
| `neuraldb://baselines/{id}` | 베이스라인 프로필 | application/json |

### Resource 구현 예시
```python
@app.list_resources()
async def list_resources():
    return [
        Resource(
            uri="neuraldb://instances",
            name="DB Instances",
            description="All monitored database instances with current health status",
            mimeType="application/json",
        ),
        # ...
    ]

@app.read_resource()
async def read_resource(uri: str):
    if uri == "neuraldb://instances":
        instances = await instance_service.list_all()
        return json.dumps([i.to_dict() for i in instances])
```

---

## 4. Tools

외부 AI 도구가 실행할 수 있는 액션:

### 4.1 Read-Only Tools

| Tool | Description | Input Schema |
|------|-------------|-------------|
| `query_metrics` | 메트릭 범위 조회 | `{instance_id: str, metric_type?: str, from: datetime, to: datetime}` |
| `get_active_sessions` | 현재 활성 세션 (ASH) | `{instance_id: str, min_duration_ms?: int, state?: str}` |
| `list_incidents` | 인시던트 목록 | `{severity?: str, status?: str, limit?: int}` |
| `analyze_query` | SQL 실행 계획 분석 | `{instance_id: str, sql: str}` |
| `run_diagnosis` | AI RCA 실행 | `{incident_id: str}` |
| `nl2sql` | 자연어 → SQL | `{question: str, instance_id: str}` |
| `get_topology` | 토폴로지 그래프 | `{cluster_id?: str}` |
| `get_schema_changes` | 스키마 변경 이력 | `{instance_id: str, since?: datetime}` |
| `get_wait_breakdown` | Wait Event 집계 | `{instance_id: str, from: datetime, to: datetime}` |

### 4.2 Write Tools (dry_run 기본)

| Tool | Description | Input Schema | 주의 |
|------|-------------|-------------|------|
| `execute_playbook` | Playbook 실행 | `{playbook_id: str, instance_id: str, dry_run: bool = true}` | dry_run=false는 Autonomy Level 체크 |

### 4.3 Tool 구현 예시

```python
@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="query_metrics",
            description="Query database performance metrics for a specific instance and time range",
            inputSchema={
                "type": "object",
                "properties": {
                    "instance_id": {"type": "string", "description": "UUID of the DB instance"},
                    "metric_type": {"type": "string", "description": "cpu_usage, memory, tps, etc."},
                    "from": {"type": "string", "format": "date-time"},
                    "to": {"type": "string", "format": "date-time"},
                },
                "required": ["instance_id", "from", "to"],
            },
        ),
        # ...
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "query_metrics":
        metrics = await metric_service.query(
            instance_id=arguments["instance_id"],
            metric_type=arguments.get("metric_type"),
            from_time=parse_datetime(arguments["from"]),
            to_time=parse_datetime(arguments["to"]),
        )
        return json.dumps(metrics)
```

---

## 5. Prompts

NeuralDB 도메인에 최적화된 LLM 프롬프트 템플릿:

| Prompt | Description | Arguments |
|--------|-------------|-----------|
| `diagnose-incident` | 인시던트 근본 원인 분석 프롬프트 | `{incident_id}` |
| `optimize-query` | SQL 최적화 제안 프롬프트 | `{sql, instance_id}` |
| `explain-plan` | 실행 계획 자연어 해석 | `{plan_json}` |
| `generate-playbook` | 장애 패턴 → Playbook YAML 생성 | `{incident_description}` |
| `daily-report` | 일간 DB 상태 리포트 | `{instance_id, date}` |

```python
@app.list_prompts()
async def list_prompts():
    return [
        Prompt(
            name="diagnose-incident",
            description="Analyze a database incident and suggest root cause",
            arguments=[
                PromptArgument(name="incident_id", description="UUID of the incident", required=True),
            ],
        ),
    ]

@app.get_prompt()
async def get_prompt(name: str, arguments: dict):
    if name == "diagnose-incident":
        incident = await incident_service.get(arguments["incident_id"])
        metrics = await metric_service.get_around(incident.detected_at)
        return f"""Analyze this database incident:
Title: {incident.title}
Severity: {incident.severity}
Metrics at detection: {json.dumps(metrics)}
..."""
```

---

## 6. Authentication

| 방식 | 용도 |
|------|------|
| **API Key** | 기본. `X-NeuralDB-Token` 헤더 또는 stdio 환경변수 |
| **JWT** | 사용자 컨텍스트가 필요한 경우 (RBAC 적용) |

```python
# 인증 미들웨어
async def authenticate_mcp_request(token: str) -> User:
    if token.startswith("ndb_"):
        return await api_key_auth(token)     # API User 역할
    else:
        return await jwt_auth(token)          # 사용자 역할 (RBAC)
```

**API Key 형식**: `ndb_` prefix + 40자 랜덤 = `ndb_a1b2c3d4e5...`
**환경변수**: `NEURALDB_MCP_TOKEN=ndb_...`

---

## 7. Rate Limiting

| Tool | Rate Limit | 이유 |
|------|-----------|------|
| `query_metrics` | 60 req/min | DB 조회 부하 |
| `nl2sql` | 10 req/min | LLM API 비용 |
| `run_diagnosis` | 5 req/min | LLM + RAG 비용 |
| `execute_playbook` | 2 req/min | Write 작업 |
| 기타 read tools | 120 req/min | 경량 조회 |

---

## 8. Audit

모든 MCP 도구 호출은 `audit_logs`에 기록:

```json
{
  "action": "mcp_tool_call",
  "resource_type": "mcp",
  "details": {
    "tool_name": "query_metrics",
    "arguments": { "instance_id": "uuid", "from": "...", "to": "..." },
    "client": "claude-code",
    "response_size_bytes": 4096,
    "duration_ms": 120
  }
}
```

---

## 9. MCP → gRPC Agent 연동 (Phase 3)

MCP Server가 외부 AI 도구의 요청을 Agent Layer에 gRPC로 직접 전달하여 저지연 응답을 제공합니다.

### 연동 경로

| MCP Tool | 전송 방식 | 대상 gRPC Service | 지연 목표 |
|----------|----------|-------------------|----------|
| `query_metrics` | REST API | (기존 FastAPI) | < 200ms |
| `get_active_sessions` | REST API | (기존 FastAPI) | < 200ms |
| `copilot_diagnose` | **gRPC** | `DiagnosisService.CopilotDiagnose` | < 10s |
| `copilot_suggest_fix` | **gRPC** | `DiagnosisService.Diagnose` | < 5s |
| `copilot_execute` | **gRPC** | `RemediationService.ExecutePlaybook` | < 30s |
| `nl2sql` | **gRPC** | `ReportingService.NL2SQL` | < 5s |
| `run_diagnosis` | **gRPC** | `DiagnosisService.Diagnose` | < 10s |

### MCP → gRPC 브릿지 구현

```python
# backend/app/mcp/grpc_bridge.py
# Spec: PROTO-MCP-001, PROTO-A2A-001

import grpc
from app.grpc.generated import agents_pb2, agents_pb2_grpc

GRPC_CHANNEL = grpc.aio.insecure_channel("localhost:50051")

async def mcp_to_grpc_diagnose(incident_id: str) -> dict:
    """MCP copilot_diagnose → gRPC DiagnosisService.Diagnose"""
    stub = agents_pb2_grpc.DiagnosisServiceStub(GRPC_CHANNEL)
    request = agents_pb2.DiagnoseRequest(
        incident_id=incident_id,
        include_reasoning=True,
    )
    response = await stub.Diagnose(request, timeout=10.0)
    return protobuf_to_dict(response)

async def mcp_to_grpc_copilot(instance_id: str, incident_id: str = None) -> dict:
    """MCP copilot_diagnose → gRPC DiagnosisService.CopilotDiagnose"""
    stub = agents_pb2_grpc.DiagnosisServiceStub(GRPC_CHANNEL)
    request = agents_pb2.CopilotRequest(
        instance_id=instance_id,
        incident_id=incident_id or "",
        max_branches=4,
        auto_execute=False,
    )
    response = await stub.CopilotDiagnose(request, timeout=30.0)
    return protobuf_to_dict(response)
```

---

## DB Copilot MCP Tools (v3.3 신규)

DB Copilot 모드에서 외부 AI 도구가 활용할 수 있는 고급 MCP 도구:

| Tool | Read/Write | Description |
|------|-----------|-------------|
| `copilot_diagnose` | Read | Tree-of-Thought 기반 자동 진단. 메트릭/로그/ASH를 종합 분석하여 다중 경로 RCA 수행 |
| `copilot_suggest_fix` | Read | MTL 4-Head 추론으로 이상분류+원인+심각도+액션을 한 번에 반환 |
| `copilot_explain` | Read | 특정 인시던트에 대한 Reasoning Chain + Evidence Links 반환 (Explainable AI) |
| `copilot_confidence` | Read | 현재 AI 모델의 정확도/신뢰도 통계 조회 (LLM Observability) |
| `copilot_execute` | Write | Autonomy Level 확인 후 추천 액션 실행 (Level 2+ 필요) |

### Copilot Diagnose 응답 형식

```json
{
  "diagnosis_id": "uuid",
  "tree_of_thought": {
    "branches_explored": 4,
    "selected_branch": "query_performance",
    "confidence": 0.87
  },
  "mtl_results": {
    "anomaly_type": "query_performance_degradation",
    "root_cause": "Missing index on orders.created_at causing Seq Scan",
    "severity": 0.72,
    "suggested_actions": [
      {"action": "CREATE INDEX CONCURRENTLY ...", "confidence": 0.91, "risk": "LOW"}
    ]
  },
  "reasoning_chain": ["Step 1: ...", "Step 2: ..."],
  "evidence_links": ["/api/v1/instances/pg-01/metrics?range=1h"]
}
```

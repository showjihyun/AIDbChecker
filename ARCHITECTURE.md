# NeuralDB Architecture — v1.1.2

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    External AI (MCP Protocol)                    │
│  Claude Code · OpenAI Codex · Gemini · Any MCP Client           │
│  → dba_ask (unified DBA Agent)                                  │
│  → dba_execute (ops with SafetyGuard)                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ MCP stdio/http
┌──────────────────────────┴──────────────────────────────────────┐
│                    Presentation Layer                            │
│  React 18 + Vite + TailwindCSS + ECharts + Socket.io            │
│  DBA Mini Chat (우하단 상시 위젯) + Dashboard + ASH Explorer     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API / WebSocket (JWT auth)
┌──────────────────────────┴──────────────────────────────────────┐
│                    API Gateway (FastAPI)                          │
│  JWT/RBAC + Rate Limiting + Prometheus /metrics                  │
│  POST /api/v1/dba/ask (unified DBA Agent endpoint)              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                    DBA Agent Orchestrator                         │
│  Intent Router: keyword-first + LLM fallback                    │
│  ActionMemory: past action context injection                    │
│                                                                  │
│  ├─ analyze  → TuningAgent (ReAct 7 tools) + LLM Retry(2)      │
│  ├─ diagnose → CopilotAgent (ToT 8 branches) + LLM Retry(3)    │
│  ├─ execute  → SafetyGuard → ExecutionEngine                    │
│  │              ├─ QuerySimulator (EXPLAIN cost)                 │
│  │              ├─ 4-level risk (SAFE/WARNING/DANGEROUS/CRITICAL)│
│  │              └─ Policy Matrix (risk × autonomy × role)        │
│  ├─ query    → NL2SQL (GraphRAG + pgvector)                     │
│  └─ status   → System Health                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                    Proactive Agent (Celery Beat)                  │
│  Quick Check (30min) → Deep Analysis (6h) → Morning Report (9AM)│
│  Self-Healing: anomaly → DBA Agent → SafetyGuard → auto-execute │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                    Core Services                                 │
│  KPI Calculator · Auto Baseline (STL+IF) · MTL Lite RCA         │
│  RAG (pgvector) · Schema Detector · AIGC Report · Playbook Lite │
│  AI Decision Logger · LLM Observability                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                    DB Adapter Layer                               │
│  PostgreSQL Remote Adapter (1s ASH + pg_stat_* + statement_timeout)│
│  ops_tools: create_index, vacuum, kill_session, alter_param      │
│  All writes → SafetyGuard → ExecutionEngine (never direct)       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                    Infrastructure                                │
│  PostgreSQL 16 (meta + metrics + vector) + Valkey (cache+broker) │
│  Celery Workers + Docker Compose                                 │
└─────────────────────────────────────────────────────────────────┘
```

## DBA Agent Architecture

```
User: "DB가 느려"
    ↓
POST /api/v1/dba/ask
    ↓
ActionMemory.get_context()     ← 과거 action 기억
    ↓
Intent Router (keyword + LLM)  → "analyze"
    ↓
retry_llm_call(TuningAgent.analyze(), max=2, safe_mode="LLM unavailable")
    ↓
TuningAgent ReAct Loop (7 tools: explain, slow_queries, index, params, bloat, locks, conns)
    ↓
DBAResponse {intent: "analyze", answer: "...", actions: [{create_index, suggested}]}
    ↓
User: "인덱스 만들어줘"
    ↓
Intent Router → "execute"
    ↓
ops_tools.create_index() → ActionRequest (SQL만 반환, 실행 안 함)
    ↓
SafetyGuard.classify_risk("CREATE INDEX CONCURRENTLY") → WARNING
    ↓
SafetyGuard.check_policy(WARNING, L2, confidence=0.8, role="db_admin") → "execute"
    ↓
ExecutionEngine:
  QuerySimulator.simulate() → {cost: 50, feasible: true}
  _execute_with_timeout(sql, 30s) → within explicit transaction
  _post_check() → {last_index: "idx_orders_user_id"}
  _audit_log() → audit_logs + agent_actions
    ↓
ActionResult {status: "executed", execution_time_ms: 1200}
```

## Security Architecture

```
SafetyGuard 4-Level Risk Classification:
  SAFE      → auto-execute (SELECT, ANALYZE)
  WARNING   → L1: approve, L2+: execute (CREATE INDEX CONCURRENTLY)
  DANGEROUS → L2: approve, L3+: execute (VACUUM FULL, pg_terminate_backend)
  CRITICAL  → L0-L3: block, L4: approve (DROP TABLE, TRUNCATE)

Role-Based Ceiling:
  viewer   → SAFE max
  operator → WARNING max
  db_admin → DANGEROUS max
  super_admin → unrestricted

Additional Guards:
  - Confidence < 0.5 → block DANGEROUS+
  - validate_identifier() on all table/column/index names
  - Semicolon/comment injection → CRITICAL
  - ALTER SYSTEM parameter allowlist (14 safe params)
  - Rate limiting: login 5/min, DBA 10/min, NL2SQL 20/min
  - WebSocket JWT auth on connect
  - OIDC token JWKS signature verification
  - Docker: non-root user, localhost port binding, Valkey requirepass
```

## Key Specs

| Spec | Description | ACs |
|------|-------------|-----|
| FS-DBA-001 | Execution Layer (SafetyGuard + ops_tools + Engine) | 16 |
| FS-DBA-002 | Orchestrator + MCP + Chat UI | 13 |
| FS-DBA-003 | Proactive Agent (Quick/Deep/Report/Self-Healing) | 10 |
| FS-DBA-004 | Multi-turn DBA Agent (session memory + context) | 10 |
| FS-DBA-005 | Claude Native Tool Use Agent | 8 |
| FS-HARNESS-001 | 4-Pillar Pre-Commit Quality Gate | 9 |
| FS-AI-NL2SQL-001 | NL2GraphRAG (Knowledge Graph + pgvector) | 20 |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, TypeScript, TailwindCSS, ECharts, TanStack |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0, Celery |
| Database | PostgreSQL 16, pgvector, pg_partman |
| Cache | Valkey 8 (Redis-compatible, BSD) |
| AI/LLM | LangChain, Ollama (llama3.1:8b), OpenAI (gpt-5.4), Anthropic (Opus/Sonnet 4.6), Google (Gemini 3.1) |
| MCP | Model Context Protocol (stdio/http transport) |
| Package | uv (not pip) |

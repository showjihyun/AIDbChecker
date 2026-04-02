# NeuralDB — AI-Powered Intelligent DB Monitoring System

> PostgreSQL 10+ instances monitoring with AI-driven anomaly detection, root cause analysis, and self-healing.

## Quick Start

```bash
# 1. Clone
git clone <repo-url> && cd AIDbChecker

# 2. Infrastructure
cd infra/docker && docker compose up -d postgres valkey

# 3. Backend
cd ../../backend
uv sync                                    # Install dependencies
uv run alembic upgrade head                # DB migration
uv run uvicorn app.main:app --reload       # API server (port 8000)

# 4. Celery Workers (separate terminal)
cd backend
uv run celery -A app.tasks worker -l info -Q collect,alert,analyze
uv run celery -A app.tasks beat -l info

# 5. Frontend (separate terminal)
cd frontend
npm install && npm run dev                 # Vite dev server (port 3000)
```

Open http://localhost:3000

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  External AI (MCP Protocol)                                      │
│  Claude Code / OpenAI Codex / Gemini / Any MCP Client            │
│  → dba_ask (unified DBA Agent)  → dba_execute (SafetyGuard)     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ MCP stdio/http
┌──────────────────────────┴──────────────────────────────────────┐
│  Presentation Layer                                              │
│  React 18 + Vite + TailwindCSS + ECharts + Socket.io             │
│  DBA Mini Chat (floating widget) + Dashboard + ASH Explorer      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API / WebSocket (JWT auth)
┌──────────────────────────┴──────────────────────────────────────┐
│  API Gateway (FastAPI)                                           │
│  JWT/RBAC + Rate Limiting + Prometheus /metrics                  │
│  POST /api/v1/dba/ask — unified DBA Agent endpoint              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│  DBA Agent Orchestrator                                          │
│  Intent Router (keyword + LLM) + ActionMemory                    │
│  ├─ analyze  → TuningAgent (ReAct 7 tools)                      │
│  ├─ diagnose → CopilotAgent (ToT 8 branches)                    │
│  ├─ execute  → SafetyGuard → ExecutionEngine                    │
│  ├─ query    → NL2SQL (GraphRAG + pgvector)                     │
│  └─ status   → System Health                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│  Proactive Agent (Celery Beat)                                   │
│  Quick Check (30min) → Deep Analysis (6h) → Morning Report (9AM) │
│  Self-Healing: anomaly → DBA Agent → SafetyGuard → auto-execute  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│  Core Services                                                   │
│  KPI Calculator · Auto Baseline (STL+IF) · MTL Lite RCA          │
│  RAG (pgvector) · Schema Detector · AIGC Report · Playbook Lite  │
│  AI Decision Logger · LLM Observability                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│  DB Adapter Layer                                                │
│  PostgreSQL Remote Adapter (1s ASH + pg_stat_*)                  │
│  ops_tools: create_index, vacuum, kill_session, alter_param      │
│  All writes → SafetyGuard → ExecutionEngine (never direct)       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│  Infrastructure                                                  │
│  PostgreSQL 16 (meta + metrics + vector) + Valkey (cache+broker) │
│  Celery Workers + Docker Compose                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

| Feature | Description | Spec |
|---------|-------------|------|
| 1-Second Metrics | Hot/Warm/Cold tier collection via pg_stat_* | FS-AI-001 |
| AI Baseline | STL decomposition + Isolation Forest anomaly detection | FS-AI-001 |
| MTL Lite RCA | 4-Head simultaneous inference (anomaly/cause/severity/action) | FS-AI-010 |
| RAG Search | pgvector incident similarity search | FS-AI-RAG-001 |
| NL2SQL + GraphRAG | Natural language to SQL with Knowledge Graph | FS-AI-NL2SQL-001 |
| **DBA Agent** | Unified AI DBA: analyze/diagnose/execute/query/status | FS-DBA-001/002 |
| **Multi-turn DBA** | Context-aware multi-turn conversation with session memory | FS-DBA-004 |
| **Native Tool Use** | Claude Native Tool Use for structured agent execution | FS-DBA-005 |
| Execution Engine | SafetyGuard 4-level risk + Autonomy Policy Matrix | FS-DBA-001 |
| Proactive Agent | Quick Check / Deep Analysis / Morning Report / Self-Healing | FS-DBA-003 |
| DB Copilot | Tree-of-Thought 8-branch diagnosis | FS-AI-012 |
| AIGC Report | LLM-generated health reports (weekly auto, PDF download) | FS-AI-005 |
| Playbook Lite | 7 built-in + custom YAML, Autonomy Gate L0~L4 | FS-AUTO-003 |
| Task Queue | State machine + approval workflow + concurrency control | FS-AUTO-004 |
| MCP Server | External AI tool integration (Claude Code, Copilot) | PROTO-MCP-001 |
| SSO/LDAP | OIDC + LDAP + API Key authentication | FS-ADMIN-002 |
| Slack Settings | Webhook configuration + test notification | FS-ALERT-002 |
| LLM Observability | Token/latency/cost/hallucination tracking | FS-AI-013 |
| Harness v3 | 4-Pillar Pre-Commit Quality Gate (lint/type/test/AC) | FS-HARNESS-001 |

## Tech Stack

| Layer | Technology | License |
|-------|-----------|---------|
| Frontend | React 18, Vite, TypeScript, TailwindCSS, ECharts, TanStack | MIT |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0, Celery | MIT/BSD |
| Database | PostgreSQL 16, pgvector, pg_partman | PostgreSQL License |
| Cache | Valkey 8 (Redis-compatible, BSD) | BSD 3-Clause |
| AI/LLM | LangChain, Ollama, OpenAI, Anthropic, Google | MIT |
| Package | uv (not pip) | MIT |

**License Policy**: Apache 2.0 / MIT / BSD only. No GPL/AGPL/SSPL.

## Project Structure

```
AIDbChecker/
├── backend/                  # Python + FastAPI
│   ├── app/
│   │   ├── api/v1/          # 26 API routers
│   │   ├── models/          # 18 SQLAlchemy models
│   │   ├── schemas/         # 23 Pydantic schemas
│   │   ├── services/        # 19 business services
│   │   ├── agents/          # DBA Orchestrator + Copilot + Tuning + Proactive
│   │   ├── adapters/        # PostgreSQL Remote Adapter
│   │   ├── tasks/           # Celery Beat schedules
│   │   ├── mcp/             # MCP Server (dba_ask + dba_execute)
│   │   └── websocket/       # Socket.io real-time
│   ├── playbooks/builtin/   # 7 built-in YAML playbooks
│   ├── migrations/           # Alembic
│   └── tests/               # 55 test files
├── frontend/                 # React + Vite
│   └── src/
│       ├── components/       # 22 TSX components
│       ├── api/hooks/        # TanStack Query hooks
│       ├── stores/           # Zustand stores
│       └── routes/           # Pages
│   ├── tests/unit/           # 7 Vitest unit tests
│   └── e2e/                  # 5 Playwright E2E specs
├── infra/docker/             # Docker Compose
├── docs/
│   ├── specs/               # 52 Spec documents (12 categories)
│   ├── ADR/                 # 11 Architecture Decision Records
│   ├── review/              # Technical reviews
│   └── screenshots/         # UI reference screens
├── scripts/                  # Utility scripts
├── skills/                   # Claude Code skills (19 NeuralDB generators)
└── CLAUDE.md                # AI harness context
```

## Spec Index

All features are driven by Spec documents in `docs/specs/`. See [CLAUDE.md](CLAUDE.md) for the full document reference map.

| Category | Specs | Key Documents |
|----------|-------|---------------|
| **Agents** (6) | Multi-agent architecture, DBA execution, orchestrator, proactive, multi-turn, native tool use | `AGENT_SPEC.md`, `DBA_AGENT_EXEC_SPEC.md`, `DBA_ORCHESTRATOR_SPEC.md`, `PROACTIVE_AGENT_SPEC.md`, `DBA_MULTITURN_SPEC.md`, `NATIVE_TOOL_USE_SPEC.md` |
| **AI** (15) | Baseline, MTL RCA, RAG, NL2SQL, Copilot, Tuning, LLM provider/observability, AIGC report, confidence score, ReAct trace, diagnosis flow, DBA report, report download | `MTL_RCA_SPEC.md`, `NL2SQL_SPEC.md`, `COPILOT_SPEC.md`, `LIGHTWEIGHT_RAG_SPEC.md` |
| **API** (3) | REST API, error codes, GraphQL schema | `API_SPEC.md`, `ERROR_CODES_SPEC.md` |
| **Config** (1) | Application settings | `SETTINGS_SPEC.md` |
| **Data Model** (2) | ERD (20+ tables), migration strategy | `ERD.md`, `MIGRATION_SPEC.md` |
| **Frontend** (5) | Components, hooks, WebSocket events, KPI dashboard, incident list | `COMPONENT_SPEC.md`, `DB_KPI_SPEC.md` |
| **Playbooks** (1) | Built-in + custom YAML playbook engine | `PLAYBOOK_SPEC.md` |
| **Protocols** (3) | A2A, ~~Kafka~~ (deprecated, ADR-011), MCP integration | `MCP_INTEGRATION.md`, `A2A_PROTOCOL.md` |
| **Services** (8) | Service layer, audit log, schema change, AI decision log, task queue, system health, SSO/LDAP, Slack settings | `SERVICE_LAYER_SPEC.md`, `TASK_QUEUE_SPEC.md` |
| **Tasks** (1) | Celery task definitions and Beat schedules | `CELERY_TASKS_SPEC.md` |
| **Tests** (7) | Backend/frontend/integration test specs, test strategy, harness v3, live test plan | `TEST_STRATEGY.md`, `HARNESS_V3_SPEC.md` |

## ADR (Architecture Decision Records)

| ADR | Decision |
|-----|----------|
| [ADR-001](docs/ADR/001-fastapi-over-nestjs.md) | Python/FastAPI single backend (NestJS removed) |
| [ADR-002](docs/ADR/002-postgresql16-unified.md) | PostgreSQL 16 unified DB (TimescaleDB removed) |
| [ADR-003](docs/ADR/003-valkey-over-redis.md) | Valkey over Redis (license compliance) |
| [ADR-004](docs/ADR/004-uv-over-pip.md) | uv package manager (pip banned) |
| [ADR-005](docs/ADR/005-react-spa-over-nextjs.md) | React SPA (Next.js unnecessary) |
| [ADR-006](docs/ADR/006-hybrid-adapter-collection.md) | 2-Tier hybrid adapter collection |
| [ADR-007](docs/ADR/007-credential-encryption.md) | Credential encryption (Fernet) |
| [ADR-008](docs/ADR/008-lightweight-playbook-hybrid.md) | Lightweight Playbook + DB Copilot hybrid |
| [ADR-009](docs/ADR/009-langchain-langgraph-framework.md) | LangChain/LangGraph AI framework |
| [ADR-010](docs/ADR/010-graphrag-integration.md) | GraphRAG integration (Phase 2) |
| [ADR-011](docs/ADR/011-remove-kafka.md) | Kafka removed — Celery + Valkey + gRPC |

## Commands

```bash
# Backend
cd backend
uv run pytest                              # All tests
uv run ruff check app/                     # Lint
uv run ruff format app/                    # Format
uv run mypy app/                           # Type check
uv run alembic upgrade head                # Migrate

# Frontend
cd frontend
npm run dev                                # Dev server (port 3000)
npm run test                               # Vitest unit tests
npm run test:e2e                           # Playwright E2E
npm run build                              # Production build

# Docker
cd infra/docker
docker compose up -d                       # Start all
docker compose down                        # Stop all
```

## Spec-Driven Development

All code follows the **Spec-Driven Harness Engineering** methodology:

1. Spec First -- no code without a Spec document
2. `# Spec: FS-AI-005` comment in every source file
3. `@spec_ref("FS-AI-005", "AC-1")` decorator on every test
4. `pytest_terminal_summary` shows AC pass/fail dashboard
5. 11 ADRs document all architectural decisions
6. 52 Spec documents across 12 categories

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch strategy, commit convention, and review checklist.

## License

All dependencies use permissive licenses (MIT, Apache 2.0, BSD, PostgreSQL License).
See [ai-db-monitor-license-audit.jsx](ai-db-monitor-license-audit.jsx) for full audit.

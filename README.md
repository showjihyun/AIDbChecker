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
React SPA (3000) → FastAPI (8000) → PostgreSQL 16 (5432)
                        ↕                    ↑
                   Socket.io            pgvector + pg_partman
                        ↕
                  Celery Workers → Valkey (6379)
                        ↕
              Ollama / OpenAI / Claude (LLM)
```

**5-Layer Architecture:**
- **Presentation**: React 18 + Vite + TailwindCSS + ECharts + Socket.io
- **API Gateway**: FastAPI + JWT/RBAC + Prometheus /metrics
- **Core Engine**: LangChain + scikit-learn + Celery + 14 services
- **DB Adapter**: PostgreSQL Remote Adapter (1-second ASH sampling)
- **Infrastructure**: PostgreSQL 16 (meta+metrics+vector) + Valkey

## Key Features

| Feature | Description | Spec |
|---------|-------------|------|
| 1-Second Metrics | Hot/Warm/Cold tier collection via pg_stat_* | FS-AI-001 |
| AI Baseline | STL decomposition + Isolation Forest anomaly detection | FS-AI-001 |
| MTL Lite RCA | 4-Head simultaneous inference (anomaly/cause/severity/action) | FS-AI-010 |
| RAG Search | pgvector incident similarity search | FS-AI-RAG-001 |
| NL2SQL + GraphRAG | Natural language to SQL with Knowledge Graph | FS-AI-NL2SQL-001 |
| DB Copilot | Tree-of-Thought 8-branch diagnosis | FS-AI-012 |
| AIGC Report | LLM-generated health reports (weekly auto) | FS-AI-005 |
| Playbook Lite | 7 built-in + custom YAML, Autonomy Gate L0~L4 | FS-AUTO-003 |
| Task Queue | State machine + approval workflow + concurrency control | FS-AUTO-004 |
| MCP Server | External AI tool integration (Claude Code, Copilot) | PROTO-MCP-001 |
| SSO/LDAP | OIDC + LDAP + API Key authentication | FS-ADMIN-002 |
| LLM Observability | Token/latency/cost/hallucination tracking | FS-AI-013 |

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
│   │   ├── api/v1/          # 22 API routers
│   │   ├── models/          # 16 SQLAlchemy models
│   │   ├── schemas/         # 21 Pydantic schemas
│   │   ├── services/        # 14 business services
│   │   ├── agents/          # DB Copilot + Tuning Agent
│   │   ├── adapters/        # PostgreSQL Remote Adapter
│   │   ├── tasks/           # 6 Celery Beat schedules
│   │   ├── mcp/             # MCP Server
│   │   └── websocket/       # Socket.io real-time
│   ├── playbooks/builtin/   # 7 built-in YAML playbooks
│   ├── migrations/           # Alembic
│   └── tests/               # 492+ tests, 217 ACs
├── frontend/                 # React + Vite
│   └── src/
│       ├── components/       # 20 TSX components
│       ├── api/hooks/        # 7 TanStack Query hooks
│       ├── stores/           # 3 Zustand stores
│       └── routes/           # 7 pages
├── infra/docker/             # Docker Compose
├── docs/
│   ├── specs/               # 43 Spec documents
│   ├── ADR/                 # 11 Architecture Decision Records
│   └── etc/                 # Analysis docs
└── CLAUDE.md                # AI harness context
```

## Commands

```bash
# Backend
uv run pytest                              # All tests (492+)
uv run ruff check app/                     # Lint (0 errors)
uv run ruff format app/                    # Format
uv run alembic upgrade head                # Migrate

# Frontend
npm run dev                                # Dev server
npm run test                               # Vitest (65 tests)
npm run build                              # Production build

# Docker
cd infra/docker
docker compose up -d                       # Start all
docker compose down                        # Stop all
```

## Spec-Driven Development

All code follows the **Spec-Driven Harness Engineering** methodology:

1. Spec First — no code without a Spec document
2. `# Spec: FS-AI-005` comment in every source file
3. `@spec_ref("FS-AI-005", "AC-1")` decorator on every test
4. `pytest_terminal_summary` shows AC pass/fail dashboard
5. 11 ADRs document all architectural decisions

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch strategy, commit convention, and review checklist.

## License

All dependencies use permissive licenses (MIT, Apache 2.0, BSD, PostgreSQL License).
See [ai-db-monitor-license-audit.jsx](ai-db-monitor-license-audit.jsx) for full audit.

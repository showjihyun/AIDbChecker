---
name: init-project
description: Initialize the AIDbChecker project structure with all required directories, configs, and boilerplate based on the PRD v3.1 and architecture spec v3.0. Use when scaffolding the project from scratch or adding a new module.
disable-model-invocation: true
argument-hint: "[module: frontend|backend|engine|infra|all]"
allowed-tools: Bash, Read, Write, Glob, Grep, Edit
---

# Project Initialization Skill

You are initializing the **AI-Powered Intelligent DB Monitoring System (NeuralDB)** project.

## Reference Documents
- PRD: Read `AI_DB_Monitoring_System_PRD_v3.1.md` at project root
- Architecture: Read `ai-db-monitor-architecture-spec-v3.md` at project root
- Frontend Design: Read `docs/FRONTEND_DESIGN.md`
- License Audit: Read `ai-db-monitor-license-audit.jsx` for approved dependencies

## Target Module: $ARGUMENTS (default: all)

## Project Structure to Generate

```
AIDbChecker/
├── frontend/                    # React 18 + Vite + TypeScript
│   ├── src/
│   │   ├── api/                 # TanStack Query hooks & client
│   │   ├── components/          # Reusable UI components
│   │   │   ├── layout/          # TopNav, SideNav, MainContent
│   │   │   ├── dashboard/       # Summary cards, charts
│   │   │   ├── topology/        # Full-stack topology map (ECharts)
│   │   │   ├── diagnosis/       # RCA panel, incident list
│   │   │   ├── ash/             # ASH heatmap, session table
│   │   │   ├── playbook/        # Playbook editor, audit log
│   │   │   ├── nl2sql/          # NL2SQL chat (Monaco Editor)
│   │   │   └── common/          # Buttons, badges, cards, inputs
│   │   ├── hooks/               # Custom React hooks (WebSocket etc)
│   │   ├── stores/              # Zustand state management
│   │   ├── routes/              # TanStack Router
│   │   ├── lib/                 # Utilities (cn, formatDate)
│   │   ├── types/               # TypeScript type definitions
│   │   └── styles/              # Tailwind config, global CSS
│   ├── vite.config.ts
│   ├── tailwind.config.ts       # Design tokens from FRONTEND_DESIGN.md
│   ├── package.json
│   └── tsconfig.json
├── backend/                     # Python 3.11+ FastAPI
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Pydantic Settings
│   │   ├── api/v1/              # REST API routes
│   │   ├── graphql/             # Strawberry GraphQL
│   │   ├── websocket/           # python-socketio real-time
│   │   ├── models/              # SQLAlchemy 2.0 models
│   │   ├── schemas/             # Pydantic v2 request/response
│   │   ├── services/            # Business logic
│   │   ├── agents/              # AI agents (LangGraph/CrewAI)
│   │   ├── adapters/            # DB adapters (PostgreSQL, MySQL, MSSQL)
│   │   ├── collectors/          # Metric collectors (1s granularity)
│   │   ├── analyzers/           # Anomaly detection, baselining
│   │   ├── rag/                 # RAG pipeline (pgvector)
│   │   ├── mcp/                 # MCP Server
│   │   ├── a2a/                 # A2A Gateway
│   │   ├── tasks/               # Celery async tasks
│   │   ├── middleware/          # CORS, Auth, Logging
│   │   └── utils/               # Utilities
│   ├── migrations/              # Alembic migrations
│   ├── playbooks/               # Playbook YAML definitions
│   ├── tests/
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── Dockerfile
├── infra/                       # Infrastructure configs
│   ├── docker/
│   ├── k8s/
│   ├── terraform/
│   └── monitoring/              # Prometheus, OpenTelemetry
├── docs/                        # Design & specification docs
├── skills/                      # Claude Code skills
└── .claude/                     # Claude Code config
```

## Rules
- Only use MIT/Apache 2.0/BSD licensed dependencies (see license audit)
- Replace Grafana with custom React dashboard
- Replace TimescaleDB with QuestDB or VictoriaMetrics
- Replace Redis 7.4+ with Valkey (BSD 3-Clause)
- Follow the design tokens from `docs/FRONTEND_DESIGN.md`
- Use TypeScript strict mode for frontend/backend
- Use Python 3.11+ type hints for engine

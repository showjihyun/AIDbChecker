# NeuralDB — AI-Powered Intelligent DB Monitoring System

> PostgreSQL 장애 원인을 5분 안에 데이터로 특정하는 AI 기반 DB 모니터링 시스템

## Quick Start

```bash
# 1. 전체 스택 기동 (PostgreSQL + Valkey + Backend + Celery + Frontend)
cd infra/docker && docker compose up -d

# 2. 브라우저 접속
open http://localhost:3000

# 3. 로그인
# Email: admin@neuraldb.local
# Password: NeuralDB@2026!
```

`docker compose up` 한 줄로 DB 마이그레이션, 시드 유저 생성, 서버 기동이 자동으로 진행됩니다.

## Features (v0.4.0)

### Dashboard
- **12개 핵심 KPI** — TPS, QPS, Hit Ratio, Connections, Lock Waits, Deadlocks 등
- **실시간 메트릭 차트** — ECharts 시계열 (Hit Ratio / Connections / TPS/s)
- **System Health** — DB, Valkey, Celery 상태 모니터링
- **Advisory 알림** — pg_stat_statements 미설치 등 구성 문제 자동 감지 + Toast

### ASH Explorer
- **Wait Event 히트맵** — 10초 버킷 단위 세션 분석
- **세션 테이블** — pid, query, wait_event, duration 실시간 표시

### AI Engine
- **Auto-Baselining** — STL 분해 + Isolation Forest, 6시간마다 재학습
- **Anomaly Detection** — z-score 기반 이상 탐지 → 인시던트 자동 생성
- **NL2SQL** — 자연어 → SQL 변환 (GPT-4o / Ollama)
- **Lightweight RAG** — pgvector 인시던트 유사 검색
- **MTL Lite RCA** — 4-Head 동시 추론 (이상분류/원인/심각도/액션)

### Security
- **JWT 인증 + RBAC** — 5개 역할 (super_admin, db_admin, operator, viewer, api_user)
- **감사 로그** — 모든 상태 변경 WHO/WHAT/WHEN 자동 기록
- **DSN 검증** — 호스트/포트/DB명 정규식 검증 (injection 방지)
- **NL2SQL 방어** — 5계층 (write 차단, 위험 함수 차단, 테이블 차단, multi-statement 차단, SELECT 강제)

## Architecture

```
Frontend (React 18 + Vite + TailwindCSS)
    ↓ REST API + WebSocket
Backend (FastAPI + SQLAlchemy 2.0 + Celery)
    ↓
PostgreSQL 16 (meta + metrics + pgvector) + Valkey
```

## Tech Stack

| Layer | Technology | License |
|-------|-----------|---------|
| Frontend | React 18, Vite 6, TypeScript, TailwindCSS, ECharts, Zustand, TanStack | MIT |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Celery, LangChain | MIT/BSD |
| Database | PostgreSQL 16, pgvector | PostgreSQL License |
| Cache | Valkey 8 (Redis-compatible) | BSD 3-Clause |
| AI/ML | scikit-learn, statsmodels, sentence-transformers | BSD/MIT |

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 22 LTS
- Docker + Docker Compose
- uv (Python package manager)

### Backend
```bash
cd backend
uv sync                              # 의존성 설치
uv run alembic upgrade head          # DB 마이그레이션
uv run python -m app.db.seed         # 시드 유저 생성
uv run uvicorn app.main:app --reload # 개발 서버 (port 8000)
uv run pytest tests/                 # 테스트 (80 pass + 74 AC stubs)
```

### Frontend
```bash
cd frontend
npm install
npm run dev     # Vite dev server (port 3000)
npm run build   # Production build
```

### Infrastructure
```bash
cd infra/docker
docker compose up -d postgres valkey   # 인프라만
docker compose up -d                   # 전체
```

## Testing

### Harness Engineering (Spec-Driven Testing)

```bash
# Spec 품질 검증
uv run python -m scripts.validate_spec --all

# AC 테스트 스텁 자동 생성
uv run python -m scripts.gen_spec_tests

# AC 커버리지 대시보드
uv run python -m scripts.spec_dashboard

# 테스트 실행 (AC Summary 포함)
uv run pytest tests/ -v
```

Spec 파일에 인수 기준(AC)을 정의하면, 테스트 스텁이 자동 생성되고 `@spec_ref` 데코레이터로 추적됩니다.

## API Documentation

Backend 실행 후: http://localhost:8000/docs (Swagger UI)

### Key Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | JWT 로그인 |
| GET | `/api/v1/instances` | 인스턴스 목록 |
| GET | `/api/v1/instances/{id}/kpi` | 12개 KPI |
| GET | `/api/v1/instances/{id}/ash/heatmap` | ASH 히트맵 |
| GET | `/api/v1/incidents` | 인시던트 목록 |
| POST | `/api/v1/nl2sql/query` | NL2SQL 쿼리 |
| POST | `/api/v1/rag/search` | RAG 유사 검색 |

## Project Structure

```
AIDbChecker/
├── backend/                 # Python + FastAPI
│   ├── app/
│   │   ├── api/v1/          # REST API routes
│   │   ├── adapters/        # PostgreSQL Remote Adapter
│   │   ├── analyzers/       # Baseline + Anomaly Detection
│   │   ├── services/        # KPI, NL2SQL, RAG, MTL, Schema Detection
│   │   ├── models/          # SQLAlchemy ORM (14 models)
│   │   ├── schemas/         # Pydantic v2 schemas
│   │   ├── middleware/      # Audit log
│   │   ├── tasks/           # Celery (collect, analyze, alert, schema)
│   │   └── websocket/       # Socket.io real-time
│   ├── migrations/          # Alembic (13 tables)
│   ├── scripts/             # Harness tools (gen_spec_tests, validate_spec, spec_dashboard)
│   └── tests/               # pytest (80 real + 74 AC stubs)
├── frontend/                # React + Vite + TypeScript
│   └── src/
│       ├── components/      # Dashboard, ASH, Incidents, KPI, Toast, NL2SQL
│       ├── api/hooks/       # TanStack Query hooks
│       ├── stores/          # Zustand (auth, metrics, notifications)
│       └── routes/          # TanStack Router pages
├── docs/                    # Spec 문서 (30개)
│   └── specs/               # Feature Specs with ACs
└── infra/docker/            # Docker Compose + Dockerfiles
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch strategy, commit conventions, and PR process.

## License

Apache 2.0 / MIT / BSD only. See [license audit](ai-db-monitor-license-audit.jsx).

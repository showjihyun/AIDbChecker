# NeuralDB - AI-Powered Intelligent DB Monitoring System

## Project Overview
- **방법론**: Spec-Driven Harness Engineering
- **Frontend**: React 18 + Vite + TypeScript + TailwindCSS
- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Celery
- **Database**: PostgreSQL 16 (Meta + Metrics + Vector)
- **Cache**: Valkey (BSD 3-Clause, Redis API 호환)
- **Messaging**: Apache Kafka
- **AI/ML**: LangChain / LangGraph / CrewAI / OpenAI / Claude / Ollama

## Python Package Manager: uv (MUST)

> **pip 사용 금지. 모든 Python 패키지 관리는 반드시 `uv`를 사용한다.**

### Why uv?
- pip/pip-tools 대비 10~100배 빠른 의존성 해석 및 설치
- 결정론적 락파일(`uv.lock`)로 환경 간 완벽한 재현성 보장
- Python 버전 충돌 방지 (uv가 Python 버전 자체도 관리)
- virtualenv 자동 생성/관리 (`.venv`)
- pip, pip-tools, pipx, pyenv, virtualenv를 단일 도구로 통합

### Commands

```bash
# 프로젝트 초기화
uv init backend
cd backend

# Python 버전 고정
uv python pin 3.12

# 의존성 추가 (MVP 필수)
uv add fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg
uv add pydantic pydantic-settings
uv add celery redis  # redis 클라이언트는 Valkey와 API 호환
uv add langchain openai  # NL2SQL + MTL Lite
uv add sentence-transformers  # 경량 RAG 임베딩
uv add pgvector  # SQLAlchemy pgvector 지원
uv add slack-sdk aiosmtplib httpx  # 알림 (Slack/Email/Webhook)
uv add python-jose[cryptography] passlib[bcrypt]  # JWT 인증
uv add python-socketio  # WebSocket 실시간 메트릭
uv add alembic  # DB 마이그레이션

# 의존성 추가 (Phase 2+)
uv add langgraph crewai  # Multi-Agent (Phase 3)

# 개발 의존성 추가
uv add --dev pytest pytest-asyncio ruff mypy

# 의존성 그룹 추가
uv add --group ml scikit-learn prophet statsmodels

# 락파일 기반 설치 (CI/CD, 동료 개발자)
uv sync

# 스크립트 실행
uv run uvicorn app.main:app --reload
uv run pytest
uv run celery -A app.tasks worker -l info
uv run alembic upgrade head

# 락파일 갱신
uv lock
```

### File Structure
```
backend/
├── pyproject.toml    # 의존성 정의 (uv가 관리)
├── uv.lock           # 결정론적 락파일 (반드시 커밋)
├── .python-version   # Python 버전 고정 (e.g., 3.12)
└── .venv/            # 가상환경 (gitignore)
```

### Rules
- `pip install` 사용 금지 → `uv add` 사용
- `pip freeze` 사용 금지 → `uv lock` 사용
- `requirements.txt` 생성 금지 → `pyproject.toml` + `uv.lock` 사용
- `python -m venv` 사용 금지 → `uv venv` 또는 자동 생성
- `uv.lock` 파일은 반드시 Git에 커밋
- `.venv/` 디렉토리는 `.gitignore`에 추가
- Dockerfile에서도 `uv sync --frozen` 사용

### Dockerfile Example
```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0"]
```

## Spec-Driven Development Rules

1. **코드 생성 전 관련 Spec 문서를 반드시 읽는다**
2. **Spec에 없는 기능은 구현하지 않는다**
3. **Spec에 명시된 기술 스택만 사용한다** (`docs/TECH_STACK.md` 참조)
4. **생성된 코드에 Spec 참조를 명시한다** (e.g., `# Spec: FR-AI-002`)
5. **라이선스 정책 준수**: Apache 2.0 / MIT / BSD만 허용, GPL/AGPL/SSPL 금지

## Key Spec Documents
- PRD: `AI_DB_Monitoring_System_PRD_v3.3.md`
- Architecture: `ai-db-monitor-architecture-spec-v3.md`
- Tech Stack: `docs/TECH_STACK.md`
- Frontend Design: `docs/FRONTEND_DESIGN.md`
- Feature Specs: `docs/specs/`

## Frontend Commands
```bash
cd frontend
npm install        # Node.js 의존성
npm run dev        # Vite dev server
npm run build      # Production build
npm run test       # Vitest
npm run lint       # ESLint
```

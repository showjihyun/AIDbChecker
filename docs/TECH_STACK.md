# NeuralDB - Technology Stack Specification

> **Version**: 1.0
> **Date**: 2026-03-21
> **Architecture**: React (FE) + Python/FastAPI (BE) + PostgreSQL 16 (DB)
> **License Policy**: Apache 2.0 / MIT / BSD only (No GPL/AGPL/SSPL)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Presentation Layer                           │
│  React 18 + Vite + TailwindCSS + ECharts + Zustand              │
│  WebSocket (Socket.io-client) for real-time                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API / WebSocket / GraphQL(Strawberry)
┌──────────────────────────┴──────────────────────────────────────┐
│                     API Gateway Layer (FastAPI)                   │
│  FastAPI + Uvicorn + Strawberry(GraphQL) + Socket.io             │
│  MCP Server + A2A Gateway + OTel Collector                      │
│  JWT/OAuth2 Auth + RBAC + Rate Limiting                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                  Core Engine Layer (Python)                       │
│  Multi-Agent (LangGraph + CrewAI) + Celery Workers               │
│  Monitoring / Diagnosis / Remediation / Reporting Agents         │
│  RAG Pipeline + NL2SQL + Auto-Baselining + Auto Query Tuning    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                  Database Adapter Layer (Plugin)                  │
│  PostgreSQL Adapter (1s ASH + DDL Trigger + pgBouncer)           │
│  MySQL Adapter / MS-SQL Adapter (Phase 4)                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                  Infrastructure Layer                             │
│  PostgreSQL 16 (Meta+Metrics+Vector) + Valkey                      │
│  Docker + Kubernetes + Prometheus + OpenTelemetry                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Frontend (Presentation Layer)

| 기술 | 버전 | 라이선스 | 용도 |
|------|------|---------|------|
| **React** | 18+ | MIT | UI 프레임워크 |
| **Vite** | 6+ | MIT | 빌드 도구 (HMR, 번들링) |
| **TypeScript** | 5.4+ | Apache 2.0 | 타입 안전성 |
| **TailwindCSS** | 3.4+ | MIT | 유틸리티 CSS (디자인 토큰 기반) |
| **Zustand** | 5+ | MIT | 경량 상태 관리 |
| **TanStack Query** | 5+ | MIT | 서버 상태 관리 / 데이터 페칭 / 캐싱 |
| **TanStack Router** | 1+ | MIT | 타입 안전 라우팅 |
| **Apache ECharts** | 5+ | Apache 2.0 | 토폴로지 맵, ASH 히트맵, 시계열 차트 |
| **Socket.io-client** | 4+ | MIT | 실시간 메트릭 WebSocket 수신 |
| **React Hook Form** | 7+ | MIT | 폼 관리 (Playbook 편집기 등) |
| **Zod** | 3+ | MIT | 스키마 검증 (API 응답, 폼 데이터) |
| **clsx + tailwind-merge** | - | MIT | 조건부 클래스 유틸리티 |
| **date-fns** | 3+ | MIT | 날짜/시간 처리 |
| **Monaco Editor** | - | MIT | SQL/YAML 코드 에디터 (NL2SQL, Playbook) |
| **Material Symbols** | - | Apache 2.0 | 아이콘 시스템 |

### Frontend 폰트
| 폰트 | 역할 | 소스 |
|------|------|------|
| Space Grotesk | Headlines / Display | Google Fonts (OFL) |
| Inter | Body / Data / Labels | Google Fonts (OFL) |
| JetBrains Mono | Code / SQL / YAML | Google Fonts (OFL) |

---

## 3. Backend (API + Core Engine Layer)

### 3.1 API Framework

| 기술 | 버전 | 라이선스 | 용도 |
|------|------|---------|------|
| **Python** | 3.11+ | PSF | 런타임 |
| **FastAPI** | 0.115+ | MIT | REST API 프레임워크 |
| **Uvicorn** | 0.30+ | BSD 3-Clause | ASGI 서버 |
| **Strawberry** | 0.230+ | MIT | GraphQL (Code-First, async) |
| **python-socketio** | 5+ | MIT | WebSocket 실시간 통신 |
| **Pydantic** | 2+ | MIT | 데이터 검증 / 설정 관리 |
| **SQLAlchemy** | 2.0+ | MIT | ORM / DB 추상화 |
| **Alembic** | 1.13+ | MIT | DB 마이그레이션 |
| **asyncpg** | 0.29+ | Apache 2.0 | PostgreSQL 비동기 드라이버 |
| **python-jose** | 3+ | MIT | JWT 토큰 처리 |
| **passlib[bcrypt]** | 1.7+ | BSD | 비밀번호 해싱 |
| **httpx** | 0.27+ | BSD 3-Clause | 비동기 HTTP 클라이언트 |

### 3.2 AI / LLM

| 기술 | 버전 | 라이선스 | 용도 |
|------|------|---------|------|
| **LangChain** | 0.3+ | MIT | LLM 프레임워크 |
| **LangGraph** | 0.2+ | MIT | 멀티 에이전트 상태 그래프 |
| **CrewAI** | 0.80+ | MIT | 멀티 에이전트 오케스트레이션 |
| **OpenAI API** | - | 상용 SaaS | GPT-4o (온라인 모드) |
| **Anthropic API** | - | 상용 SaaS | Claude Sonnet (온라인 모드) |
| **Ollama** | - | MIT | 로컬 LLM 런타임 (오프라인 모드) |
| **vLLM** | - | Apache 2.0 | 고성능 LLM 서빙 (오프라인 모드) |
| **OpenLIT** | 1.0+ | Apache 2.0 | LLM Observability (토큰/지연/비용 자동 계측) |

### 3.3 AI/ML (데이터 분석)

| 기술 | 버전 | 라이선스 | 용도 |
|------|------|---------|------|
| **scikit-learn** | 1.4+ | BSD 3-Clause | Isolation Forest (이상 탐지) |
| **Prophet** | 1.1+ | MIT | 시계열 예측 / 베이스라인 학습 |
| **statsmodels** | 0.14+ | BSD 3-Clause | STL 분해 (시계열 분석) |
| **NumPy** | 1.26+ | BSD 3-Clause | 수치 연산 |
| **Pandas** | 2.2+ | BSD 3-Clause | 데이터 처리 |
| **PyTorch** | 2.3+ | BSD 3-Clause | MTL Shared Encoder + Task Heads (Phase 2 파인튜닝) |
| **transformers** | 4.40+ | Apache 2.0 | Pretrained Transformer 모델 로딩 (MTL Encoder) |

### 3.4 비동기 / 메시징

| 기술 | 버전 | 라이선스 | 용도 |
|------|------|---------|------|
| **Celery** | 5.4+ | BSD 3-Clause | 비동기 태스크 큐 (메트릭 수집, 에이전트 실행) |
| ~~**aiokafka**~~ | ~~0.10+~~ | ~~Apache 2.0~~ | ~~Kafka 비동기~~ — **ADR-011: 제거됨. Celery + Valkey로 대체** |
| **aio-pika** | 9+ | Apache 2.0 | RabbitMQ (Celery 브로커 대안) |

### 3.5 프로토콜 / Agent 통신

| 기술 | 버전 | 라이선스 | 용도 |
|------|------|---------|------|
| **MCP SDK** | 1.0+ | MIT | Model Context Protocol 서버 (외부 AI 도구 연동) |
| **A2A SDK** | 0.2+ | Apache 2.0 | Agent-to-Agent 프로토콜 (에이전트 발견/Task 라우팅) |
| **grpcio** | 1.64+ | Apache 2.0 | Agent 간 동기 RPC (Phase 3). 저지연 요청/응답 |
| **grpcio-tools** | 1.64+ | Apache 2.0 | Protocol Buffers 컴파일러 (`.proto` → Python stub) |
| **protobuf** | 5.27+ | BSD 3-Clause | gRPC 직렬화 포맷 (JSON 대비 ~10x 효율) |
| **grpcio-reflection** | 1.64+ | Apache 2.0 | gRPC 서비스 런타임 발견 (디버깅/테스트용) |
| **OpenTelemetry SDK** | 1.24+ | Apache 2.0 | 분산 트레이싱 / 메트릭 수집 |
| **opentelemetry-instrumentation-grpc** | 0.45+ | Apache 2.0 | gRPC 호출 자동 트레이싱 |

#### Agent 통신 하이브리드 전략 (Phase 3)

> **ADR-011**: Kafka 제거됨. Celery + Valkey가 모든 비동기를, gRPC가 에이전트 동기 통신을 처리합니다.

```
동기 (gRPC, 저지연 RPC):
  ├── Agent 간 직접 요청/응답 (RCA 요청 → 즉시 결과)
  ├── MCP → Agent 연동 (외부 Copilot → gRPC → Agent)
  ├── Health Check / Agent Discovery heartbeat
  └── DB Copilot ToT 분기별 동기 분석

비동기 (Celery + Valkey):
  ├── 메트릭 수집 태스크 (Celery Beat 스케줄링)
  ├── 인시던트 생성/갱신 태스크
  ├── 알림 디스패치 (Slack/Email/Webhook)
  ├── 감사 로그 / AI Decision Log
  ├── AIGC 리포트 주간 생성
  └── A2A 에이전트 간 비동기 태스크 (Phase 3)
```

### 3.6 RAG / Vector

| 기술 | 버전 | 라이선스 | 용도 |
|------|------|---------|------|
| **pgvector** | 0.7+ | PostgreSQL License | 벡터 임베딩 저장 / 유사도 검색 |
| **LangChain RAG** | - | MIT | RAG 파이프라인 (문서 로더 + 임베딩 + 리트리버) |
| **sentence-transformers** | 3+ | Apache 2.0 | 임베딩 모델 (로컬) |

---

## 4. Database Layer

| 기술 | 버전 | 라이선스 | 용도 |
|------|------|---------|------|
| **PostgreSQL** | 16+ | PostgreSQL License (MIT계열) | 메타 DB + 메트릭 저장 + 벡터 저장 |
| **pgvector** | 0.7+ | PostgreSQL License | 벡터 검색 (RAG) |
| **pg_partman** | 5+ | PostgreSQL License | 자동 테이블 파티셔닝 (시계열 메트릭) |
| **pg_cron** | 1.6+ | PostgreSQL License | 스케줄 작업 (다운샘플링, 정리) |
| **pg_stat_statements** | - | Built-in | 쿼리 통계 수집 |

### PostgreSQL 16 활용 전략
- **메트릭 저장**: 네이티브 파티셔닝 + pg_partman으로 시계열 데이터 관리 (QuestDB/TimescaleDB 대체)
- **ASH 데이터**: 파티션 테이블 (일별) + Materialized View로 다운샘플링
- **벡터 검색**: pgvector 확장으로 RAG 임베딩 저장
- **토폴로지**: JSONB + 재귀 CTE로 그래프 탐색
- **감사 로그**: JSONB 컬럼으로 유연한 이벤트 저장

---

## 5. Infrastructure

| 기술 | 버전 | 라이선스 | 용도 |
|------|------|---------|------|
| **Valkey** | 7+ | BSD 3-Clause | 캐시 (베이스라인, 세션, Agent 상태) + Celery 브로커 |
| ~~**Apache Kafka**~~ | ~~3.7+~~ | ~~Apache 2.0~~ | ~~이벤트 스트리밍~~ — **ADR-011: 제거됨. Celery + Valkey + gRPC로 대체** |
| **Docker** | 26+ | Apache 2.0 | 컨테이너화 |
| **Kubernetes** | 1.30+ | Apache 2.0 | 오케스트레이션 |
| **Prometheus** | 2.52+ | Apache 2.0 | **NeuralDB 자체** 시스템 메트릭 수집 (대상 DB 메트릭 아님) |
| **OpenTelemetry Collector** | 0.100+ | Apache 2.0 | 앱 트레이스 수신 / 의존성 추출 |

### 5.1 Self-Monitoring Stack (NeuralDB 자체 감시)

> **대상 DB 메트릭**은 자체 Adapter가 수집 → PostgreSQL 16 저장.
> **아래는 NeuralDB 시스템 자체를 감시하기 위한 스택.**

| 기술 | 라이선스 | 용도 |
|------|---------|------|
| **prometheus-fastapi-instrumentator** | MIT | FastAPI 자동 `/metrics` 노출 (요청수, 지연, 에러율) |
| **opentelemetry-instrumentation-fastapi** | Apache 2.0 | FastAPI 분산 트레이싱 자동 계측 |
| **opentelemetry-instrumentation-sqlalchemy** | Apache 2.0 | SQLAlchemy 쿼리 트레이싱 |
| **opentelemetry-instrumentation-celery** | Apache 2.0 | Celery 태스크 트레이싱 |
| **celery-exporter** | MIT | Celery Worker 메트릭 → Prometheus |
| **postgres_exporter** | Apache 2.0 | 시스템 DB(PostgreSQL 16) 메트릭 → Prometheus |
| **redis_exporter** | MIT | Valkey 메트릭 → Prometheus (호환) |
| ~~**kafka-exporter**~~ | ~~Apache 2.0~~ | ~~Kafka consumer lag~~ — **ADR-011: Kafka 제거로 불필요** |
| **openlit** | Apache 2.0 | LLM 파이프라인 메트릭 (토큰 사용량, 응답 지연, 비용) → Prometheus |

```
┌──────────────────────────────────────────────────────────────┐
│  NeuralDB Self-Monitoring Architecture                       │
│                                                              │
│  FastAPI ──┐                                                 │
│  Celery  ──┼── OpenTelemetry SDK ──► OTel Collector          │
│  Agents  ──┘         │                    │                  │
│                      │              (traces → Jaeger 등)     │
│                      ▼                                       │
│              /metrics endpoint                               │
│                      │                                       │
│  postgres_exporter ──┤                                       │
│  redis_exporter ─────┼──► Prometheus ──► System Health 탭    │
│  celery-exporter ────┘                   (React + ECharts)   │
│                                                              │
│  ※ Grafana 사용 안함 (AGPL) → 자체 React 대시보드            │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. Development Tools

### 6.1 Python Package Manager: uv (MUST)

> **pip 사용 금지. 모든 Python 패키지 관리는 반드시 `uv`를 사용한다.**

| 기술 | 버전 | 라이선스 | 용도 |
|------|------|---------|------|
| **uv** | 0.6+ | MIT / Apache 2.0 | Python 패키지/프로젝트/버전 통합 관리 |

**uv 채택 이유:**
- pip 대비 10~100배 빠른 의존성 해석 및 설치
- 결정론적 락파일(`uv.lock`)로 환경 간 완벽한 재현성 보장
- Python 버전 충돌 방지 (uv가 Python 버전 자체도 관리)
- pip, pip-tools, pipx, pyenv, virtualenv를 단일 도구로 대체

**금지 명령:**
| 금지 | 대체 |
|------|------|
| `pip install <pkg>` | `uv add <pkg>` |
| `pip install -r requirements.txt` | `uv sync` |
| `pip freeze > requirements.txt` | `uv lock` (자동 `uv.lock` 생성) |
| `python -m venv .venv` | `uv venv` (또는 `uv sync` 시 자동 생성) |
| `requirements.txt` 파일 생성 | `pyproject.toml` + `uv.lock` 사용 |

**필수 커밋 파일:** `pyproject.toml`, `uv.lock`, `.python-version`
**gitignore 대상:** `.venv/`

### 6.2 Tools

| 기술 | 버전 | 라이선스 | 용도 |
|------|------|---------|------|
| **Ruff** | 0.4+ | MIT | Python 린터 + 포매터 |
| **mypy** | 1.10+ | MIT | Python 타입 체커 |
| **pytest** | 8+ | MIT | Python 테스트 프레임워크 |
| **pytest-asyncio** | 0.23+ | Apache 2.0 | 비동기 테스트 |
| **Vitest** | 2+ | MIT | Frontend 단위 테스트 |
| **Playwright** | 1.44+ | Apache 2.0 | Frontend E2E 테스트 |
| **ESLint** | 9+ | MIT | JS/TS 린터 |
| **Prettier** | 3+ | MIT | JS/TS/CSS 포매터 |
| **Gitea** | 1.22+ | MIT | Git 호스팅 (자체 호스팅) |
| **Woodpecker CI** | 2+ | Apache 2.0 | CI/CD 파이프라인 |

---

## 7. Notification / Integration

| 기술 | 라이선스 | 용도 |
|------|---------|------|
| **slack-sdk** (Python) | MIT | Slack 알림 발송 |
| **aiosmtplib** | MIT | Email 알림 (비동기) |
| **httpx** | BSD | Webhook / PagerDuty 연동 |

---

## 8. Project Directory Structure

```
AIDbChecker/
├── frontend/                          # React + Vite + TypeScript
│   ├── public/
│   ├── src/
│   │   ├── api/                       # API 클라이언트 (TanStack Query)
│   │   │   ├── client.ts              # Axios/fetch 설정
│   │   │   ├── hooks/                 # useQuery/useMutation 커스텀 훅
│   │   │   └── types.ts              # API 응답 타입
│   │   ├── components/                # UI 컴포넌트
│   │   │   ├── layout/               # TopNav, SideNav, MainLayout
│   │   │   ├── dashboard/            # 메트릭 카드, 차트
│   │   │   ├── topology/             # 토폴로지 맵 (ECharts)
│   │   │   ├── diagnosis/            # RCA 패널, 인시던트 리스트
│   │   │   ├── ash/                  # ASH 히트맵, 세션 테이블
│   │   │   ├── playbook/            # Playbook 에디터, 감사 로그
│   │   │   ├── nl2sql/              # NL2SQL 챗 인터페이스
│   │   │   └── common/              # Button, Badge, Card, Input, Modal
│   │   ├── hooks/                    # 범용 커스텀 훅 (useWebSocket 등)
│   │   ├── stores/                   # Zustand 스토어
│   │   ├── routes/                   # TanStack Router 라우트
│   │   ├── lib/                      # 유틸리티 (cn, formatDate 등)
│   │   ├── styles/                   # 글로벌 CSS, tailwind 확장
│   │   └── types/                    # 공통 타입 정의
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                           # Python + FastAPI
│   ├── app/
│   │   ├── main.py                   # FastAPI 앱 진입점
│   │   ├── config.py                 # 환경 설정 (Pydantic Settings)
│   │   ├── api/                      # API 라우터
│   │   │   ├── v1/
│   │   │   │   ├── monitoring.py     # 메트릭 API
│   │   │   │   ├── diagnosis.py      # 진단 API
│   │   │   │   ├── topology.py       # 토폴로지 API
│   │   │   │   ├── ash.py            # ASH API
│   │   │   │   ├── playbook.py       # Playbook API
│   │   │   │   ├── nl2sql.py         # NL2SQL API
│   │   │   │   ├── auth.py           # 인증/인가 API
│   │   │   │   └── audit.py          # 감사 로그 API
│   │   │   └── deps.py              # 의존성 주입
│   │   ├── graphql/                  # Strawberry GraphQL
│   │   │   ├── schema.py
│   │   │   ├── queries/
│   │   │   ├── mutations/
│   │   │   └── subscriptions/        # 실시간 GraphQL 구독
│   │   ├── websocket/                # Socket.io 이벤트
│   │   │   ├── manager.py
│   │   │   └── events.py
│   │   ├── models/                   # SQLAlchemy 모델
│   │   │   ├── base.py
│   │   │   ├── db_instance.py
│   │   │   ├── metric.py
│   │   │   ├── incident.py
│   │   │   ├── playbook.py
│   │   │   └── ...
│   │   ├── schemas/                  # Pydantic 스키마 (Request/Response)
│   │   ├── services/                 # 비즈니스 로직
│   │   ├── agents/                   # AI 에이전트
│   │   │   ├── monitoring/           # 모니터링 에이전트
│   │   │   ├── diagnosis/            # 진단 에이전트 (RCA)
│   │   │   ├── remediation/          # 자가 치유 에이전트
│   │   │   ├── reporting/            # 리포팅 에이전트 (AIGC)
│   │   │   └── base.py              # 에이전트 기본 클래스
│   │   ├── adapters/                 # DB 어댑터 (Plugin)
│   │   │   ├── base.py              # 어댑터 인터페이스
│   │   │   ├── postgresql/
│   │   │   ├── mysql/
│   │   │   └── mssql/
│   │   ├── collectors/               # 메트릭 수집기
│   │   ├── analyzers/                # 분석 엔진
│   │   │   ├── baseline.py           # Auto-Baselining
│   │   │   ├── anomaly.py            # 이상 탐지
│   │   │   └── query.py              # 쿼리 분석
│   │   ├── rag/                      # RAG 파이프라인
│   │   ├── mcp/                      # MCP Server
│   │   ├── a2a/                      # A2A Gateway
│   │   ├── tasks/                    # Celery 태스크
│   │   ├── middleware/               # CORS, Auth, Logging
│   │   └── utils/                    # 유틸리티
│   ├── migrations/                   # Alembic 마이그레이션
│   │   ├── versions/
│   │   └── env.py
│   ├── playbooks/                    # Playbook YAML 정의
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── Dockerfile
│
├── infra/                             # 인프라 설정
│   ├── docker/
│   │   ├── docker-compose.yml        # 로컬 개발 환경
│   │   ├── docker-compose.prod.yml
│   │   └── Dockerfile.frontend
│   ├── k8s/                          # Kubernetes 매니페스트
│   ├── monitoring/                   # Prometheus, OTel 설정
│   └── scripts/                      # 배포/초기화 스크립트
│
├── docs/                              # 문서
├── skills/                            # Claude Code 스킬
├── .claude/                           # Claude Code 설정
└── CLAUDE.md                          # 프로젝트 컨텍스트
```

---

## 9. Key Design Decisions

### 9.1 Why React (not Next.js)?
- SPA로 충분 (SSR/SSG 불필요한 내부 모니터링 도구)
- Vite 기반으로 빠른 HMR과 빌드
- 온프레미스 배포 시 정적 파일 서빙이 단순

### 9.2 Why FastAPI (not NestJS)?
- Core Engine(AI/ML)이 Python이므로 백엔드도 Python으로 통일 → 코드 공유, 배포 단순화
- FastAPI는 async 네이티브, 자동 OpenAPI 문서, Pydantic 통합
- Strawberry로 GraphQL Code-First 지원
- LangChain/LangGraph/CrewAI 등 AI 프레임워크와 네이티브 통합

### 9.3 Why PostgreSQL 16 (unified)?
- 메타 DB + 시계열 메트릭 + 벡터 검색을 단일 PostgreSQL로 통합
- 네이티브 파티셔닝 + pg_partman으로 시계열 관리 (QuestDB/TimescaleDB 대체)
- pgvector로 RAG 벡터 저장 (별도 벡터 DB 불필요)
- 운영 복잡도 감소, 라이선스 리스크 제거

### 9.4 Why Valkey (not Redis)?
- Redis 7.4+ RSALv2/SSPL 라이선스 회피
- Linux Foundation 관리, Redis API 100% 호환
- BSD 3-Clause 라이선스

---

## 10. Version Compatibility Matrix

| Component | Min Version | Tested Version |
|-----------|------------|----------------|
| Python | 3.11 | 3.12 |
| Node.js | 20 LTS | 22 LTS |
| PostgreSQL | 16.0 | 16.4 |
| Valkey | 7.0 | 8.0 |
| Docker | 26.0 | 27.0 |
| Kubernetes | 1.30 | 1.31 |

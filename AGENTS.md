# AGENTS.md — NeuralDB Project Intelligence

> 이 문서는 CLAUDE.md, README.md에 기술되지 않은 **프로젝트 고유의 맥락, 함정, 판단 기준**을 기록합니다.
> AI 에이전트(Claude Code 등)가 이 프로젝트에서 작업할 때 반드시 참고해야 할 내용입니다.

---

## 1. 프로젝트 특이성

### 1.1 단일 PostgreSQL 16으로 3가지 역할 수행

이 프로젝트는 PostgreSQL 16 하나로 **메타 DB + 시계열 메트릭 + 벡터 검색**을 모두 처리합니다.
별도의 TimescaleDB, QuestDB, Pinecone, Weaviate 등을 사용하지 않습니다.

| 역할 | 구현 방식 | 주의사항 |
|------|----------|---------|
| 메타 DB | 일반 테이블 | 표준 CRUD |
| 시계열 메트릭 | 네이티브 파티셔닝 + pg_partman | `PARTITION BY RANGE (sampled_at)` 필수. TimescaleDB 함수(`time_bucket` 등) 사용 금지 |
| 벡터 검색 | pgvector 확장 | `CREATE EXTENSION vector`. 별도 벡터 DB 의존 금지 |

**함정**: 시계열 관련 코드를 작성할 때 TimescaleDB Continuous Aggregate 문법을 쓰지 말 것. Materialized View + pg_cron으로 다운샘플링을 구현해야 합니다.

### 1.2 Backend 단일 레이어 (Python Only)

원래 아키텍처 스펙(v3.0)에는 NestJS API + Python Engine 2층 구조가 있었으나, **v3.2에서 Python/FastAPI 단일 레이어로 통합**되었습니다.

- 아키텍처 스펙의 "NestJS", "Apollo GraphQL", "TypeORM" 언급은 **폐기됨**
- GraphQL은 **Strawberry** (Python Code-First)로 대체
- ORM은 **SQLAlchemy 2.0 async** 단일 사용
- `backend/` 디렉토리가 API + Core Engine + Agent를 모두 포함

**함정**: `ai-db-monitor-architecture-spec-v3.md`의 기술 스택 테이블에 NestJS가 남아있으나 무시할 것. `docs/TECH_STACK.md`가 최신 진실입니다.

### 1.3 Valkey ≠ Redis (미세한 차이)

Valkey는 Redis API 99.9% 호환이지만, 코드에서 주의할 점:

- 패키지: `redis` (Python redis 클라이언트)를 그대로 사용 → Valkey 서버에 연결
- 환경변수: `VALKEY_URL`로 명명하되, 실제 연결 문자열은 `redis://valkey:6379/0` 형태
- Docker 이미지: `valkey/valkey:8-alpine` (redis 이미지 아님)
- Celery 브로커 URL도 `redis://` 프로토콜 사용 (Valkey가 이를 수용)
- **Redis 전용 모듈(RedisJSON, RediSearch, RedisGraph)은 사용 금지** — Valkey에 없음

### 1.4 라이선스 지뢰밭

이 프로젝트는 **독립 솔루션/SaaS 전환**을 목표로 하므로, 허용적 라이선스만 사용합니다.

자주 실수하는 패턴:
| 유혹 | 문제 | 대체 |
|------|------|------|
| Grafana 대시보드 임베딩 | AGPL v3 | 자체 React + ECharts 대시보드 |
| `redis-py`의 `Redis.json()` 사용 | RedisJSON = RSALv2 | 일반 `SET/GET` + JSON 직렬화 |
| TimescaleDB `time_bucket()` | TSL | PostgreSQL `date_trunc()` + Materialized View |
| Elastic APM / Kibana | SSPL | OpenTelemetry + Prometheus |
| MongoDB | SSPL | PostgreSQL JSONB |

### 1.5 2-Tier Hybrid Adapter (수집 전략)

대상 DB 메트릭 수집은 **Phase에 따라 2단계**로 구현됩니다:

| Tier | 이름 | 배포 위치 | 해상도 | Phase |
|------|------|----------|--------|-------|
| **Tier 2** | Remote Adapter | NeuralDB 백엔드 | RTT 의존 (1~10초) | Phase 1~2 |
| **Tier 1** | Lightweight Collector | 대상 DB 서버 | 항상 1초 | Phase 3+ |

- Phase 1 코드에서 `PostgreSQLRemoteAdapter`를 구현할 때, **`BaseAdapter` 인터페이스는 Phase 3의 `PostgreSQLLocalCollector`도 지원 가능하도록 설계되어 있음**
- Collector 미설치 시 Remote Adapter로 자동 폴백 → 해상도만 다운그레이드
- Remote Adapter 코드에 `asyncpg.create_pool(dsn)` 사용 시, dsn이 원격 주소임을 주석으로 명시할 것

**함정**: Phase 1에서 "어차피 나중에 Collector로 바꿀 건데"라며 Adapter를 대충 만들지 말 것. Collector도 같은 `BaseAdapter` 인터페이스를 구현하므로, `collect_metrics()` / `collect_ash()` 반환 타입이 Phase 3에서도 그대로 사용됨.

> 상세 검토: `docs/review/001-adapter-vs-agent-collection.md`

### 1.6 1초 수집의 현실적 제약

1초 메트릭 수집은 대상 DB에 부하를 줍니다. 코드에서 반드시:

- `pg_stat_activity` 조회는 **읽기 전용 커넥션 풀** 사용 (모니터링 전용)
- ASH 샘플링 쿼리에 `statement_timeout = '500ms'` 설정
- 수집 실패 시 silent skip (대상 DB 장애를 악화시키지 않음)
- Hot 메트릭만 1초, Warm은 10초, Cold는 1분 — 모든 메트릭을 1초로 수집하지 않음

### 1.7 Adaptive Autonomy Level과 코드 분기

모든 자동화 코드에는 autonomy level 체크가 필요합니다:

```python
# 모든 remediation action 전에 반드시
if action.risk_level > current_autonomy_level.max_allowed_risk:
    await escalate_to_human(action)
    return

# Level 0: 알림만
# Level 1: 추천 (사람 승인 필요)
# Level 2: 승인 후 실행
# Level 3: 실행 후 보고
# Level 4: 완전 자율
```

자동 실행 코드를 작성할 때 autonomy check 없이 `execute()`를 직접 호출하면 **아키텍처 리뷰에서 거부**됩니다.

---

## 2. 파일 간 우선순위 (충돌 시)

Spec 문서 간 내용이 충돌할 경우, 아래 순서로 최신/우선을 판단합니다:

```
1. docs/TECH_STACK.md          ← 기술 스택 최종 진실 (v3.2 반영)
2. AI_DB_Monitoring_System_PRD_v3.3.md  ← 요구사항 + 방법론
3. docs/FRONTEND_DESIGN.md     ← UI/UX 디자인 토큰
4. ai-db-monitor-architecture-spec-v3.md  ← 아키텍처 (일부 구 스택 잔존 주의)
5. ai-db-monitor-license-audit.jsx  ← 라이선스 감사 (v3.1 기준, 여전히 유효)
```

`architecture-spec-v3.md`에 NestJS/TimescaleDB가 남아있으나, `TECH_STACK.md`의 FastAPI/PostgreSQL 16이 우선합니다.

---

## 3. 코드 생성 시 흔한 실수

### 3.1 Python

| 실수 | 올바른 방식 |
|------|------------|
| `pip install fastapi` | `uv add fastapi` |
| `from sqlalchemy import Column, Integer` | `from sqlalchemy.orm import Mapped, mapped_column` (2.0 스타일) |
| `session.query(Model).filter()` | `select(Model).where()` (2.0 스타일) |
| `sync def endpoint()` | `async def endpoint()` (FastAPI async 필수) |
| `import redis; r = redis.Redis()` | 연결 URL에 `VALKEY_URL` 환경변수 사용 |
| `requirements.txt` 생성 | `pyproject.toml` + `uv.lock` 사용 |
| `print()` 디버깅 | `structlog` 또는 `logging` + OpenTelemetry |

### 3.2 Frontend (React)

| 실수 | 올바른 방식 |
|------|------------|
| `next/link`, `next/image` | React SPA — Next.js 아님. `react-router` 또는 TanStack Router |
| `getServerSideProps` | 없음. TanStack Query로 클라이언트 데이터 페칭 |
| `#000000` 배경색 | `#0b1326` (surface 토큰). 순수 검정 금지 |
| `border: 1px solid #ccc` | 배경색 차이로 구분 (No-Line Rule) |
| `className="animate-bounce"` | `ease-out` 전환만 허용. 탄성 애니메이션 금지 |
| `import axios from 'axios'` | TanStack Query + 네이티브 fetch 또는 ky |
| `useState` 남용 | 서버 상태는 TanStack Query, 글로벌은 Zustand |

### 3.3 Database

| 실수 | 올바른 방식 |
|------|------------|
| `SERIAL` / `BIGSERIAL` PK | `UUID` + `gen_random_uuid()` |
| `OFFSET` 기반 페이지네이션 | 커서 기반 페이지네이션 |
| `SELECT *` | 필요한 컬럼만 명시 |
| `CREATE INDEX idx ON big_table(col)` | `CREATE INDEX CONCURRENTLY` (프로덕션 무중단) |
| TimescaleDB `create_hypertable()` | `PARTITION BY RANGE` + pg_partman |
| `TIMESTAMP` | `TIMESTAMPTZ` (timezone-aware 필수) |

---

## 4. Skills 구성

### 4.1 프로젝트 커스텀 Skills (19종) — `skills/`

| Category | Skill | Trigger | 용도 |
|----------|-------|---------|------|
| **초기화** | `init-project` | `/init-project [module]` | 프로젝트 구조 스캐폴딩 (PRD v3.2 기반) |
| **검증** | `review-arch` | `/review-arch [path]` | Spec 준수 여부 검증 (TECH_STACK + AGENTS.md 기반) |
| **디자인** | `stitch-sync` | `/stitch-sync [all]` | Google Stitch 디자인 동기화 |
| **FastAPI** | `gen-fastapi-route` | `/gen-fastapi-route [name] [method]` | API 라우트 + 서비스 + 스키마 |
| | `gen-pydantic-model` | `/gen-pydantic-model [name]` | Pydantic v2 Request/Response |
| **DB** | `gen-sqlalchemy-model` | `/gen-sqlalchemy-model [name]` | SQLAlchemy 2.0 ORM 모델 |
| | `gen-alembic-migration` | `/gen-alembic-migration [desc]` | Alembic 마이그레이션 스크립트 |
| | `db-adapter` | `/db-adapter [db-type] [feature] [mode]` | DB 어댑터 플러그인 (Remote/Local) |
| **React** | `gen-component` | `/gen-component [name] [screen]` | Stitch 디자인 기반 React 컴포넌트 (SPA) |
| | `gen-react-hook` | `/gen-react-hook [name] [type]` | TanStack Query / WebSocket / Zustand 훅 |
| | `gen-echarts` | `/gen-echarts [chart-type]` | ECharts 차트 (시계열/토폴로지/히트맵) |
| **AI/Agent** | `gen-agent` | `/gen-agent [name] [level]` | LangGraph/CrewAI 에이전트 |
| | `gen-rag-pipeline` | `/gen-rag-pipeline [kb] [source]` | RAG 파이프라인 (pgvector) |
| | `gen-mcp-tool` | `/gen-mcp-tool [name] [type]` | MCP Server 도구/리소스 |
| **Infra** | `gen-celery-task` | `/gen-celery-task [name] [schedule]` | Celery 비동기 태스크 |
| | `gen-websocket` | `/gen-websocket [ns] [events]` | python-socketio 이벤트 핸들러 |
| | `gen-docker` | `/gen-docker [target]` | Docker/Compose 설정 (uv 기반) |
| **공통** | `gen-playbook` | `/gen-playbook [name] [db-type]` | Playbook-as-Code YAML |
| | `gen-test` | `/gen-test [path] [type]` | 4-Layer 테스트 (FE Unit/BE Unit/Integration/E2E) |

> **삭제된 Skills**: `gen-api` (NestJS 구 스택 → `gen-fastapi-route`로 통합), `gen-schema` (TypeORM 구 스택 → `gen-sqlalchemy-model` + `gen-alembic-migration`으로 분리)

### 4.2 Vercel Skills (6종) — `.agents/skills/` → `.claude/skills/` symlink

| Skill | 용도 | 참고 |
|-------|------|------|
| `vercel-react-best-practices` | React 40+ 성능 최적화 규칙 | **핵심**. 모든 React 코드에 적용 |
| `vercel-composition-patterns` | React 컴포지션 패턴 가이드 | 컴포넌트 설계 시 참고 |
| `web-design-guidelines` | 웹 디자인 가이드라인 | UI 작업 시 참고 |
| `deploy-to-vercel` | Vercel 배포 | 이 프로젝트는 온프레미스 우선이므로 참고용 |
| `vercel-cli-with-tokens` | Vercel CLI 토큰 관리 | 참고용 |
| `vercel-react-native-skills` | React Native 스킬 | 이 프로젝트에는 불필요 (참고용) |

### 4.3 Skills 파일 위치 규칙

```
skills/                    ← 원본 (프로젝트 커스텀, Git 추적)
.claude/skills/            ← Claude Code가 읽는 위치 (커스텀 복사 + Vercel symlink)
.agents/skills/            ← npx skills가 설치한 위치 (Vercel 원본)
```

- 커스텀 스킬 수정 시 `skills/`에서 수정 후 `.claude/skills/`에 복사
- Vercel 스킬은 `.agents/skills/`에서 `.claude/skills/`로 자동 symlink

---

## 5. 환경별 차이

### 5.1 Online vs Offline AI

이 프로젝트는 **인터넷 차단 환경(에어갭)**에서도 동작해야 합니다.

```python
# config.py
class AIConfig:
    mode: Literal["online", "offline"] = "online"

    # Online
    openai_model: str = "gpt-4o"
    claude_model: str = "claude-sonnet-4-20250514"

    # Offline (에어갭)
    ollama_model: str = "mistral:7b"  # 또는 qwen2.5:14b
    vllm_model: str = "mistral-7b-instruct"
```

- 모든 LLM 호출은 `AIConfig.mode`에 따라 분기
- 오프라인 모드에서는 임베딩도 `sentence-transformers` 로컬 모델 사용
- 하드코딩된 `openai.ChatCompletion.create()` 호출 금지 → LangChain 추상화 사용

### 5.2 3종 메트릭 흐름 구분 (가장 혼동하기 쉬운 부분)

| 구분 | 무엇을 | 어떻게 수집 | 어디에 저장 | Prometheus? |
|------|--------|-----------|-----------|-------------|
| **대상 DB 메트릭** | 고객 PostgreSQL/MySQL의 CPU, 세션, 쿼리 | 자체 Adapter가 `pg_stat_*` 직접 조회 (1초) | `metric_samples` 테이블 (시스템 PostgreSQL 16) | **사용 안함** |
| **자체 시스템 메트릭** | NeuralDB FastAPI/Celery/Kafka/Valkey 상태 | OpenTelemetry SDK + Exporter | **Prometheus** | **사용함** |
| **자체 시스템 트레이스** | API 요청 → Agent → DB 호출 분산 추적 | OpenTelemetry SDK | OTel Collector → (옵션: Jaeger) | 해당 없음 |

**함정**: "메트릭을 Prometheus에 저장하면 되지 않나?"
- 대상 DB 메트릭은 **1초 해상도 + ASH + Wait Event** → Prometheus 15초 scrape로 불가능
- 대상 DB에 exporter 설치 요구도 비현실적 (고객 환경 변경 불가)
- 따라서 대상 DB는 Adapter 방식, 자체 시스템만 Prometheus

### 5.3 모니터링 대상 DB vs 시스템 자체 DB

| 구분 | 설명 | 커넥션 |
|------|------|--------|
| **대상 DB** | 모니터링하는 고객의 PostgreSQL/MySQL/MSSQL | 읽기 전용 (`pg_monitor` 역할) |
| **시스템 DB** | NeuralDB 자체 메타/메트릭 저장 PostgreSQL 16 | 읽기+쓰기 (full access) |

- 대상 DB에 `CREATE INDEX`, `ALTER TABLE` 등 쓰기 작업은 **반드시 Playbook + Autonomy Level 체크** 후에만 실행
- 시스템 DB에는 자유롭게 쓰기 가능
- 두 DB의 커넥션 풀을 절대 혼용하지 않음
- 시스템 DB 자체의 헬스는 `postgres_exporter` → Prometheus로 별도 감시

---

## 6. 네이밍 컨벤션

| 대상 | 컨벤션 | 예시 |
|------|--------|------|
| Python 파일/모듈 | snake_case | `metric_collector.py` |
| Python 클래스 | PascalCase | `MetricCollector` |
| Python 상수 | UPPER_SNAKE | `MAX_RETRY_COUNT` |
| FastAPI 라우터 prefix | kebab-case | `/api/v1/db-instances` |
| SQLAlchemy 테이블 | snake_case 복수형 | `metric_samples` |
| React 컴포넌트 파일 | PascalCase | `TopologyMap.tsx` |
| React 훅 | camelCase + use 접두사 | `useMetrics.ts` |
| Zustand 스토어 | camelCase + Store 접미사 | `incidentStore.ts` |
| CSS 토큰 (Tailwind) | kebab-case | `surface-container-high` |
| Playbook YAML | kebab-case | `lock-remediation.yaml` |
| Spec 문서 ID | `FS-{MODULE}-{NNN}` | `FS-DASH-001` |
| 요구사항 ID | `FR-{CATEGORY}-{NNN}` | `FR-AI-002` |

# AGENTS.md — NeuralDB Project Intelligence

> 이 문서는 AI 에이전트(Claude Code, OpenAI Codex, Cursor, Windsurf, GitHub Copilot 등)가
> 이 프로젝트에서 작업할 때 반드시 참고해야 할 **맥락, 규칙, 함정**을 기록합니다.
>
> **Scope**: 하위 디렉토리에 별도 `AGENTS.md`가 없는 한, 이 파일이 전체 저장소에 적용됩니다.
> **`@` 접두사**: 프로젝트 루트 기준 상대 경로. 해당 파일을 읽어 컨텍스트를 확보합니다.

---

## 1. Quick Reference — Commands

> 에이전트가 가장 먼저 참조하는 섹션. 실제 플래그와 옵션을 포함합니다.

### Backend (Python / FastAPI)

```bash
cd backend
uv sync                                    # 의존성 설치 (pip 금지)
uv run uvicorn app.main:app --reload       # 개발 서버 (port 8000)
uv run pytest                              # 전체 테스트
uv run pytest tests/unit/test_adapter.py   # 단일 파일 테스트
uv run ruff check .                        # 린트
uv run ruff format .                       # 포맷
uv run mypy app/                           # 타입 체크
uv run alembic upgrade head                # DB 마이그레이션 적용
uv run alembic revision --autogenerate -m "desc"  # 마이그레이션 생성
uv run celery -A app.tasks worker -l info  # Celery 워커
```

### Frontend (React / Vite)

```bash
cd frontend
npm install          # 의존성 설치
npm run dev          # Vite dev server (port 3000)
npm run build        # Production build
npm run test         # Vitest 단위 테스트
npm run test:e2e     # Playwright E2E
npm run lint         # ESLint
npm run format       # Prettier
```

### Infrastructure

```bash
cd infra/docker
docker compose up -d postgres valkey kafka   # 인프라만 기동
docker compose up -d                         # 전체 기동
docker compose down                          # 전체 중지
```

---

## 2. Task Boundaries

### ✅ Always Do

- 코드 생성 전 관련 Spec 문서 읽기 (`@docs/specs/`)
- 생성된 코드에 Spec 참조 주석 명시 (`# Spec: FR-AI-002`)
- `@docs/TECH_STACK.md`에 있는 기술만 사용
- 라이선스 확인: Apache 2.0 / MIT / BSD만 허용
- Python은 `uv` 사용, `async def`, SQLAlchemy 2.0 스타일
- DB 컬럼: `UUID` PK, `TIMESTAMPTZ`, 커서 기반 페이지네이션
- 테스트 작성 후 `uv run pytest` / `npm run test` 통과 확인
- 변경 전 `git status` 확인, 토픽 브랜치에서 작업

### ⚠️ Ask First

- production 의존성 추가 (`uv add` / `npm install`)
- DB 스키마 변경 (Alembic 마이그레이션 리뷰 필수)
- 대상 DB에 대한 쓰기 작업 (Playbook + Autonomy Level 체크)
- `@docs/specs/` 의 Spec 문서 구조 변경
- Docker/인프라 설정 수정
- 인증/인가 흐름 변경
- Autonomy Level 변경

### 🚫 Never Do

- `pip install` 사용 (→ `uv add`)
- `requirements.txt` 생성 (→ `pyproject.toml` + `uv.lock`)
- GPL/AGPL/SSPL 라이선스 패키지 도입
- TimescaleDB 함수 (`time_bucket`, `create_hypertable`) 사용
- Redis 전용 모듈 (RedisJSON, RediSearch, RedisGraph) 사용
- Next.js 패턴 (`getServerSideProps`, `next/link`) 사용
- Grafana/Kibana/MongoDB 등 라이선스 위반 기술 도입
- `main` 브랜치에 직접 push
- Spec 없이 기능 구현
- 대상 DB와 시스템 DB의 커넥션 풀 혼용
- `dump.rdb`, `*.log`, `.env`, `node_modules/`, `.venv/` 커밋
- Autonomy check 없이 `execute()` 직접 호출

---

## 3. Project Context

### @3.1 단일 PostgreSQL 16 = 3가지 역할

PostgreSQL 16 하나로 **메타 DB + 시계열 메트릭 + 벡터 검색**을 모두 처리합니다.

| 역할 | 구현 방식 | 참조 |
|------|----------|------|
| 메타 DB | 일반 테이블 (CRUD) | @docs/specs/data-model/ERD.md |
| 시계열 메트릭 | 네이티브 파티셔닝 + pg_partman | @docs/specs/data-model/MIGRATION_SPEC.md |
| 벡터 검색 | pgvector 확장 | @docs/specs/ai/LIGHTWEIGHT_RAG_SPEC.md |

**함정**: `PARTITION BY RANGE (sampled_at)` 필수. TimescaleDB Continuous Aggregate 문법 금지. Materialized View + pg_cron으로 다운샘플링.
근거: @docs/ADR/002-postgresql16-unified.md

### @3.2 Backend 단일 레이어 (Python Only)

Architecture Spec v3.0의 NestJS 2층 구조는 **v3.2에서 Python/FastAPI 단일 레이어로 통합**.

- `architecture-spec-v3.md`의 NestJS, Apollo GraphQL, TypeORM 언급은 **폐기됨**
- GraphQL → **Strawberry** (Python Code-First) / ORM → **SQLAlchemy 2.0 async**
- 근거: @docs/ADR/001-fastapi-over-nestjs.md
- 최종 진실: @docs/TECH_STACK.md

### @3.3 Valkey ≠ Redis

| 항목 | 값 |
|------|-----|
| Python 패키지 | `redis` 클라이언트 → Valkey 서버 연결 |
| 환경변수 | `VALKEY_URL` (연결 문자열은 `redis://valkey:6379/0`) |
| Docker 이미지 | `valkey/valkey:8-alpine` |
| **금지** | Redis 전용 모듈 (RedisJSON, RediSearch, RedisGraph) |

근거: @docs/ADR/003-valkey-over-redis.md

### @3.4 라이선스 지뢰밭

독립 솔루션/SaaS 전환 목표 → 허용적 라이선스만 사용.

| 유혹 | 문제 | 대체 |
|------|------|------|
| Grafana 임베딩 | AGPL v3 | 자체 React + ECharts |
| RedisJSON | RSALv2 | `SET/GET` + JSON 직렬화 |
| TimescaleDB | TSL | `date_trunc()` + Materialized View |
| Elastic APM / Kibana | SSPL | OpenTelemetry + Prometheus |
| MongoDB | SSPL | PostgreSQL JSONB |

참조: @ai-db-monitor-license-audit.jsx

### @3.5 2-Tier Hybrid Adapter (수집 전략)

| Tier | 이름 | 배포 위치 | 해상도 | Phase |
|------|------|----------|--------|-------|
| Tier 2 | Remote Adapter | NeuralDB 백엔드 | RTT 의존 | Phase 1~2 |
| Tier 1 | Lightweight Collector | 대상 DB 서버 | 항상 1초 | Phase 3+ |

- `BaseAdapter` 인터페이스는 Phase 3의 `PostgreSQLLocalCollector`도 지원
- `collect_metrics()` / `collect_ash()` 반환 타입이 Phase 3에서도 그대로 사용됨 — 대충 만들지 말 것
- 근거: @docs/ADR/006-hybrid-adapter-collection.md, @docs/review/001-adapter-vs-agent-collection.md

### @3.6 1초 수집의 현실적 제약

- `pg_stat_activity` 조회 → **읽기 전용 커넥션 풀** 사용
- ASH 샘플링 쿼리에 `statement_timeout = '500ms'`
- 수집 실패 → silent skip (대상 DB 장애 악화 방지)
- Hot 1초 / Warm 10초 / Cold 1분 — 전부 1초로 수집하지 않음
- 참조: @docs/MVP.md (Section 2.2)

### @3.7 Adaptive Autonomy Level

모든 자동화 코드에 autonomy level 체크 필수:

```python
# GOOD — 모든 remediation action 전에 반드시
if action.risk_level > current_autonomy_level.max_allowed_risk:
    await escalate_to_human(action)
    return

# Level 0: 알림만 / Level 1: 추천 / Level 2: 승인 후 실행
# Level 3: 실행 후 보고 / Level 4: 완전 자율

# BAD — autonomy check 없이 직접 호출 → 아키텍처 리뷰에서 거부
await execute(action)
```

참조: @docs/specs/agents/AGENT_SPEC.md

### @3.8 Online vs Offline AI

인터넷 차단 환경(에어갭)에서도 동작해야 합니다.

```python
class AIConfig:
    mode: Literal["online", "offline"] = "online"
    # Online: GPT-4o, Claude Sonnet
    # Offline: Ollama mistral:7b, vLLM
```

- 모든 LLM 호출은 `AIConfig.mode`에 따라 분기
- 하드코딩 `openai.ChatCompletion.create()` 금지 → LangChain 추상화 사용
- 참조: @docs/specs/ai/COPILOT_SPEC.md

### @3.9 3종 메트릭 흐름 (가장 혼동하기 쉬움)

| 구분 | 수집 방식 | 저장 | Prometheus? |
|------|----------|------|-------------|
| **대상 DB 메트릭** | 자체 Adapter (1초) | `metric_samples` 테이블 | **미사용** |
| **자체 시스템 메트릭** | OpenTelemetry SDK | **Prometheus** | **사용** |
| **자체 시스템 트레이스** | OpenTelemetry SDK | OTel Collector | 해당 없음 |

**함정**: 대상 DB 메트릭을 Prometheus에 저장하려 하지 말 것 (1초 해상도 + ASH → 15초 scrape 불가).

---

## 4. Working Guidelines

- **최소 변경 원칙**: Spec에 정의된 범위만 구현. 관련 없는 리팩토링을 같은 PR에 섞지 않음
- **기존 스타일 준수**: 새 패턴을 도입하지 말고 주변 코드와 일치시킴
- **Backportable 변경**: 커밋은 단일 목적, 원자적으로 유지
- **코멘트 원칙**: 코드를 재기술하지 말고, 비명시적 동작만 설명

---

## 5. Code Patterns — Good vs Bad

### @5.1 Python

```python
# GOOD — SQLAlchemy 2.0 async
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import select

async def get_instance(session: AsyncSession, id: UUID) -> DBInstance:
    stmt = select(DBInstance).where(DBInstance.id == id)
    result = await session.execute(stmt)
    return result.scalar_one()

# BAD — Legacy 1.x style
from sqlalchemy import Column, Integer
session.query(DBInstance).filter(DBInstance.id == id).first()
```

```python
# GOOD — Valkey 연결
import redis.asyncio as aioredis
valkey = aioredis.from_url(settings.VALKEY_URL)

# BAD — 하드코딩 Redis
r = redis.Redis(host="localhost", port=6379)
```

### @5.2 Frontend (React)

```tsx
// GOOD — TanStack Query + 디자인 토큰
import { useQuery } from '@tanstack/react-query';

function Dashboard() {
  const { data } = useQuery({ queryKey: ['metrics'], queryFn: fetchMetrics });
  return <div className="bg-[#0b1326]">...</div>;  // surface 토큰
}

// BAD — Next.js 패턴 + 순수 검정
import Link from 'next/link';           // React SPA — Next.js 아님
export async function getServerSideProps() {}  // 존재하지 않음
<div className="bg-black">             // #000000 금지
<div className="border border-gray-300"> // No-Line Rule 위반
```

### @5.3 Database

```sql
-- GOOD
CREATE TABLE metric_samples (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    sampled_at TIMESTAMPTZ NOT NULL,
    ...
) PARTITION BY RANGE (sampled_at);

CREATE INDEX CONCURRENTLY idx_metrics_time ON metric_samples (sampled_at);

-- BAD
CREATE TABLE metric_samples (
    id SERIAL PRIMARY KEY,              -- UUID 사용
    sampled_at TIMESTAMP,               -- TIMESTAMPTZ 사용
);
SELECT * FROM metric_samples OFFSET 100; -- 커서 페이지네이션 사용
```

---

## 6. Files to Avoid Touching

| 파일/디렉토리 | 이유 |
|--------------|------|
| `.env`, `.env.local` | 시크릿 포함 — `.env.example`만 수정 |
| `uv.lock` | `uv add/remove` 로 자동 갱신 — 직접 수정 금지 |
| `package-lock.json` | `npm install` 로 자동 갱신 |
| `.venv/`, `node_modules/` | 런타임 아티팩트 — 커밋 대상 아님 |
| `dump.rdb`, `*.log`, `*.pid` | 로컬 런타임 잔재물 |
| `docs/screenshots/*.png` | 바이너리 — 별도 프로세스로 생성 |
| `ai-db-monitor-architecture-spec-v3.md` | 구 스택 잔존. 참고만 하고 수정하지 말 것. `TECH_STACK.md`가 최종 진실 |

---

## 7. Document Priority (충돌 시)

```
1. @docs/TECH_STACK.md                      ← 기술 스택 최종 진실
2. @AI_DB_Monitoring_System_PRD_v3.3.md     ← 요구사항 + 방법론
3. @docs/MVP.md                             ← Phase 1 범위
4. @docs/FRONTEND_DESIGN.md                 ← UI/UX 디자인 토큰
5. @ai-db-monitor-architecture-spec-v3.md   ← 아키텍처 (구 스택 잔존 주의)
```

---

## 8. Naming Conventions

| 대상 | 컨벤션 | 예시 |
|------|--------|------|
| Python 파일 | snake_case | `metric_collector.py` |
| Python 클래스 | PascalCase | `MetricCollector` |
| Python 상수 | UPPER_SNAKE | `MAX_RETRY_COUNT` |
| FastAPI 라우터 | kebab-case | `/api/v1/db-instances` |
| SQLAlchemy 테이블 | snake_case 복수형 | `metric_samples` |
| React 컴포넌트 | PascalCase.tsx | `TopologyMap.tsx` |
| React 훅 | use + camelCase.ts | `useMetrics.ts` |
| Zustand 스토어 | camelCase + Store | `incidentStore.ts` |
| Spec ID | `FS-{MODULE}-{NNN}` | `FS-DASH-001` |
| 요구사항 ID | `FR-{CATEGORY}-{NNN}` | `FR-AI-002` |

---

## 9. Git Workflow

- **브랜치**: `main`에서 분기 → 토픽 브랜치 → PR → main 머지
- **브랜치 네이밍**: `feature/FS-{ID}-{desc}`, `fix/BUG-{ID}-{desc}`, `spec/FS-{ID}-{desc}`
- **커밋 형식**: `{type}({scope}): {subject}` + `Spec: {FS-ID}`
- **PR**: upstream에 직접 push 금지. 항상 fork 또는 토픽 브랜치 경유
- 상세: @CONTRIBUTING.md

---

## 10. Skills — 2-Layer Architecture

> **Layer 1 (프로젝트)**: NeuralDB Spec-Driven 코드 생성 → `.claude/skills/`
> **Layer 2 (글로벌)**: gstack 워크플로우 (리뷰/QA/Ship) → `~/.claude/skills/gstack/`

### Layer 1: NeuralDB Project Skills (19종)

원본: `@skills/` → Claude Code 읽기 위치: `@.claude/skills/`

| Category | Skill | Trigger |
|----------|-------|---------|
| 초기화 | `init-project` | `/init-project [module]` |
| 검증 | `review-arch` | `/review-arch [path]` |
| FastAPI | `gen-fastapi-route` | `/gen-fastapi-route [name] [method]` |
| | `gen-pydantic-model` | `/gen-pydantic-model [name]` |
| DB | `gen-sqlalchemy-model` | `/gen-sqlalchemy-model [name]` |
| | `gen-alembic-migration` | `/gen-alembic-migration [desc]` |
| | `db-adapter` | `/db-adapter [db-type] [feature] [mode]` |
| React | `gen-component` | `/gen-component [name] [screen]` |
| | `gen-react-hook` | `/gen-react-hook [name] [type]` |
| | `gen-echarts` | `/gen-echarts [chart-type]` |
| AI/Agent | `gen-agent` | `/gen-agent [name] [level]` |
| | `gen-rag-pipeline` | `/gen-rag-pipeline [kb] [source]` |
| | `gen-mcp-tool` | `/gen-mcp-tool [name] [type]` |
| Infra | `gen-celery-task` | `/gen-celery-task [name] [schedule]` |
| | `gen-websocket` | `/gen-websocket [ns] [events]` |
| | `gen-docker` | `/gen-docker [target]` |
| 공통 | `gen-playbook` | `/gen-playbook [name] [db-type]` |
| | `gen-test` | `/gen-test [path] [type]` |
| 디자인 | `stitch-sync` | `/stitch-sync [all]` |

### Layer 2: gstack Workflow Skills (선별 사용)

설치: `~/.claude/skills/gstack/` (글로벌)

| 단계 | Skill | 용도 | 사용 시점 |
|------|-------|------|----------|
| **Think** | `/office-hours` | 요구사항 검증, 6가지 강제 질문 | Spec 작성 전 아이디어 검증 |
| **Plan** | `/plan-eng-review` | 아키텍처/데이터플로우/테스트 매트릭스 잠금 | Spec 완성 후 구현 착수 전 |
| **Plan** | `/plan-design-review` | 디자인 차원별 0-10 평가 | UI 컴포넌트 구현 전 |
| **Review** | `/review` | CI 통과하지만 프로덕션에서 깨지는 버그 탐지 | PR 생성 전 |
| **Review** | `/cso` | OWASP Top 10 + STRIDE 보안 감사 | 인증/인가/DB 접속 코드 변경 시 |
| **Test** | `/qa` | 실제 Chromium 브라우저 테스트 + 회귀 테스트 자동 생성 | 프론트엔드 기능 완성 후 |
| **Ship** | `/ship` | 테스트 → 커버리지 → PR 원커맨드 | 기능 완성 + 리뷰 통과 후 |
| **Reflect** | `/retro` | 주간 회고 + 커밋/LOC 메트릭 | 매주 금요일 |
| **Safety** | `/guard` | 위험 명령어 경고 + 수정 범위 제한 | DB 마이그레이션, 인프라 변경 시 |
| **Debug** | `/investigate` | 가설 기반 체계적 디버깅 | 원인 불명 버그 |

---

## 11. Spec-Driven Sprint — 7-Phase Loop

> gstack의 Think→Plan→Build→Review→Test→Ship→Reflect과
> NeuralDB의 Spec-Driven 방법론을 결합한 하이브리드 워크플로우.

```
 ┌──────────────────────────────────────────────────────────────┐
 │                    Spec-Driven Sprint                        │
 │                                                              │
 │  Think ──→ Plan ──→ Build ──→ Review ──→ Test ──→ Ship      │
 │    ↑                                                  ↓      │
 │    └──────────────── Reflect ←────────────────────────┘      │
 └──────────────────────────────────────────────────────────────┘
```

### Phase 1: Think — 요구사항 검증

```
/office-hours          → 6가지 강제 질문으로 요구사항 검증
docs/specs/ 읽기        → 관련 Spec 존재 여부 확인
Spec 작성/갱신          → 없으면 새로 작성, 있으면 갱신
```

### Phase 2: Plan — 아키텍처 잠금

```
/plan-eng-review       → 아키텍처, 데이터플로우, 엣지케이스, 테스트 계획 잠금
/plan-design-review    → UI 변경 시 디자인 차원별 평가 (선택)
출력: 테스트 매트릭스, 실패 모드 분석, ASCII 다이어그램
```

### Phase 3: Build — Spec 기반 코드 생성

```
NeuralDB Skills 활용:
  /gen-sqlalchemy-model  → ERD.md 기반 ORM 모델
  /gen-fastapi-route     → API_SPEC.md 기반 엔드포인트
  /gen-component         → COMPONENT_SPEC.md 기반 React 컴포넌트
  /gen-test              → TEST_STRATEGY.md 기반 테스트 자동 생성

규칙:
  - 코드에 Spec 참조 주석 명시 (# Spec: FR-AI-002)
  - Spec에 없는 기능 구현 금지
  - TECH_STACK.md 기술만 사용
```

### Phase 4: Review — 다관점 검증

```
/review-arch           → Spec 준수 여부 검증 (NeuralDB)
/review                → 프로덕션 버그 탐지 (gstack)
/cso                   → 보안 감사 (인증/DB 접속 변경 시)
Section 5 체크          → Good vs Bad 패턴 확인
```

### Phase 5: Test — 실행 검증

```
uv run pytest          → 백엔드 단위/통합 테스트
npm run test           → 프론트엔드 단위 테스트
/qa                    → 실제 브라우저 테스트 (대시보드, ASH 히트맵)
/gen-test              → 누락된 엣지케이스 테스트 추가 생성
```

### Phase 6: Ship — 릴리스

```
/ship                  → 테스트 → 커버리지 확인 → PR 생성 → main 머지
커밋 형식: {type}({scope}): {subject} + Spec: {FS-ID}
```

### Phase 7: Reflect — 회고

```
/retro                 → 주간 커밋/LOC 메트릭, 개선점 식별
피드백 → Phase 1 복귀   → 다음 Sprint Loop 시작
```

### "Boil the Lake" 원칙 (gstack)

> AI 시대에는 100% 완성도의 비용이 10~100배 낮다.
> 엣지케이스, 테스트 커버리지, 에러 핸들링을 "나중에"로 미루지 말 것.
>
> - **Lake** (끓일 수 있음): 단일 모듈, 기능 완성, 엣지케이스 → 완벽히 마무리
> - **Ocean** (끓일 수 없음): 시스템 전면 재작성, 멀티쿼터 마이그레이션 → 쪼개서 Lake로 분해

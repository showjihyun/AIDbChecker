# AGENTS.md — NeuralDB Project Intelligence

> 이 문서는 **프로젝트 고유의 맥락, 함정, 판단 기준**을 기록합니다.
> AI 에이전트(Claude Code, OpenAI Codex, Cursor, Windsurf 등)가 이 프로젝트에서 작업할 때 반드시 참고해야 할 내용입니다.
>
> **`@` 접두사**: 프로젝트 루트 기준 상대 경로. 에이전트는 해당 파일을 읽어 컨텍스트를 확보합니다.

---

## 1. 프로젝트 특이성

### @1.1 단일 PostgreSQL 16으로 3가지 역할 수행

이 프로젝트는 PostgreSQL 16 하나로 **메타 DB + 시계열 메트릭 + 벡터 검색**을 모두 처리합니다.
별도의 TimescaleDB, QuestDB, Pinecone, Weaviate 등을 사용하지 않습니다.

| 역할 | 구현 방식 | 참조 |
|------|----------|------|
| 메타 DB | 일반 테이블 (표준 CRUD) | @docs/specs/data-model/ERD.md |
| 시계열 메트릭 | 네이티브 파티셔닝 + pg_partman | @docs/specs/data-model/MIGRATION_SPEC.md |
| 벡터 검색 | pgvector 확장 | @docs/specs/ai/LIGHTWEIGHT_RAG_SPEC.md |

**함정**:
- `PARTITION BY RANGE (sampled_at)` 필수. TimescaleDB 함수(`time_bucket` 등) 사용 금지
- Materialized View + pg_cron으로 다운샘플링. Continuous Aggregate 문법 금지
- 근거: @docs/ADR/002-postgresql16-unified.md

### @1.2 Backend 단일 레이어 (Python Only)

Architecture Spec v3.0의 NestJS + Python 2층 구조는 **v3.2에서 Python/FastAPI 단일 레이어로 통합**.

- `architecture-spec-v3.md`의 "NestJS", "Apollo GraphQL", "TypeORM" 언급은 **폐기됨**
- GraphQL은 **Strawberry** (Python Code-First)로 대체
- ORM은 **SQLAlchemy 2.0 async** 단일 사용
- 근거: @docs/ADR/001-fastapi-over-nestjs.md
- 기술 스택 최종 진실: @docs/TECH_STACK.md

### @1.3 Valkey ≠ Redis (미세한 차이)

Valkey는 Redis API 99.9% 호환이지만 주의 필요:

| 항목 | 값 |
|------|-----|
| 패키지 | `redis` (Python 클라이언트) → Valkey 서버에 연결 |
| 환경변수 | `VALKEY_URL`, 연결 문자열은 `redis://valkey:6379/0` |
| Docker 이미지 | `valkey/valkey:8-alpine` |
| Celery 브로커 | `redis://` 프로토콜 (Valkey 수용) |
| **금지** | Redis 전용 모듈(RedisJSON, RediSearch, RedisGraph) |

근거: @docs/ADR/003-valkey-over-redis.md

### @1.4 라이선스 지뢰밭

독립 솔루션/SaaS 전환 목표 → 허용적 라이선스만 사용.

| 유혹 | 문제 | 대체 |
|------|------|------|
| Grafana 임베딩 | AGPL v3 | 자체 React + ECharts 대시보드 |
| RedisJSON | RSALv2 | 일반 `SET/GET` + JSON 직렬화 |
| TimescaleDB `time_bucket()` | TSL | PostgreSQL `date_trunc()` + Materialized View |
| Elastic APM / Kibana | SSPL | OpenTelemetry + Prometheus |
| MongoDB | SSPL | PostgreSQL JSONB |

참조: @ai-db-monitor-license-audit.jsx

### @1.5 2-Tier Hybrid Adapter (수집 전략)

| Tier | 이름 | 배포 위치 | 해상도 | Phase |
|------|------|----------|--------|-------|
| **Tier 2** | Remote Adapter | NeuralDB 백엔드 | RTT 의존 (1~10초) | Phase 1~2 |
| **Tier 1** | Lightweight Collector | 대상 DB 서버 | 항상 1초 | Phase 3+ |

- `BaseAdapter` 인터페이스는 Phase 3의 `PostgreSQLLocalCollector`도 지원 가능하도록 설계
- Collector 미설치 시 Remote Adapter로 자동 폴백 → 해상도만 다운그레이드
- 근거: @docs/ADR/006-hybrid-adapter-collection.md
- 상세 검토: @docs/review/001-adapter-vs-agent-collection.md

**함정**: Phase 1에서 Adapter를 대충 만들지 말 것. `collect_metrics()` / `collect_ash()` 반환 타입이 Phase 3에서도 그대로 사용됨.

### @1.6 1초 수집의 현실적 제약

- `pg_stat_activity` 조회는 **읽기 전용 커넥션 풀** 사용
- ASH 샘플링 쿼리에 `statement_timeout = '500ms'` 설정
- 수집 실패 시 silent skip (대상 DB 장애를 악화시키지 않음)
- Hot 메트릭만 1초, Warm은 10초, Cold는 1분 — 모든 메트릭을 1초로 수집하지 않음
- 참조: @docs/MVP.md (Section 2.2)

### @1.7 Adaptive Autonomy Level과 코드 분기

모든 자동화 코드에는 autonomy level 체크가 필요:

```python
# 모든 remediation action 전에 반드시
if action.risk_level > current_autonomy_level.max_allowed_risk:
    await escalate_to_human(action)
    return

# Level 0: 알림만 / Level 1: 추천 / Level 2: 승인 후 실행
# Level 3: 실행 후 보고 / Level 4: 완전 자율
```

참조: @docs/specs/agents/AGENT_SPEC.md

---

## 2. 문서 우선순위 (충돌 시)

```
1. @docs/TECH_STACK.md                      ← 기술 스택 최종 진실 (v3.2 반영)
2. @AI_DB_Monitoring_System_PRD_v3.3.md     ← 요구사항 + 방법론
3. @docs/MVP.md                             ← Phase 1 범위 + 기능 상세
4. @docs/FRONTEND_DESIGN.md                 ← UI/UX 디자인 토큰
5. @ai-db-monitor-architecture-spec-v3.md   ← 아키텍처 (일부 구 스택 잔존 주의)
6. @ai-db-monitor-license-audit.jsx         ← 라이선스 감사 (v3.1, 유효)
```

---

## 3. 코드 생성 시 흔한 실수

### @3.1 Python

| 실수 | 올바른 방식 | 참조 |
|------|------------|------|
| `pip install fastapi` | `uv add fastapi` | @docs/ADR/004-uv-over-pip.md |
| `from sqlalchemy import Column, Integer` | `from sqlalchemy.orm import Mapped, mapped_column` (2.0 스타일) | @docs/TECH_STACK.md |
| `session.query(Model).filter()` | `select(Model).where()` (2.0 스타일) | |
| `sync def endpoint()` | `async def endpoint()` (FastAPI async 필수) | |
| `import redis; r = redis.Redis()` | 연결 URL에 `VALKEY_URL` 환경변수 사용 | @docs/ADR/003-valkey-over-redis.md |
| `requirements.txt` 생성 | `pyproject.toml` + `uv.lock` 사용 | |
| `print()` 디버깅 | `structlog` 또는 `logging` + OpenTelemetry | |

### @3.2 Frontend (React)

| 실수 | 올바른 방식 | 참조 |
|------|------------|------|
| `next/link`, `next/image` | React SPA — `react-router` 또는 TanStack Router | @docs/ADR/005-react-spa-over-nextjs.md |
| `getServerSideProps` | TanStack Query로 클라이언트 데이터 페칭 | |
| `#000000` 배경색 | `#0b1326` (surface 토큰). 순수 검정 금지 | @docs/FRONTEND_DESIGN.md |
| `border: 1px solid #ccc` | 배경색 차이로 구분 (No-Line Rule) | @docs/FRONTEND_DESIGN.md |
| `import axios from 'axios'` | TanStack Query + 네이티브 fetch 또는 ky | |
| `useState` 남용 | 서버 상태는 TanStack Query, 글로벌은 Zustand | @docs/specs/frontend/REACT_HOOKS_SPEC.md |

### @3.3 Database

| 실수 | 올바른 방식 | 참조 |
|------|------------|------|
| `SERIAL` / `BIGSERIAL` PK | `UUID` + `gen_random_uuid()` | @docs/specs/data-model/ERD.md |
| `OFFSET` 페이지네이션 | 커서 기반 페이지네이션 | @docs/specs/api/API_SPEC.md |
| `SELECT *` | 필요한 컬럼만 명시 | |
| `CREATE INDEX idx ON big_table(col)` | `CREATE INDEX CONCURRENTLY` | |
| TimescaleDB `create_hypertable()` | `PARTITION BY RANGE` + pg_partman | @docs/ADR/002-postgresql16-unified.md |
| `TIMESTAMP` | `TIMESTAMPTZ` (timezone-aware 필수) | @docs/specs/data-model/ERD.md |

---

## 4. 환경별 차이

### @4.1 Online vs Offline AI

이 프로젝트는 **인터넷 차단 환경(에어갭)**에서도 동작해야 합니다.

```python
# config.py
class AIConfig:
    mode: Literal["online", "offline"] = "online"
    # Online: openai_model = "gpt-4o", claude_model = "claude-sonnet-4-20250514"
    # Offline: ollama_model = "mistral:7b", vllm_model = "mistral-7b-instruct"
```

- 모든 LLM 호출은 `AIConfig.mode`에 따라 분기
- 하드코딩된 `openai.ChatCompletion.create()` 호출 금지 → LangChain 추상화 사용
- 참조: @docs/specs/ai/COPILOT_SPEC.md

### @4.2 3종 메트릭 흐름 구분

| 구분 | 무엇을 | 어떻게 | 어디에 | Prometheus? |
|------|--------|--------|--------|-------------|
| **대상 DB 메트릭** | 고객 DB의 CPU, 세션, 쿼리 | 자체 Adapter (1초) | `metric_samples` 테이블 | **미사용** |
| **자체 시스템 메트릭** | NeuralDB 상태 | OpenTelemetry SDK | **Prometheus** | **사용** |
| **자체 시스템 트레이스** | API→Agent→DB 분산 추적 | OpenTelemetry SDK | OTel Collector | 해당 없음 |

**함정**: 대상 DB 메트릭을 Prometheus에 저장하려 하지 말 것.
- 1초 해상도 + ASH + Wait Event → Prometheus 15초 scrape로 불가능
- 대상 DB에 exporter 설치 불가 (고객 환경 변경 불가)

### @4.3 모니터링 대상 DB vs 시스템 자체 DB

| 구분 | 설명 | 커넥션 |
|------|------|--------|
| **대상 DB** | 고객의 PostgreSQL/MySQL/MSSQL | 읽기 전용 (`pg_monitor`) |
| **시스템 DB** | NeuralDB 자체 PostgreSQL 16 | 읽기+쓰기 |

- 대상 DB에 쓰기 작업 → **반드시 Playbook + Autonomy Level 체크**
- 두 DB의 커넥션 풀을 절대 혼용하지 않음

---

## 5. Skills 구성

### @5.1 프로젝트 커스텀 Skills (19종)

원본: `@skills/` → Claude Code 읽기 위치: `@.claude/skills/`

| Category | Skill | Trigger | 용도 |
|----------|-------|---------|------|
| **초기화** | `init-project` | `/init-project [module]` | 프로젝트 구조 스캐폴딩 |
| **검증** | `review-arch` | `/review-arch [path]` | Spec 준수 여부 검증 |
| **디자인** | `stitch-sync` | `/stitch-sync [all]` | Google Stitch 디자인 동기화 |
| **FastAPI** | `gen-fastapi-route` | `/gen-fastapi-route [name] [method]` | API 라우트 + 서비스 + 스키마 |
| | `gen-pydantic-model` | `/gen-pydantic-model [name]` | Pydantic v2 Request/Response |
| **DB** | `gen-sqlalchemy-model` | `/gen-sqlalchemy-model [name]` | SQLAlchemy 2.0 ORM 모델 |
| | `gen-alembic-migration` | `/gen-alembic-migration [desc]` | Alembic 마이그레이션 |
| | `db-adapter` | `/db-adapter [db-type] [feature] [mode]` | DB 어댑터 플러그인 |
| **React** | `gen-component` | `/gen-component [name] [screen]` | React 컴포넌트 |
| | `gen-react-hook` | `/gen-react-hook [name] [type]` | TanStack Query / WebSocket / Zustand 훅 |
| | `gen-echarts` | `/gen-echarts [chart-type]` | ECharts 차트 |
| **AI/Agent** | `gen-agent` | `/gen-agent [name] [level]` | LangGraph/CrewAI 에이전트 |
| | `gen-rag-pipeline` | `/gen-rag-pipeline [kb] [source]` | RAG 파이프라인 (pgvector) |
| | `gen-mcp-tool` | `/gen-mcp-tool [name] [type]` | MCP Server 도구 |
| **Infra** | `gen-celery-task` | `/gen-celery-task [name] [schedule]` | Celery 비동기 태스크 |
| | `gen-websocket` | `/gen-websocket [ns] [events]` | python-socketio 이벤트 핸들러 |
| | `gen-docker` | `/gen-docker [target]` | Docker/Compose 설정 |
| **공통** | `gen-playbook` | `/gen-playbook [name] [db-type]` | Playbook-as-Code YAML |
| | `gen-test` | `/gen-test [path] [type]` | 4-Layer 테스트 |

### @5.2 Skills 파일 위치 규칙

```
skills/                    ← 원본 (프로젝트 커스텀, Git 추적)
.claude/skills/            ← Claude Code가 읽는 위치
```

---

## 6. 네이밍 컨벤션

| 대상 | 컨벤션 | 예시 |
|------|--------|------|
| Python 파일/모듈 | snake_case | `metric_collector.py` |
| Python 클래스 | PascalCase | `MetricCollector` |
| Python 상수 | UPPER_SNAKE | `MAX_RETRY_COUNT` |
| FastAPI 라우터 | kebab-case | `/api/v1/db-instances` |
| SQLAlchemy 테이블 | snake_case 복수형 | `metric_samples` |
| React 컴포넌트 | PascalCase | `TopologyMap.tsx` |
| React 훅 | camelCase + use | `useMetrics.ts` |
| Zustand 스토어 | camelCase + Store | `incidentStore.ts` |
| Spec 문서 ID | `FS-{MODULE}-{NNN}` | `FS-DASH-001` |
| 요구사항 ID | `FR-{CATEGORY}-{NNN}` | `FR-AI-002` |

---

## 7. Spec-Driven Loop 워크플로우

```
Phase 1: 기획 (Spec)
  ├── 관련 Spec 읽기 (이 문서의 Reference Map 참조)
  ├── 필요 시 Spec 작성/갱신 → docs/specs/ 에 배치
  └── Spec 리뷰 (기술 스택, 라이선스, 네이밍 검증)

Phase 2: 구현 (Code)
  ├── Spec 기반 코드 생성 (Skills 활용)
  ├── 코드에 Spec 참조 주석 명시 (# Spec: FR-AI-002)
  └── 단위 테스트 작성

Phase 3: 리뷰 (Review)
  ├── /review-arch 실행 → Spec 준수 여부 자동 검증
  ├── 흔한 실수 체크 (Section 3 참조)
  └── 피드백 → Phase 1로 복귀 (Loop)
```

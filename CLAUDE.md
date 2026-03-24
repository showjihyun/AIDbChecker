# NeuralDB — AI-Powered Intelligent DB Monitoring System

## 방법론: Spec-Driven Harness Engineering

```
┌─────────────────────────────────────────────────────────┐
│              Spec-Driven Loop (반복 순환)                 │
│                                                         │
│   기획 (Spec) ──→ 구현 (Code) ──→ 리뷰 (Review)         │
│       ↑                                ↓                │
│       └────────── 피드백 ──────────────┘                │
│                                                         │
│   매 Loop마다:                                          │
│   1. Spec 읽기/작성 → 2. Spec 기반 코드 생성            │
│   3. /review-arch 검증 → 4. 피드백 반영 → 1로 복귀      │
└─────────────────────────────────────────────────────────┘
```

## Spec-Driven Rules

1. **코드 생성 전 관련 Spec 문서를 반드시 읽는다**
2. **Spec에 없는 기능은 구현하지 않는다**
3. **Spec에 명시된 기술 스택만 사용한다** → `@docs/TECH_STACK.md`
4. **생성된 코드에 Spec 참조를 명시한다** (e.g., `# Spec: FR-AI-002`)
5. **라이선스 정책 준수**: Apache 2.0 / MIT / BSD만 허용, GPL/AGPL/SSPL 금지
6. **Spec 없이 구현된 코드는 리뷰에서 거부된다**

## Python Package Manager: uv (MUST)

> pip 사용 금지. 모든 Python 패키지 관리는 반드시 `uv`를 사용한다.

| 금지 | 대체 |
|------|------|
| `pip install` | `uv add` |
| `pip freeze` | `uv lock` |
| `requirements.txt` | `pyproject.toml` + `uv.lock` |
| `python -m venv` | `uv venv` 또는 자동 생성 |

## Tech Stack Summary

- **Frontend**: React 18 + Vite + TypeScript + TailwindCSS
- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Celery
- **Database**: PostgreSQL 16 (Meta + Metrics + Vector)
- **Cache**: Valkey (BSD 3-Clause, Redis API 호환)
- **Messaging**: Apache Kafka
- **AI/ML**: LangChain / scikit-learn / statsmodels / OpenAI / Ollama

---

## 📚 Document Reference Map

### Core Documents (프로젝트 루트)

| 문서 | 경로 | 역할 |
|------|------|------|
| PRD | `@AI_DB_Monitoring_System_PRD_v3.3.md` | 요구사항 + 방법론 정의 |
| Architecture | `@ai-db-monitor-architecture-spec-v3.md` | 아키텍처 설계 (일부 구 스택 잔존 주의) |
| License Audit | `@ai-db-monitor-license-audit.jsx` | 라이선스 감사 (v3.1, 유효) |
| Competitive Analysis | `@AI_DB_Monitor_Competitive_Analysis.md` | 경쟁사 분석 |
| Contributing | `@CONTRIBUTING.md` | 개발 규칙, 브랜치/커밋 컨벤션 |
| Agents | `@AGENTS.md` | 프로젝트 특이성, 함정, 판단 기준 |

### docs/ — 설계 문서

| 문서 | 경로 | 역할 |
|------|------|------|
| Tech Stack | `@docs/TECH_STACK.md` | 기술 스택 최종 진실 (v3.2 반영) |
| MVP | `@docs/MVP.md` | Phase 1 범위, 기능, 마일스톤 |
| Frontend Design | `@docs/FRONTEND_DESIGN.md` | UI/UX 디자인 토큰, 스크린 설계 |
| UI/UX Plan | `@docs/UI_UX_PLAN.md` | UI/UX 전략 |
| MVP UI Reference | `@docs/MVP_UI_REFERENCE.md` | MVP UI 참고 화면 |
| Use Cases | `@docs/USECASES.md` | 액터별 유즈케이스 |
| Glossary | `@docs/GLOSSARY.md` | 도메인 용어 ↔ 코드 매핑 |

### docs/ADR/ — Architecture Decision Records

| ADR | 경로 | 결정 사항 |
|-----|------|----------|
| ADR-001 | `@docs/ADR/001-fastapi-over-nestjs.md` | FastAPI 선택 근거 |
| ADR-002 | `@docs/ADR/002-postgresql16-unified.md` | PostgreSQL 16 통합 근거 |
| ADR-003 | `@docs/ADR/003-valkey-over-redis.md` | Valkey 선택 근거 |
| ADR-004 | `@docs/ADR/004-uv-over-pip.md` | uv 도입 근거 |
| ADR-005 | `@docs/ADR/005-react-spa-over-nextjs.md` | React SPA 선택 근거 |
| ADR-006 | `@docs/ADR/006-hybrid-adapter-collection.md` | 2-Tier 수집 전략 근거 |
| ADR-007 | `@docs/ADR/007-credential-encryption.md` | 자격증명 암호화 근거 |

### docs/specs/ — Feature Specifications

| 카테고리 | 경로 | Spec 목록 |
|----------|------|----------|
| **Agents** | `@docs/specs/agents/` | AGENT_SPEC.md |
| **AI** | `@docs/specs/ai/` | CONFIDENCE_SCORE_SPEC.md, COPILOT_SPEC.md, DIAGNOSIS_FLOW_USECASE.md, LIGHTWEIGHT_RAG_SPEC.md, LLM_OBSERVABILITY_SPEC.md, MTL_RCA_SPEC.md |
| **API** | `@docs/specs/api/` | API_SPEC.md, ERROR_CODES_SPEC.md, GRAPHQL_SCHEMA.md |
| **Config** | `@docs/specs/config/` | SETTINGS_SPEC.md |
| **Data Model** | `@docs/specs/data-model/` | ERD.md, MIGRATION_SPEC.md |
| **Frontend** | `@docs/specs/frontend/` | COMPONENT_SPEC.md, REACT_HOOKS_SPEC.md, WEBSOCKET_EVENTS_SPEC.md |
| **Playbooks** | `@docs/specs/playbooks/` | PLAYBOOK_SPEC.md |
| **Protocols** | `@docs/specs/protocols/` | A2A_PROTOCOL.md, KAFKA_SPEC.md, MCP_INTEGRATION.md |
| **Services** | `@docs/specs/services/` | SERVICE_LAYER_SPEC.md |
| **Tasks** | `@docs/specs/tasks/` | CELERY_TASKS_SPEC.md |
| **Tests** | `@docs/specs/tests/` | BACKEND_TEST_SPEC.md, FRONTEND_TEST_SPEC.md, TEST_SPEC.md, TEST_STRATEGY.md |

### docs/review/ — Technical Reviews

| 리뷰 | 경로 | 주제 |
|------|------|------|
| Review-001 | `@docs/review/001-adapter-vs-agent-collection.md` | Adapter vs Agent 수집 방식 검증 |

### docs/screenshots/ — UI 참고 화면

| 화면 | 경로 |
|------|------|
| Topology | `@docs/screenshots/screen1_topology.png` |
| Self-Healing | `@docs/screenshots/screen2_selfhealing.png` |
| ASH | `@docs/screenshots/screen3_ash.png` |
| Diagnosis | `@docs/screenshots/screen4_diagnosis.png` |
| Topology Explorer | `@docs/screenshots/screen5_topology_explorer.png` |
| Add Database | `@docs/screenshots/screen6_add_database.png` |

### HTML Prototypes — 화면 프로토타입

| 화면 | 경로 |
|------|------|
| Topology | `@docs/screen1_topology.html` |
| Self-Healing | `@docs/screen2_selfhealing.html` |
| ASH | `@docs/screen3_ash.html` |
| Diagnosis | `@docs/screen4_diagnosis.html` |
| Topology Explorer | `@docs/screen5_topology_explorer.html` |
| Add Database | `@docs/screen6_add_database.html` |
| Diagnosis Flow | `@docs/specs/ai/DIAGNOSIS_FLOW_USECASE.md` |

---

## 문서 우선순위 (충돌 시)

```
1. docs/TECH_STACK.md          ← 기술 스택 최종 진실
2. AI_DB_Monitoring_System_PRD_v3.3.md  ← 요구사항 + 방법론
3. docs/MVP.md                 ← Phase 1 범위
4. docs/FRONTEND_DESIGN.md     ← UI/UX 디자인 토큰
5. ai-db-monitor-architecture-spec-v3.md  ← 아키텍처 (구 스택 잔존 주의)
```

## Frontend Commands

```bash
cd frontend
npm install        # Node.js 의존성
npm run dev        # Vite dev server
npm run build      # Production build
npm run test       # Vitest
npm run lint       # ESLint
```

## Backend Commands

```bash
cd backend
uv sync                              # 의존성 설치
uv run alembic upgrade head          # DB 마이그레이션
uv run uvicorn app.main:app --reload # 개발 서버
uv run pytest                        # 테스트
uv run ruff check .                  # 린트
```

# Contributing to NeuralDB

---

## 1. 개발 방법론

본 프로젝트는 **Spec-Driven Harness Engineering**을 따릅니다.
코드를 작성하기 전에 반드시 관련 Spec 문서가 존재해야 합니다.

```
Spec 작성 → Spec 리뷰 → Spec 승인 → 코드 구현 → 검증 → 머지
```

**Spec 없이 구현된 코드는 리뷰에서 거부됩니다.**

---

## 2. Branch Strategy

```
main                    ← 릴리스 가능 상태
├── develop             ← 통합 브랜치
│   ├── feature/FS-DASH-001-dashboard-metrics
│   ├── feature/FS-AI-002-rag-pipeline
│   ├── fix/BUG-042-ash-sampling-timeout
│   └── spec/FS-AUTO-003-playbook-schema
└── release/v1.0.0      ← 릴리스 브랜치
```

| Branch | 용도 | Base |
|--------|------|------|
| `feature/FS-{ID}-{description}` | 새 기능 구현 (Spec ID 필수) | develop |
| `fix/BUG-{ID}-{description}` | 버그 수정 | develop |
| `spec/FS-{ID}-{description}` | Spec 문서 작성/수정 | develop |
| `hotfix/{description}` | 긴급 수정 | main |

---

## 3. Commit Message Convention

```
{type}({scope}): {subject}

{body}

Spec: {FS-ID or FR-ID}
```

### Types
| Type | 용도 |
|------|------|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `spec` | Spec 문서 추가/수정 |
| `refactor` | 리팩토링 (기능 변경 없음) |
| `test` | 테스트 추가/수정 |
| `docs` | 문서 (Spec 외) |
| `chore` | 빌드, 설정, 의존성 |
| `style` | 코드 포맷팅 |

### Scopes
`frontend` / `backend` / `agent` / `adapter` / `infra` / `spec`

### Examples
```
feat(backend): add ASH sampling collector for PostgreSQL

Implement 1-second pg_stat_activity sampling with connection pooling.
Includes statement_timeout safety and silent failure handling.

Spec: FS-ASH-001
```

```
spec(data-model): define metric_samples partitioning strategy

Add pg_partman daily partitioning with 7/90/365 day retention tiers.

Spec: DM-001
```

---

## 4. Pull Request Process

### PR Title
```
[{type}] {FS-ID}: {short description}
```
예: `[feat] FS-DASH-001: Implement real-time metrics dashboard`

### PR Body Template
```markdown
## Spec Reference
- Spec ID: FS-{MODULE}-{NUMBER}
- PRD Reference: FR-{CATEGORY}-{NUMBER}

## Changes
- [변경 내용 요약]

## Acceptance Criteria Checklist
- [ ] AC-1: ...
- [ ] AC-2: ...

## Test Plan
- [ ] Unit tests pass
- [ ] /review-arch pass
- [ ] Manual verification

## Screenshots (UI changes)
[해당 시 첨부]
```

### Review Checklist
- [ ] Spec에 정의된 인터페이스와 일치하는가?
- [ ] Spec에 없는 기능이 추가되지 않았는가?
- [ ] `docs/TECH_STACK.md`에 있는 기술만 사용했는가?
- [ ] 라이선스 정책 준수 (MIT/Apache 2.0/BSD)?
- [ ] `# Spec: FR-xxx` 참조 주석이 있는가?
- [ ] Python: uv 사용, SQLAlchemy 2.0 스타일, async?
- [ ] React: Next.js 패턴 없음, 디자인 토큰 사용?
- [ ] DB: UUID PK, TIMESTAMPTZ, 커서 페이지네이션?

---

## 5. Development Setup

### Prerequisites
- Python 3.12+
- Node.js 22 LTS
- PostgreSQL 16
- uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Backend
```bash
cd backend
uv sync                              # 의존성 설치
cp ../.env.example ../.env           # 환경변수 설정
uv run alembic upgrade head          # DB 마이그레이션
uv run uvicorn app.main:app --reload # 개발 서버
```

### Frontend
```bash
cd frontend
npm install                          # 의존성 설치
npm run dev                          # Vite dev server (localhost:3000)
```

### Infrastructure (Docker)
```bash
cd infra/docker
docker compose up -d postgres valkey kafka   # 인프라만 기동
```

---

## 6. Code Quality

### Python
```bash
uv run ruff check .                  # 린트
uv run ruff format .                 # 포맷
uv run mypy app/                     # 타입 체크
uv run pytest                        # 테스트
```

### Frontend
```bash
npm run lint                         # ESLint
npm run format                       # Prettier
npm run test                         # Vitest
npm run test:e2e                     # Playwright
```

---

## 7. File Naming

| 대상 | 규칙 | 예시 |
|------|------|------|
| Python 모듈 | `snake_case.py` | `metric_collector.py` |
| React 컴포넌트 | `PascalCase.tsx` | `TopologyMap.tsx` |
| React 훅 | `camelCase.ts` (use 접두사) | `useMetrics.ts` |
| Spec 문서 | `UPPER_SNAKE.md` | `API_SPEC.md`, `ERD.md` |
| ADR 문서 | `NNN-kebab-case.md` | `001-fastapi-over-nestjs.md` |
| Playbook | `kebab-case.yaml` | `lock-remediation.yaml` |
| Migration | `{hash}_{description}.py` (Alembic auto) | |

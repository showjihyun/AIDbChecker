# Feature Spec: Harness Engineering v3 — 4-Pillar AI Quality Gate

## 메타데이터
- **Spec ID**: FS-HARNESS-001
- **PRD 참조**: TEST-STRATEGY-001 (Spec-Driven Test 확장)
- **우선순위**: P0 (인프라)
- **상태**: Approved
- **구현 파일**:
  - Hook: `.claude/settings.json` (PreCommit hook)
  - Scripts: `backend/scripts/precommit_check.sh`
  - Config: `.pre-commit-config.yaml`

---

## 0. AI 모델 할당 전략

### 원칙: "Think는 Opus, Build는 Sonnet"

AI 에이전트(Claude Code)의 작업 유형에 따라 최적 모델을 선택합니다.

| 작업 유형 | 모델 | 근거 |
|----------|------|------|
| **Plan-Mode** (설계, 아키텍처, SPEC 작성, 의사결정) | **Opus 4.6** | 깊은 추론, 복잡한 트레이드오프 분석, 장기적 아키텍처 판단 |
| **Code 작성** (구현, 리팩토링, 버그 수정) | **Sonnet 4.6** | 빠른 코드 생성, 비용 효율, 일관된 패턴 적용 |
| **Test 작성** (단위/통합/E2E 테스트) | **Sonnet 4.6** | 반복적 패턴, 대량 생성, 속도 우선 |
| **Review** (보안 감사, 코드 리뷰) | **Opus 4.6** | 취약점 추론, 전체 맥락 파악, 높은 정확도 필수 |
| **Debug** (원인 분석, 에러 추적) | **Opus 4.6** | 복잡한 인과 관계 추론 |
| **문서 작성** (SPEC, README, CHANGELOG) | **Sonnet 4.6** | 구조화된 텍스트 생성, 속도 우선 |

### gstack Skill별 모델 매핑

| Skill | 모델 | 이유 |
|-------|------|------|
| `/plan-eng-review`, `/plan-ceo-review` | Opus | 아키텍처 판단 |
| `/review`, `/cso` | Opus | 보안 + 품질 추론 |
| `/investigate` | Opus | 근본 원인 추론 |
| `/ship` | Sonnet | 자동화 워크플로우 실행 |
| `/qa` | Sonnet | 테스트 실행 + 버그 수정 |
| `/retro` | Sonnet | 메트릭 집계 + 텍스트 생성 |
| `/office-hours` | Opus | 요구사항 발굴 + 아이디어 검증 |

### 적용 방법

Claude Code에서 모델 전환:
```bash
# Plan-Mode (Opus)
/model opus

# Code/Test 작성 (Sonnet)
/model sonnet
```

또는 Agent 도구 사용 시 `model` 파라미터로 지정:
```
Agent(subagent_type="Plan", model="opus")
Agent(subagent_type="python-expert", model="sonnet")
```

> **비용 최적화**: Opus는 Sonnet 대비 ~5x 비용. Plan/Review처럼 정확도가 핵심인 작업에만 Opus를 사용하고, 반복적 코드 생성은 Sonnet으로 처리.

---

## 1. 개요

AI 에이전트(Claude Code)가 코드를 생성할 때, **커밋 전에 자동으로 품질 검증**이 실행되고, 실패 시 **Claude가 스스로 수정하여 다시 커밋**하는 자율 피드백 루프.

```
┌─────────────────────────────────────────────────────────────┐
│               Harness v3: 4-Pillar Quality Gate              │
│                                                              │
│   Claude writes code                                         │
│       ↓                                                      │
│   git commit                                                 │
│       ↓                                                      │
│   ┌──────────────────────────────────────┐                   │
│   │ Pillar 1: CONSTRAINT (Lint)          │ ← ruff check      │
│   │ Pillar 2: CONTEXT (Type Check)       │ ← mypy / tsc      │
│   │ Pillar 3: VERIFICATION (Test)        │ ← pytest / vitest  │
│   │ Pillar 4: FEEDBACK (AC Dashboard)    │ ← spec_dashboard   │
│   └──────────┬───────────────────────────┘                   │
│              │                                                │
│         ┌────▼────┐                                          │
│         │ PASS?   │                                          │
│         └────┬────┘                                          │
│         Yes  │  No                                           │
│          ↓   │  ↓                                            │
│   ✅ Commit  │  ❌ Hook fails                                │
│   완료       │     ↓                                          │
│              │  Claude reads error                            │
│              │     ↓                                          │
│              │  Claude auto-fixes                             │
│              │     ↓                                          │
│              └── git commit (retry)                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 4-Pillar 정의

### Pillar 1: CONSTRAINT (제약)

**목적**: 코드 스타일과 안전 규칙을 강제하여 코드 품질의 하한선을 보장.

| 검증 | 도구 | 대상 | 통과 기준 | 자동 수정 |
|------|------|------|----------|----------|
| Python Lint | `ruff check --fix` | `backend/app/` | 에러 0 | ✅ `--fix` 자동 |
| Python Format | `ruff format --check` | `backend/app/` | 변경 0 | ✅ `ruff format` |
| Frontend Lint | `npm run lint` | `frontend/src/` | 에러 0 | ⚠️ 수동 |
| Import 정렬 | ruff (isort 규칙) | `backend/` | 에러 0 | ✅ 자동 |

**원칙**:
- `--fix`로 자동 수정 가능한 것은 즉시 수정하고 다시 스테이지
- 자동 수정 불가한 에러만 Claude에게 리포트

### Pillar 2: CONTEXT (맥락)

**목적**: 타입 시스템을 통해 코드의 의미적 정합성을 검증. "컴파일이 되는가?"

#### 환경별 검증 수준

| 환경 | Python mypy | TypeScript tsc | 검증 범위 |
|------|------------|---------------|----------|
| **dev/staging** (pre-commit) | staged 파일만, 경고 | staged 파일만, 경고 | **변경분만** |
| **production** (/ship) | 전체 프로젝트, 차단 | 전체 프로젝트, 차단 | **전체** |

> **설계 근거**: dev/staging에서 전체 프로젝트 검사는 다른 에이전트/개발자의 미완성 코드까지 차단하여 작업 흐름을 방해. 전체 검사는 `/ship` (production gate)에서 시행.

| 검증 | 도구 | dev/staging | production (/ship) |
|------|------|-----------|-------------------|
| Python Type | `mypy` | staged `*.py`, **warn only** | `mypy app/`, **block** |
| TypeScript | `tsc --noEmit` | staged `*.tsx/*.ts`, **warn only** | 전체, **block** |

**원칙**:
- **Pre-commit (dev/staging)**: staged 파일만 검사, 경고만 (차단 안 함). 빠른 피드백 우선.
- **/ship (production)**: 전체 프로젝트 검사, 에러 시 차단. 품질 보장.
- 다중 에이전트 환경에서 서로의 미완성 코드가 커밋을 차단하지 않도록 격리.

### Pillar 3: VERIFICATION (검증)

**목적**: 기능이 올바르게 동작하는지 실제 실행으로 확인.

| 검증 | 도구 | 대상 | 통과 기준 | 비고 |
|------|------|------|----------|------|
| Backend Unit | `uv run pytest {affected_tests} -x` | **변경 파일 관련 테스트만** | 0 failures | 전체 테스트는 `/ship` 시 실행 |
| Frontend Unit | `npx vitest run` | frontend 변경 시에만 | 0 failures | |

**Affected Tests 탐색 전략**:
```
staged: backend/app/services/nl2sql.py
  → 매칭: tests/unit/test_*nl2sql*.py
  → 실행: pytest tests/unit/test_ai_nl2sql_001_spec.py -x

staged: backend/tests/unit/test_foo.py
  → 직접 실행: pytest tests/unit/test_foo.py -x
```

**원칙**:
- **Pre-commit**: affected tests only (~2-5초, 커밋 흐름 유지)
- **/ship**: full test suite (전체 regression 확인)
- skip은 허용하되, fail은 불허
- `-x` 플래그로 첫 실패 즉시 중단

### Pillar 4: FEEDBACK (피드백)

**목적**: AC 커버리지 상태를 리포트하여 진행 상황을 투명하게 공유.

| 검증 | 도구 | 대상 | 통과 기준 | 비고 |
|------|------|------|----------|------|
| AC Dashboard | `spec_dashboard` | 전체 Spec | 정보 제공 (차단 없음) | AC pass/skip/fail 요약 |
| Spec Coverage | `gen_spec_tests` | 새 Spec | 정보 제공 | 누락 AC 알림 |

**원칙**:
- Feedback은 차단하지 않음 (정보 제공 목적)
- 커밋 메시지에 AC 요약을 자동 삽입하지 않음 (노이즈 방지)
- Claude가 결과를 읽고 다음 작업 우선순위를 조정

---

## 3. Pre-Commit Hook 동작

### 3.1 실행 순서

```bash
#!/bin/bash
# .git/hooks/pre-commit (또는 pre-commit framework)

set -e

echo "🔍 Pillar 1: CONSTRAINT (Lint)"
cd backend && uv run ruff check app/ --fix && uv run ruff format app/ --check
cd ..

echo "🔍 Pillar 2: CONTEXT (Type Check)"
cd backend && uv run mypy app/ --ignore-missing-imports --no-error-summary
cd ..

echo "🔍 Pillar 3: VERIFICATION (Test)"
cd backend && uv run pytest tests/unit/ -x --tb=short -q
cd ..

echo "📊 Pillar 4: FEEDBACK (AC Dashboard)"
cd backend && uv run python -m scripts.spec_dashboard 2>/dev/null | tail -5
cd ..

echo "✅ All pillars passed"
```

### 3.2 실패 시 Claude 자동 수정 루프

```
Pre-commit hook 실패
    ↓
Claude Code가 hook 출력을 자동으로 수신 (CLAUDE.md hook integration)
    ↓
Claude가 에러 메시지를 분석:
  - Pillar 1 실패 → ruff --fix 실행 후 재스테이지
  - Pillar 2 실패 → 타입 에러 수정
  - Pillar 3 실패 → 테스트 코드 또는 구현 수정
    ↓
git add + git commit (재시도)
    ↓
Hook 재실행 → 통과할 때까지 반복 (최대 3회)
```

### 3.3 Claude Code Hook 설정

```json
// .claude/settings.json — hooks 섹션
{
  "hooks": {
    "PreCommit": [
      {
        "type": "command",
        "command": "bash backend/scripts/precommit_check.sh"
      }
    ]
  }
}
```

---

## 4. 설정 파일

### 4.1 ruff 설정 (pyproject.toml)

```toml
[tool.ruff]
target-version = "py311"
line-length = 120
src = ["backend/app", "backend/tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]
ignore = ["E501"]  # line length handled by formatter
fixable = ["ALL"]

[tool.ruff.format]
quote-style = "double"
```

### 4.2 mypy 설정 (pyproject.toml)

```toml
[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true
warn_return_any = false
warn_unused_configs = true
exclude = ["migrations/", "tests/"]
```

---

## 5. 인수 기준 (Acceptance Criteria)

### Infrastructure

- [ ] **AC-1**: `git commit` 시 pre-commit hook이 자동 실행되어 4-Pillar 검증 수행
- [ ] **AC-2**: Pillar 1 (Lint) 실패 시 `ruff --fix` 자동 수정 후 재스테이지
- [ ] **AC-3**: Pillar 2 (Type) 실패 시 커밋 차단 + 에러 메시지 출력
- [ ] **AC-4**: Pillar 3 (Test) 실패 시 커밋 차단 + 실패 테스트명 출력
- [ ] **AC-5**: Pillar 4 (Feedback) AC 요약이 출력되되 커밋을 차단하지 않음
- [ ] **AC-6**: 전체 hook 실행 시간 < 60초 (backend unit tests 기준)

### Claude Auto-Fix Loop

- [ ] **AC-7**: Claude Code에서 커밋 실패 시 에러 메시지를 자동 수신
- [ ] **AC-8**: Claude가 lint/type/test 에러를 분석하여 수정 시도
- [ ] **AC-9**: 수정 후 재커밋 시 hook이 다시 실행됨 (최대 3회 재시도)

---

## 6. 의존성

- **선행 Spec**: TEST-STRATEGY-001 (테스트 전략)
- **도구**: ruff, mypy, pytest, vitest, spec_dashboard
- **연동**: `.claude/settings.json` hooks, `pyproject.toml` tool 설정

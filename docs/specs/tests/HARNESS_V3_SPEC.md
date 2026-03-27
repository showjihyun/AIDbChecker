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

| 검증 | 도구 | 대상 | 통과 기준 | 비고 |
|------|------|------|----------|------|
| Python Type | `mypy app/` | `backend/app/` | exit 0 (error 0) | `--ignore-missing-imports` |
| TypeScript | `npx tsc --noEmit` | `frontend/src/` | exit 0 | 전체 타입 체크 |

**원칙**:
- 타입 에러 = 런타임 버그의 전조. 0-tolerance
- 새 코드가 기존 타입 계약을 깨뜨리면 커밋 차단

### Pillar 3: VERIFICATION (검증)

**목적**: 기능이 올바르게 동작하는지 실제 실행으로 확인.

| 검증 | 도구 | 대상 | 통과 기준 | 비고 |
|------|------|------|----------|------|
| Backend Unit | `uv run pytest tests/unit/ -x` | 변경된 파일 관련 | 0 failures | `-x`: 첫 실패에 중단 |
| Frontend Unit | `npx vitest run` | 변경된 파일 관련 | 0 failures | |

**원칙**:
- 모든 테스트가 통과해야 커밋 허용
- skip은 허용하되, fail은 불허
- `-x` 플래그로 첫 실패 즉시 중단 (빠른 피드백)

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

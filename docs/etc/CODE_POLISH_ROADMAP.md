# 코드 깎기 로드맵 — Harness Engineering 보완

> **Date**: 2026-03-27
> **Baseline**: 500 passed, 200/230 ACs, Ruff 275 errors, Mypy 228 errors

## 현재 건강 점수

| 메트릭 | 현재 값 | 목표 | 상태 |
|--------|---------|------|------|
| BE 테스트 | 500 passed, 31 skipped | 500+ passed, <10 skipped | ⚠️ |
| AC 커버리지 | 200/230 (87%) | 220/230 (95%+) | ⚠️ |
| Ruff 린트 | 275 errors (119 auto-fixable) | 0 errors | ❌ |
| Mypy 타입 | 228 errors | 0 errors (strict) | ❌ |
| FE 테스트 | 5/20 컴포넌트 (25%) | 20/20 (100%) | ❌ |
| 소스:테스트 비율 | 102:49 = 2.1:1 | 1.5:1 이하 | ⚠️ |
| 통합 테스트 | 1개 (test_db_tables) | 10개+ API E2E | ❌ |
| Pre-commit | ruff 실패로 커밋 차단 | 자동 fix + 통과 | ❌ |
| README | 없음 | 완성 (온보딩 가이드) | ❌ |

## 7가지 돌 (우선순위 순)

### 1. Ruff Auto-fix (5분)
- `uv run ruff check app/ --fix` → 119개 자동 수정
- 나머지 156개 수동 수정 (E501 line length, B008 Depends 등)
- 목표: `ruff check app/` = 0 errors

### 2. Pre-commit 정상화
- `.pre-commit-config.yaml` 또는 `scripts/precommit_check.sh` 수정
- ruff auto-fix를 pre-commit에 통합
- 커밋 플로우 복구

### 3. FE 테스트 확대 (25% → 100%)
- 20개 컴포넌트 × 기본 테스트 (render + props + interaction)
- Vitest + React Testing Library
- `/gen-test` 스킬 활용

### 4. Skipped AC 해소 (31 → <10)
- 31개 skipped 테스트 분석
- 구현 가능한 것은 구현, Phase 4+ 인 것은 명시적 skip 사유

### 5. Mypy Strict (228 → 0)
- `mypy app/ --strict` 점진적 도입
- 단계: warn-only → per-module strict → 전체 strict

### 6. 통합 테스트 (1 → 10+)
- API E2E: httpx + 실제 SQLite/PostgreSQL
- 주요 워크플로우: 인스턴스 등록 → 메트릭 수집 → 인시던트 → RCA → Playbook

### 7. README + 배포 가이드
- README.md: 프로젝트 소개, 빠른 시작, 아키텍처 다이어그램
- DEPLOYMENT.md: Docker Compose 배포 가이드
- CHANGELOG.md: 버전 이력

## 완료 기준

```
ruff check app/ → 0 errors
mypy app/ → 0 errors
pytest tests/ → 600+ passed, <10 skipped, 220+ ACs
FE: vitest → 20/20 컴포넌트 테스트
pre-commit → 자동 통과
README.md → 존재 + 빠른 시작 가이드
```

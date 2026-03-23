---
name: gen-test
description: Generate test suites for the NeuralDB system. 4-Layer test strategy — FE Unit (Vitest + RTL + MSW), BE Unit (pytest + mock), Integration (pytest + testcontainers), E2E (Playwright). References TEST_SPEC.md, FRONTEND_TEST_SPEC.md, BACKEND_TEST_SPEC.md.
argument-hint: "[target-path] [type: unit|integration|e2e]"
allowed-tools: Read, Write, Glob, Grep, Edit, Bash
---

# Generate Test Suite

You are generating tests for the **NeuralDB** system.

## Arguments
- Target file/module: $0
- Test type: $1 (default: unit)

## Reference Specs
- **Spec-Driven Strategy**: `docs/specs/tests/TEST_STRATEGY.md` ← **반드시 먼저 읽을 것**
- FE Unit: `docs/specs/tests/FRONTEND_TEST_SPEC.md`
- BE Unit: `docs/specs/tests/BACKEND_TEST_SPEC.md`
- Integration/E2E: `docs/specs/tests/TEST_SPEC.md`
- AI Feature Specs: `docs/specs/ai/*.md` (AC 기반 테스트 생성)

## Test Frameworks by Layer

| Layer | Framework | Config | 외부 의존 |
|-------|-----------|--------|----------|
| FE Unit | Vitest + React Testing Library + MSW | vitest.config.ts | 없음 |
| FE E2E | Playwright | playwright.config.ts | BE + DB |
| BE Unit | pytest + pytest-asyncio + mock | pyproject.toml | 없음 |
| BE Integration | pytest + testcontainers | pyproject.toml | DB + Kafka + Valkey |

## Test File Structure
```
# Frontend (컴포넌트 옆에 위치)
frontend/src/components/{Category}/{Component}/{Component}.test.tsx
frontend/src/hooks/{hookName}.test.ts
frontend/src/api/hooks/{hookName}.test.ts
frontend/src/stores/{storeName}.test.ts

# Backend Unit (외부 의존 없음)
backend/tests/unit/test_schemas.py
backend/tests/unit/test_services.py
backend/tests/unit/test_adapters.py
backend/tests/unit/test_analyzers.py
backend/tests/api/test_instances_api.py

# Backend Integration (실제 DB/Kafka)
backend/tests/integration/test_metric_collection.py
backend/tests/integration/test_ash_collection.py
```

## Test Coverage Targets
- Unit tests: > 80% line coverage
- Integration tests: All API endpoints and DB operations
- E2E tests: Critical user flows (dashboard, diagnosis, playbook execution)

## Test Patterns

### Frontend Component Test
- Render test (component mounts without errors)
- Props test (renders correctly with different props)
- Interaction test (click, hover, input events)
- Accessibility test (ARIA labels, keyboard navigation)
- Snapshot test (visual regression for complex components)

### Backend Service Test (pytest)
- Happy path for each method
- Error handling (invalid input, not found, unauthorized)
- Database interaction (mock SQLAlchemy AsyncSession)
- WebSocket event emission (mock python-socketio)

### Python Agent Test
- Agent initialization with config
- Tool execution (mock external dependencies)
- Autonomy level enforcement
- Audit log generation
- Error recovery and rollback

## Spec-Driven Test Generation Rules (MUST FOLLOW)

### 규칙 1: Spec AC에서 테스트 파생
1. 대상 모듈의 Feature Spec을 먼저 읽는다 (docs/specs/ai/*.md, API_SPEC.md 등)
2. Spec의 **인수 기준(AC)** 섹션에서 각 AC를 1개 이상의 테스트 함수로 변환한다
3. AC가 없는 기능의 테스트는 생성하지 않는다

### 규칙 2: Spec 참조 필수
```python
# Backend: @spec_ref 데코레이터 사용
@spec_ref("FS-AI-010", "AC-1")
async def test_fs_ai_010_ac1_mtl_predict_returns_4_heads():
    """FS-AI-010 AC-1: POST /mtl/predict 호출 시 4개 Head 결과 반환"""
    ...
```

```typescript
// Frontend: @spec JSDoc 주석 사용
/**
 * @spec FS-AI-011 AC-4
 * @description Confidence Badge 4단계 색상 코딩 표시
 */
it('renders green badge for confidence >= 0.8', () => { ... });
```

### 규칙 3: 함수명 규칙
- Backend: `test_{spec_id}_{ac}_{description}` (snake_case)
- Frontend: describe 블록에 `[Spec: FS-XXX-XXX]`, it 블록에 AC 내용

### 규칙 4: Spec 변경 추적
- Spec AC가 추가되면 → 대응 테스트 추가
- Spec AC가 수정되면 → assertion 값 수정
- Spec AC가 삭제되면 → 대응 테스트 삭제

## General Rules
- Mock external services (DB, LLM APIs, Kafka)
- Use factories/fixtures for test data
- No flaky tests (no sleep/setTimeout, use waitFor)
- Test error paths, not just happy paths
- Include edge cases for metrics (zero values, null, overflow)

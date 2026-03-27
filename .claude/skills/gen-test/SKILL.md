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

## Pre-Flight (MUST execute before writing any code)

1. READ `docs/specs/tests/TEST_STRATEGY.md` — extract Spec-Driven rules.
2. READ `docs/specs/tests/BACKEND_TEST_SPEC.md` — extract BE test patterns.
3. READ `docs/specs/tests/FRONTEND_TEST_SPEC.md` — extract FE test patterns.
4. FIND the Feature Spec for the target module:
   - GREP `# Spec:` in target file → extract Spec IDs (e.g., `FS-AI-005`).
   - READ the corresponding Spec file in `docs/specs/`.
   - EXTRACT all `**AC-N**:` lines from the "인수 기준" section.
5. COUNT ACs. Each AC MUST produce ≥1 test function. Zero AC = abort with message.

## Test Frameworks

| Layer | Framework | Config | External Deps |
|-------|-----------|--------|---------------|
| FE Unit | Vitest + RTL + MSW | vitest.config.ts | None |
| FE E2E | Playwright | playwright.config.ts | BE + DB |
| BE Unit | pytest + pytest-asyncio + mock | pyproject.toml | None |
| BE Integration | pytest + testcontainers | pyproject.toml | DB + Kafka + Valkey |

## Output File Locations

```
# Backend Unit
backend/tests/unit/test_{spec_id_snake}_spec.py

# Backend API
backend/tests/api/test_{module}_api.py

# Frontend Unit
frontend/tests/unit/{componentName}.test.ts(x)

# Backend Integration
backend/tests/integration/test_{feature}_e2e.py
```

## File Structure Rules (every generated file MUST contain)

### Rule 1: Header Comment
```python
# Spec: {SPEC_ID}
"""Spec-Driven tests for {feature name}.

Feature Spec: docs/specs/{category}/{SPEC_FILE}.md
Test Strategy: docs/specs/tests/TEST_STRATEGY.md

AC Coverage:
  AC-1: {description} → test_{spec_snake}_ac1_{desc}
  AC-2: {description} → test_{spec_snake}_ac2_{desc}
  ...
"""
```

### Rule 2: Import spec_ref
```python
from tests.conftest import spec_ref
```

### Rule 3: Every test function MUST have @spec_ref
```python
@spec_ref("{SPEC_ID}", "AC-{N}")
@pytest.mark.asyncio
async def test_{spec_id_snake}_ac{n}_{description}():
    """FS-AI-005 AC-1: {AC description from Spec}"""
    ...
```

### Rule 4: Function Naming Convention
- Backend: `test_{spec_id_snake}_ac{n}_{description}` (snake_case)
  - Example: `test_fs_ai_005_ac1_report_generation_within_30s`
- Frontend: `describe('[Spec: FS-XXX]')` → `it('AC-N: {description}')`

### Rule 5: AC → Test Mapping (minimum)
- Each AC → ≥1 happy-path test
- Each AC with error condition → +1 error-path test
- Each AC with boundary value → +1 boundary test
- Schema validation AC → Pydantic ValidationError test

## Test Pattern Rules

### Backend Service Test (pytest)
1. MOCK all external deps: DB session (`AsyncMock`), LLM (`AsyncMock`), Valkey, Celery.
2. USE `mock_session` fixture with `MagicMock` for `.execute()`, `.scalars()`, `.all()`.
3. TEST happy path for each service method.
4. TEST error handling: invalid input, not found, LLM failure.
5. ASSERT response schema matches Pydantic model.
6. ASSERT timing: `generation_time_ms >= 0` (mock is instant).

### Backend API Test (httpx)
1. USE `client` fixture from `conftest.py` (httpx.AsyncClient).
2. USE `auth_client` fixture for authenticated endpoints (override `get_current_user`).
3. ASSERT HTTP status codes: 200/201/204/400/401/403/404/409.
4. ASSERT response JSON matches schema.
5. ASSERT OpenAPI route is registered: check `app.routes`.

### Frontend Component Test (Vitest + RTL)
1. RENDER component with minimal required props.
2. ASSERT component mounts without errors.
3. ASSERT ARIA labels present for accessibility.
4. TEST user interactions (click, input) with `userEvent`.
5. USE MSW for API mocking (no fetch mocking).

### Agent Test
1. MOCK LLM via `_get_llm` patch.
2. TEST autonomy level enforcement (FS-AUTO-002).
3. TEST confidence gate (score < 0.5 → blocked).
4. ASSERT audit log generation for ai_decision.

## Validation Checklist (self-verify before outputting)

- [ ] Every AC in the Feature Spec has ≥1 test function
- [ ] Every test function has `@spec_ref` decorator
- [ ] Function names follow `test_{spec_snake}_ac{n}_{desc}` pattern
- [ ] File header lists AC → test mapping
- [ ] No external deps in unit tests (all mocked)
- [ ] No `sleep()` or `time.sleep()` in tests
- [ ] `import from tests.conftest import spec_ref` present
- [ ] RUN `uv run pytest {test_file} -v --tb=short` and report results

## Post-Generation (MUST execute after writing)

1. RUN `uv run pytest {generated_file} -v --tb=short` — all tests must pass.
2. VERIFY AC summary output: `SPEC ACCEPTANCE CRITERIA SUMMARY` section in pytest output.
3. REPORT: `{N} tests, {M} ACs, {P} passed, {F} failed`.
4. If failures exist, FIX and re-run until 0 failures.

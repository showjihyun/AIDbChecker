---
name: gen-fastapi-route
description: Generate FastAPI route with request/response schemas, dependency injection, error handling, and OpenAPI documentation. Follows the NeuralDB API conventions with Pydantic v2 validation and async patterns.
argument-hint: "[route-name] [method: get|post|put|delete|ws]"
allowed-tools: Read, Write, Glob, Grep, Edit, Bash
---

# Generate FastAPI Route

## Arguments
- Route name: $0
- HTTP method: $1 (default: get)

## Pre-Flight (MUST execute before writing any code)

1. READ `docs/TECH_STACK.md` — extract API conventions and authorized packages.
2. READ `docs/specs/api/API_SPEC.md` — check if this route is already defined.
3. FIND the Feature Spec for this route:
   - GREP `$0` in `docs/specs/**/*.md` — locate the relevant Spec.
   - EXTRACT Spec ID, AC list, request/response schemas.
   - If NO Spec exists: ABORT with "Spec-First: create Feature Spec before generating code."
4. READ `AGENTS.md` Section 5 — extract Good vs Bad Python patterns.
5. READ `backend/app/api/deps.py` — extract available dependencies (get_session, get_current_user, require_role).
6. READ `backend/app/main.py` — check for existing router registration conflicts.

## Output Files (all 4 MUST be generated)

```
backend/app/api/v1/{route_name}.py         # Route handler
backend/app/schemas/{route_name}.py        # Pydantic request/response
backend/app/services/{route_name}.py       # Business logic service
backend/tests/unit/test_{route_name}.py    # Unit tests (@spec_ref)
```

## Route Handler Rules

### Rule 1: File Header
```python
# Spec: {SPEC_ID}
"""Route description — one line summary.

{HTTP_METHOD} /api/v1/{route-name} — {description}
Auth required: {role list or 'public'}
"""
```

### Rule 2: Imports (exact pattern)
```python
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session, require_role
from app.models.user import User
from app.schemas.{name} import {Name}Request, {Name}Response
from app.services import {name} as {name}_service
```

### Rule 3: Router Declaration
```python
logger = structlog.get_logger(__name__)
router = APIRouter()
```

### Rule 4: Endpoint Decorator (exact pattern)
```python
@router.{method}(
    "/{route-name}",
    response_model={Name}Response,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="{Short summary}",
    description="{Detailed description for OpenAPI docs}",
)
async def {function_name}(
    body: {Name}Request,                          # POST/PUT only
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> {Name}Response:
    """Docstring matching Spec AC."""
```

### Rule 5: Error Handling
```python
# Validation errors → 400
if invalid_input:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Specific message")

# Not found → 404
if not resource:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="{Resource} not found")

# Conflict → 409
if duplicate:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already exists")
```

### Rule 6: Logging
```python
logger.info("{route}.{action}", key1=val1, key2=val2, user=current_user.email)
```

## Schema Rules (Pydantic v2)

### Rule 7: File Header
```python
# Spec: {SPEC_ID}, DM-001
"""Pydantic v2 schemas for {feature name} API operations."""
```

### Rule 8: Request Schema
```python
class {Name}Request(BaseModel):
    """Request schema — field descriptions from Spec."""
    field: Type = Field(..., description="From Spec Section X.X")
```

### Rule 9: Response Schema
```python
class {Name}Response(BaseModel):
    """Response schema — matches Spec Section X.X."""
    id: UUID
    # ... domain fields ...
    created_at: datetime
```

### Rule 10: Enum Values from Spec
- IF Spec defines allowed values → CREATE `str, Enum` class.
- NEVER hardcode string literals that should be enums.

## Service Rules

### Rule 11: Service Pattern
```python
# Spec: {SPEC_ID}
"""Service layer for {feature}. Business logic only, no HTTP concerns."""

async def {action}(session: AsyncSession, *, param: Type) -> ResponseType:
    """Spec: {SPEC_ID} — {AC description}"""
    ...
```

### Rule 12: DB Operations
- USE `select()` + `session.execute()` (SQLAlchemy 2.0 style).
- NEVER use `session.query()` or `.filter()`.
- USE `async def` for all DB operations.
- USE `statement_timeout` for read queries: `SET LOCAL statement_timeout = '5s'`.

### Rule 13: LLM Operations
- USE `LLMProviderManager.get_llm()` — never import openai/anthropic directly.
- SET `temperature`, `max_tokens`, `request_timeout` explicitly.
- HANDLE LLM failure gracefully (try/except → fallback response).

## Test Generation Rules

### Rule 14: Test File (auto-generated with route)
- FOLLOW `/gen-test` Skill rules exactly.
- USE `@spec_ref("{SPEC_ID}", "AC-{N}")` on every test.
- TEST: happy path, 400, 401, 404 for each endpoint.

## Registration Rules

### Rule 15: Register in main.py
- ADD import: `from app.api.v1 import {name}`.
- ADD router: `app.include_router({name}.router, prefix="/api/v1", tags=["{name}"], dependencies=_auth_dep)`.
- VERIFY no duplicate route paths.

## Validation Checklist (self-verify before outputting)

- [ ] Feature Spec exists and was read
- [ ] All 4 files generated (route, schema, service, test)
- [ ] `# Spec: {ID}` header in all files
- [ ] All methods are `async def`
- [ ] SQLAlchemy 2.0 patterns (select, not query)
- [ ] Pydantic v2 (BaseModel, Field)
- [ ] structlog used (not print/logging)
- [ ] `require_role()` on protected endpoints
- [ ] Router registered in main.py
- [ ] Tests use `@spec_ref` and pass

## Post-Generation (MUST execute)

1. RUN `uv run ruff check backend/app/api/v1/{name}.py backend/app/schemas/{name}.py backend/app/services/{name}.py` — 0 errors.
2. RUN `uv run pytest backend/tests/unit/test_{name}*.py -v --tb=short` — all pass.
3. REPORT: files created, routes registered, tests passed.

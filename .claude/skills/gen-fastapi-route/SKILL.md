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

## Reference
- Read `docs/TECH_STACK.md` for API conventions
- Read `ai-db-monitor-architecture-spec-v3.md` for API contracts

## Output Files
```
backend/app/api/v1/{route_name}.py         # Route handler
backend/app/schemas/{route_name}.py        # Pydantic request/response
backend/app/services/{route_name}.py       # Business logic service
backend/tests/unit/test_{route_name}.py    # Unit tests
```

## FastAPI Route Template
```python
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.schemas.{name} import {Name}Create, {Name}Response, {Name}List
from app.services.{name} import {Name}Service
from app.models.user import User

router = APIRouter(prefix="/{route}", tags=["{Route}"])

@router.get("/", response_model={Name}List)
async def list_{names}(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> {Name}List:
    """List all {names} with cursor-based pagination."""
    service = {Name}Service(db)
    return await service.list(skip=skip, limit=limit)
```

## Conventions
- All routes async (`async def`)
- Pydantic v2 for request/response schemas
- Dependency injection for DB session, auth, services
- HTTP status codes: 200 OK, 201 Created, 204 No Content, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found
- Cursor-based pagination (not offset) for large datasets
- OpenTelemetry span on each endpoint
- Structured logging with correlation ID
- Rate limiting decorator for public endpoints

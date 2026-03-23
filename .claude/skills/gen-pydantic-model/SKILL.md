---
name: gen-pydantic-model
description: Generate Pydantic v2 schema models for FastAPI request/response validation. Creates Create, Update, Response, and List schemas with proper field validation, serialization config, and examples.
argument-hint: "[model-name]"
allowed-tools: Read, Write, Glob, Grep, Edit
---

# Generate Pydantic Schema

## Arguments
- Model name: $ARGUMENTS

## Output File
```
backend/app/schemas/{model_name}.py
```

## Template
```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional

class {Name}Base(BaseModel):
    """Shared fields."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class {Name}Create({Name}Base):
    """Request body for creating a {name}."""
    pass

class {Name}Update(BaseModel):
    """Partial update. All fields optional."""
    model_config = ConfigDict(from_attributes=True)

class {Name}Response({Name}Base):
    """Single {name} response."""
    id: UUID
    created_at: datetime
    updated_at: datetime

class {Name}List(BaseModel):
    """Paginated list response."""
    items: list[{Name}Response]
    total: int
    has_next: bool
    next_cursor: Optional[str] = None
```

## Rules
- Use `UUID` for IDs, `datetime` for timestamps
- `ConfigDict(from_attributes=True)` for ORM compatibility
- Field constraints: `Field(min_length=1, max_length=255)`, `Field(ge=0)`, etc.
- Custom validators with `@field_validator`
- Enum types for status/severity/type fields
- Optional fields use `Optional[T] = None`
- List responses always include pagination metadata
- Add `model_config` examples for OpenAPI docs

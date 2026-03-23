---
name: gen-sqlalchemy-model
description: Generate SQLAlchemy 2.0 async models for PostgreSQL 16. Creates table definitions with proper column types, indexes, relationships, JSONB fields, partitioning support, and UUID v7 primary keys.
argument-hint: "[model-name]"
allowed-tools: Read, Write, Glob, Grep, Edit
---

# Generate SQLAlchemy Model

## Arguments
- Model name: $ARGUMENTS

## Reference
- Read `docs/TECH_STACK.md` for DB conventions

## Output File
```
backend/app/models/{model_name}.py
```

## Template
```python
import uuid
from datetime import datetime
from sqlalchemy import (
    String, DateTime, Integer, Float, Boolean, Text, ForeignKey, Index,
    func, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class {Name}(Base):
    __tablename__ = "{table_name}"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    # Indexes
    __table_args__ = (
        Index("ix_{table}_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<{Name}(id={self.id})>"
```

## Base Model (backend/app/models/base.py)
```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

## PostgreSQL 16 Features to Use
- `UUID` with `gen_random_uuid()` server default
- `JSONB` for flexible metadata/config fields
- `ARRAY` for tags, categories
- Native partitioning for time-series tables (metric_sample, active_session)
- Partial indexes: `Index("ix_active", "status", postgresql_where=text("status = 'active'"))`
- GIN indexes for JSONB: `Index("ix_meta", "metadata", postgresql_using="gin")`
- pgvector: `from pgvector.sqlalchemy import Vector` for embedding columns

## Rules
- All tables have `id`, `created_at`, `updated_at`
- Use `Mapped[T]` type annotations (SQLAlchemy 2.0 style)
- Use `mapped_column()` not `Column()`
- Relationships use `Mapped["RelatedModel"]` with `relationship()`
- Enums as `String` with Python `enum.Enum` for validation
- Soft delete via `deleted_at: Mapped[Optional[datetime]]`
- Table names: snake_case plural (`db_instances`, `metric_samples`)

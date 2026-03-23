---
name: gen-alembic-migration
description: Generate Alembic database migration scripts for PostgreSQL 16. Creates upgrade/downgrade functions with proper DDL operations, data migrations, partitioning setup, and pgvector extension management.
argument-hint: "[migration-description]"
allowed-tools: Read, Write, Glob, Grep, Edit, Bash
---

# Generate Alembic Migration

## Arguments
- Description: $ARGUMENTS

## Steps

1. Read existing models in `backend/app/models/`
2. Check current migration chain in `backend/migrations/versions/`
3. Generate migration script

## Auto-generate Command
```bash
cd backend && alembic revision --autogenerate -m "$ARGUMENTS"
```

## Manual Migration Template
```python
"""${ARGUMENTS}

Revision ID: {revision}
Revises: {down_revision}
Create Date: {create_date}
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '{revision}'
down_revision = '{down_revision}'

def upgrade() -> None:
    op.create_table(
        '{table_name}',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

def downgrade() -> None:
    op.drop_table('{table_name}')
```

## PostgreSQL 16 Specific Operations
```python
# Enable extensions
op.execute("CREATE EXTENSION IF NOT EXISTS vector")
op.execute("CREATE EXTENSION IF NOT EXISTS pg_partman")
op.execute("CREATE EXTENSION IF NOT EXISTS pg_cron")

# Create partitioned table
op.execute("""
    CREATE TABLE metric_samples (
        id UUID DEFAULT gen_random_uuid(),
        instance_id UUID NOT NULL,
        sampled_at TIMESTAMPTZ NOT NULL,
        data JSONB NOT NULL
    ) PARTITION BY RANGE (sampled_at)
""")

# Add partman management
op.execute("""
    SELECT partman.create_parent(
        p_parent_table := 'public.metric_samples',
        p_control := 'sampled_at',
        p_interval := '1 day',
        p_premake := 7
    )
""")
```

## Rules
- Always provide both `upgrade()` and `downgrade()`
- Use `op.execute()` for raw SQL (extensions, partitions)
- Create indexes separately from tables
- Test migration: `alembic upgrade head` then `alembic downgrade -1`
- Data migrations in separate files from schema migrations

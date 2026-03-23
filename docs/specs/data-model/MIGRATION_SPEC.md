# Migration Spec: Alembic DB 마이그레이션 전략

> **Spec ID**: DM-MIG-001
> **PRD 참조**: §8 기술 스택 (Alembic 1.13+)
> **상태**: Approved
> **Phase**: MVP

---

## 1. Alembic 설정

```ini
# backend/alembic.ini
[alembic]
script_location = migrations
sqlalchemy.url = postgresql+asyncpg://neuraldb:neuraldb@localhost:5432/neuraldb

[loggers]
keys = root,sqlalchemy,alembic
```

```python
# backend/migrations/env.py
# Spec: DM-MIG-001

from app.models.base import Base  # 모든 모델 import
from app.config import settings

target_metadata = Base.metadata

# async 마이그레이션 지원
from alembic import context
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

def run_migrations_online():
    connectable = create_async_engine(str(settings.DATABASE_URL))
    asyncio.run(_run_async(connectable))

async def _run_async(connectable):
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
```

---

## 2. 리비전 네이밍 규칙

```
형식: {sequence}_{short_description}.py
예시:
  001_initial_schema.py
  002_add_mtl_predictions.py
  003_add_rag_documents_hnsw_index.py
```

---

## 3. 초기 마이그레이션 (001_initial_schema)

### 3.1 Extension 활성화

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";
CREATE EXTENSION IF NOT EXISTS "pg_partman";
```

### 3.2 MVP 테이블 생성 순서 (FK 의존성)

```
1. users                    (FK 없음)
2. db_instances              (FK 없음)
3. metric_samples            (FK: db_instances, PARTITION BY RANGE)
4. active_sessions           (FK: db_instances, PARTITION BY RANGE)
5. incidents                 (FK: db_instances)
6. baselines                 (FK: db_instances)
7. schema_changes            (FK: db_instances)
8. audit_logs                (FK: users, PARTITION BY RANGE)
9. nl2sql_histories          (FK: db_instances, users)
10. rag_documents            (FK: incidents — pgvector 인덱스)
11. mtl_predictions          (FK: incidents, db_instances)
12. reasoning_chains         (FK: mtl_predictions)
13. evidence_links           (FK: mtl_predictions)
```

### 3.3 파티셔닝 설정 (pg_partman)

```sql
-- metric_samples: 일별 파티션, 7일 보관
SELECT create_parent(
    p_parent_table := 'public.metric_samples',
    p_control := 'sampled_at',
    p_type := 'native',
    p_interval := 'daily',
    p_premake := 3
);

-- active_sessions: 일별 파티션, 7일 보관
SELECT create_parent(
    p_parent_table := 'public.active_sessions',
    p_control := 'sampled_at',
    p_type := 'native',
    p_interval := 'daily',
    p_premake := 3
);

-- audit_logs: 월별 파티션, 1년 보관
SELECT create_parent(
    p_parent_table := 'public.audit_logs',
    p_control := 'created_at',
    p_type := 'native',
    p_interval := 'monthly',
    p_premake := 2
);
```

### 3.4 pg_cron 유지보수 작업

```sql
-- 매일 03:00 — 오래된 파티션 삭제
SELECT cron.schedule('partition-cleanup', '0 3 * * *',
    $$SELECT run_maintenance_proc()$$);

-- 매일 04:00 — Materialized View 리프레시 (ASH 다운샘플링)
SELECT cron.schedule('ash-downsample', '0 4 * * *',
    $$REFRESH MATERIALIZED VIEW CONCURRENTLY ash_hourly_summary$$);
```

### 3.5 pgvector HNSW 인덱스

```sql
-- rag_documents 임베딩 검색용
CREATE INDEX idx_rag_documents_embedding
    ON rag_documents USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

### 3.6 FK Cascade 정책

| Parent | Child | ON DELETE | 이유 |
|--------|-------|-----------|------|
| db_instances | metric_samples | CASCADE | 인스턴스 삭제 시 메트릭 삭제 |
| db_instances | active_sessions | CASCADE | 인스턴스 삭제 시 ASH 삭제 |
| db_instances | incidents | SET NULL | 인시던트 이력 보존 |
| incidents | mtl_predictions | CASCADE | 인시던트 삭제 시 예측 삭제 |
| mtl_predictions | reasoning_chains | CASCADE | 예측 삭제 시 추론 삭제 |
| mtl_predictions | evidence_links | CASCADE | 예측 삭제 시 증거 삭제 |
| users | audit_logs | SET NULL | 사용자 삭제 시 로그 보존 |
| incidents | rag_documents | CASCADE | 인시던트 삭제 시 임베딩 삭제 |

---

## 4. 롤백 전략

```bash
# 최신 마이그레이션 롤백
uv run alembic downgrade -1

# 특정 리비전으로 롤백
uv run alembic downgrade 001

# 주의: 파티션 테이블 롤백 시 pg_partman 정리 필요
```

---

## 5. 인수 기준

- [ ] AC-1: `uv run alembic upgrade head` 로 MVP 전체 스키마 생성
- [ ] AC-2: `uv run alembic downgrade base` 로 완전 롤백
- [ ] AC-3: pg_partman 파티션이 자동 생성됨 (3일 premake)
- [ ] AC-4: pgvector HNSW 인덱스 EXPLAIN에서 확인

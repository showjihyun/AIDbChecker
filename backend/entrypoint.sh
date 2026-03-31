#!/bin/sh
# Spec: MVP.md §7.1 — Docker auto-setup entrypoint
# Runs migration + seed before starting the application server.
set -e

# --- 1. Wait for PostgreSQL to be ready ---
echo "[entrypoint] Waiting for PostgreSQL at ${DB_HOST:-postgres}:${DB_PORT:-5432}..."

MAX_RETRIES=30
RETRY_COUNT=0

while [ "$RETRY_COUNT" -lt "$MAX_RETRIES" ]; do
  if pg_isready -h "${DB_HOST:-postgres}" -p "${DB_PORT:-5432}" -U "${DB_USER:-neuraldb}" -q 2>/dev/null; then
    echo "[entrypoint] PostgreSQL is ready."
    break
  fi
  RETRY_COUNT=$((RETRY_COUNT + 1))
  echo "[entrypoint] PostgreSQL not ready (attempt ${RETRY_COUNT}/${MAX_RETRIES}). Retrying in 2s..."
  sleep 2
done

if [ "$RETRY_COUNT" -eq "$MAX_RETRIES" ]; then
  echo "[entrypoint] ERROR: PostgreSQL not reachable after ${MAX_RETRIES} attempts. Exiting."
  exit 1
fi

# --- 2. Run Alembic migrations (idempotent — skips already-applied revisions) ---
echo "[entrypoint] Running Alembic migrations..."
PYTHONPATH=. uv run alembic upgrade head
echo "[entrypoint] Migrations complete."

# --- 3. Run seed script (idempotent — skips if admin already exists) ---
echo "[entrypoint] Running seed script..."
PYTHONPATH=. uv run python -m app.db.seed
echo "[entrypoint] Seed complete."

# --- 3b. Run demo seed (idempotent — skips if demo data exists) ---
echo "[entrypoint] Running demo seed..."
PYTHONPATH=. uv run python -m app.db.seed_demo
echo "[entrypoint] Demo seed complete."

# --- 4. Auto-build Knowledge Graph for all instances (non-blocking, 30s max) ---
echo "[entrypoint] Building Knowledge Graph..."
timeout 30 sh -c 'PYTHONPATH=. uv run python -c "
import asyncio
async def build_graphs():
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.models.db_instance import DBInstance
    from app.services.graph_rag import SchemaGraphBuilder
    from app.utils.dsn import build_target_dsn
    import asyncpg
    async with AsyncSessionLocal() as session:
        stmt = select(DBInstance).where(DBInstance.is_active.is_(True), DBInstance.deleted_at.is_(None))
        result = await session.execute(stmt)
        for inst in result.scalars().all():
            try:
                dsn = build_target_dsn(inst)
                pool = await asyncio.wait_for(asyncpg.create_pool(dsn, min_size=1, max_size=2, command_timeout=5), timeout=5)
                builder = SchemaGraphBuilder()
                nodes, edges = await builder.build_graph(session, inst.id, pool)
                await session.commit()
                await pool.close()
                print(f\"  Graph built: {inst.name} ({nodes} nodes, {edges} edges)\")
            except Exception as e:
                print(f\"  Graph skip: {inst.name} ({e})\")
asyncio.run(build_graphs())
"' 2>/dev/null || echo "[entrypoint] Graph build skipped or timed out (non-critical)."
echo "[entrypoint] Graph build complete."

# --- 5. Start the application ---
echo "[entrypoint] Starting uvicorn..."
exec "$@"

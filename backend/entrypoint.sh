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

# --- 4. Start the application ---
echo "[entrypoint] Starting uvicorn..."
exec "$@"

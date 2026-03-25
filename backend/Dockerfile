# Spec: TECH_STACK.md §6.1
FROM python:3.12-slim

# Install system dependencies for pg_isready and psycopg2
RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client libpq-dev gcc && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies (cached layer)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# Copy application code
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Entrypoint runs migration + seed, then hands off to CMD
ENTRYPOINT ["./entrypoint.sh"]

# Default command (passed as "$@" to entrypoint.sh)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

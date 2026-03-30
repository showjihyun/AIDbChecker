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

# Fix CRLF line endings (Windows → Linux) and make executable
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

# SEC-05: Run as non-root user
RUN adduser --disabled-password --gecos "" --uid 1001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Entrypoint runs migration + seed, then hands off to CMD
ENTRYPOINT ["./entrypoint.sh"]

# Default command (passed as "$@" to entrypoint.sh)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

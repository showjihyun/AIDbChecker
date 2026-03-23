---
name: gen-docker
description: Generate Docker and docker-compose configurations for the NeuralDB system. Creates Dockerfiles for frontend/backend, compose files for local development with PostgreSQL 16, Valkey, Kafka, and Prometheus, and production compose variants.
argument-hint: "[target: dev|prod|service-name]"
allowed-tools: Read, Write, Glob, Grep, Edit, Bash
---

# Generate Docker Configuration

## Arguments
- Target: $ARGUMENTS (default: dev)

## Output Files
```
infra/docker/
├── docker-compose.yml              # Local development
├── docker-compose.prod.yml         # Production overlay
├── Dockerfile.frontend             # React build
├── Dockerfile.backend              # Python/FastAPI
├── .env.example                    # Environment variables
└── init-scripts/
    └── 01-init-extensions.sql      # PostgreSQL extensions
```

## docker-compose.yml Template
```yaml
services:
  # PostgreSQL 16 (Meta + Metrics + Vector)
  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: neuraldb
      POSTGRES_USER: neuraldb
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U neuraldb"]
      interval: 5s

  # Valkey (Cache)
  valkey:
    image: valkey/valkey:8-alpine
    ports: ["6379:6379"]

  # Kafka (Event Streaming)
  kafka:
    image: bitnami/kafka:3.8
    ports: ["9092:9092"]
    environment:
      KAFKA_CFG_NODE_ID: 0
      KAFKA_CFG_PROCESS_ROLES: controller,broker
      KAFKA_CFG_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: 0@kafka:9093
      KAFKA_CFG_CONTROLLER_LISTENER_NAMES: CONTROLLER

  # FastAPI Backend
  backend:
    build:
      context: ../../backend
      dockerfile: ../infra/docker/Dockerfile.backend
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://neuraldb:${DB_PASSWORD}@postgres:5432/neuraldb
      VALKEY_URL: redis://valkey:6379/0
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
    depends_on:
      postgres: { condition: service_healthy }
      valkey: { condition: service_started }

  # Celery Worker
  celery-worker:
    build:
      context: ../../backend
      dockerfile: ../infra/docker/Dockerfile.backend
    command: celery -A app.tasks worker -l info -c 4
    depends_on: [backend]

  # Celery Beat (Scheduler)
  celery-beat:
    build:
      context: ../../backend
      dockerfile: ../infra/docker/Dockerfile.backend
    command: celery -A app.tasks beat -l info
    depends_on: [backend]

  # React Frontend
  frontend:
    build:
      context: ../../frontend
      dockerfile: ../infra/docker/Dockerfile.frontend
    ports: ["3000:80"]
    depends_on: [backend]

  # ===========================
  # Self-Monitoring (NeuralDB 자체 감시)
  # ===========================

  # Prometheus (자체 시스템 메트릭 수집 — 대상 DB 메트릭 아님)
  prometheus:
    image: prom/prometheus:v2.52.0
    ports: ["9090:9090"]
    volumes:
      - ../monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  # System DB Exporter (시스템 PostgreSQL 16 자체 헬스)
  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:v0.15.0
    environment:
      DATA_SOURCE_NAME: "postgresql://neuraldb:${DB_PASSWORD}@postgres:5432/neuraldb?sslmode=disable"
    ports: ["9187:9187"]
    depends_on: [postgres]

  # Valkey Exporter
  redis-exporter:
    image: oliver006/redis_exporter:v1.58.0
    environment:
      REDIS_ADDR: "redis://valkey:6379"
    ports: ["9121:9121"]
    depends_on: [valkey]

  # Kafka Exporter
  kafka-exporter:
    image: danielqsj/kafka-exporter:v1.7.0
    command: ["--kafka.server=kafka:9092"]
    ports: ["9308:9308"]
    depends_on: [kafka]

volumes:
  pgdata:
```

## PostgreSQL Init Script
```sql
-- 01-init-extensions.sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_partman;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

## Backend Dockerfile (uv 기반 - MUST)
```dockerfile
# Dockerfile.backend
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

FROM base AS deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM base AS runtime
COPY --from=deps /app/.venv /app/.venv
COPY . .
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> **pip install 금지**: Dockerfile에서도 반드시 `uv sync --frozen` 사용. `requirements.txt` 생성 금지.

## Rules
- Use specific image tags, not `latest`
- Health checks on all services
- Environment variables via `.env` file
- Named volumes for persistent data
- Multi-stage builds for production images
- Non-root user in production containers
- `pgvector/pgvector:pg16` base image (includes pgvector extension)
- **Python dependencies: `uv sync --frozen` only (no pip)**

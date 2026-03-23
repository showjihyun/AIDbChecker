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

  # Prometheus
  prometheus:
    image: prom/prometheus:v2.52.0
    ports: ["9090:9090"]
    volumes:
      - ../monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

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

## Rules
- Use specific image tags, not `latest`
- Health checks on all services
- Environment variables via `.env` file
- Named volumes for persistent data
- Multi-stage builds for production images
- Non-root user in production containers
- `pgvector/pgvector:pg16` base image (includes pgvector extension)

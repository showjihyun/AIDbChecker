# Settings Spec: Pydantic Settings 환경 설정

> **Spec ID**: CFG-001
> **PRD 참조**: §8 기술 스택, §10 제약 조건
> **상태**: Approved
> **Phase**: MVP

---

## 1. Settings 클래스 구조

```python
# backend/app/config.py
# Spec: CFG-001

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PostgresDsn, AnyHttpUrl

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────
    APP_NAME: str = "NeuralDB"
    APP_ENV: str = Field(default="development", pattern="^(development|staging|production)$")
    DEBUG: bool = False
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    API_HOST: str = "0.0.0.0"
    API_PORT: int = Field(default=8000, ge=1024, le=65535)
    API_WORKERS: int = Field(default=4, ge=1, le=32)
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # ── Database (PostgreSQL 16) ─────────────────
    DATABASE_URL: PostgresDsn = "postgresql+asyncpg://neuraldb:neuraldb@localhost:5432/neuraldb"
    DB_POOL_SIZE: int = Field(default=20, ge=5, le=100)
    DB_POOL_OVERFLOW: int = Field(default=10, ge=0, le=50)
    DB_POOL_TIMEOUT: int = Field(default=30, ge=5, le=120)  # seconds
    DB_POOL_RECYCLE: int = Field(default=3600, ge=300)  # seconds
    DB_ECHO: bool = False  # SQL 로깅 (개발 모드용)
    DB_STATEMENT_TIMEOUT: int = Field(default=30000, ge=1000)  # ms

    # ── Valkey (Cache + Celery Broker) ───────────
    VALKEY_URL: str = "redis://localhost:6379/0"  # redis:// 프로토콜 호환
    VALKEY_CACHE_DB: int = 0
    VALKEY_CELERY_DB: int = 1
    VALKEY_DEFAULT_TTL: int = Field(default=300, ge=60)  # seconds

    # ── Kafka ────────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_SECURITY_PROTOCOL: str = Field(default="PLAINTEXT", pattern="^(PLAINTEXT|SSL|SASL_PLAINTEXT|SASL_SSL)$")
    KAFKA_CONSUMER_GROUP: str = "neuraldb"
    KAFKA_AUTO_OFFSET_RESET: str = "latest"

    # ── JWT Auth ─────────────────────────────────
    JWT_SECRET_KEY: str  # REQUIRED, no default
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = Field(default=30, ge=5, le=1440)
    JWT_REFRESH_EXPIRE_DAYS: int = Field(default=7, ge=1, le=30)

    # ── LLM (Online) ────────────────────────────
    LLM_MODE: str = Field(default="online", pattern="^(online|offline|auto)$")
    OPENAI_API_KEY: str | None = None  # online 모드 시 필수
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MAX_TOKENS: int = Field(default=4096, ge=256, le=16384)
    OPENAI_TEMPERATURE: float = Field(default=0.1, ge=0.0, le=2.0)
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # ── LLM (Offline) ───────────────────────────
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral:7b"

    # ── LLM Budget ───────────────────────────────
    LLM_DAILY_TOKEN_LIMIT: int = Field(default=500_000, ge=10_000)
    LLM_MONTHLY_COST_LIMIT_USD: float = Field(default=500.0, ge=0)
    LLM_OFFLINE_FALLBACK_PERCENT: int = Field(default=80, ge=50, le=100)

    # ── RAG (Embedding) ─────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSIONS: int = 384
    EMBEDDING_DEVICE: str = "cpu"
    RAG_MIN_SIMILARITY: float = Field(default=0.7, ge=0.0, le=1.0)
    RAG_TOP_K: int = Field(default=3, ge=1, le=10)
    RAG_CACHE_TTL: int = Field(default=300, ge=60)  # seconds

    # ── Slack ────────────────────────────────────
    SLACK_WEBHOOK_URL: str | None = None
    SLACK_BOT_TOKEN: str | None = None
    SLACK_ALERT_CHANNEL: str = "#db-alerts"

    # ── Monitoring (Self) ────────────────────────
    PROMETHEUS_ENABLED: bool = True
    OTEL_EXPORTER_ENDPOINT: str | None = None
    SENTRY_DSN: str | None = None

    # ── Metric Collection ────────────────────────
    COLLECT_HOT_INTERVAL_SEC: float = Field(default=1.0, ge=0.5, le=60)
    COLLECT_WARM_INTERVAL_SEC: float = Field(default=10.0, ge=5, le=300)
    COLLECT_COLD_INTERVAL_SEC: float = Field(default=60.0, ge=30, le=3600)
    COLLECT_STATEMENT_TIMEOUT_MS: int = Field(default=500, ge=100, le=5000)
    MAX_INSTANCES: int = Field(default=10, ge=1, le=200)

    # ── Confidence Score ─────────────────────────
    CONFIDENCE_HIGH_THRESHOLD: float = 0.8
    CONFIDENCE_MEDIUM_THRESHOLD: float = 0.5
    CONFIDENCE_LOW_THRESHOLD: float = 0.3
    CONFIDENCE_BLOCK_AUTO_BELOW: float = 0.5

settings = Settings()
```

---

## 2. 환경별 필수/선택 매트릭스

| 변수 | Development | Staging | Production |
|------|------------|---------|-----------|
| `JWT_SECRET_KEY` | 필수 | 필수 | 필수 |
| `DATABASE_URL` | 기본값 OK | 필수 | 필수 |
| `OPENAI_API_KEY` | 선택 (offline 가능) | 필수 | 필수 |
| `SLACK_WEBHOOK_URL` | 선택 | 필수 | 필수 |
| `KAFKA_BOOTSTRAP_SERVERS` | 기본값 OK | 필수 | 필수 |
| `SENTRY_DSN` | 선택 | 필수 | 필수 |

---

## 3. `.env.example`

```env
# App
APP_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG
JWT_SECRET_KEY=change-me-in-production

# Database
DATABASE_URL=postgresql+asyncpg://neuraldb:neuraldb@localhost:5432/neuraldb

# Valkey
VALKEY_URL=redis://localhost:6379/0

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# LLM
LLM_MODE=online
OPENAI_API_KEY=sk-...
# OLLAMA_HOST=http://localhost:11434

# Slack (optional for dev)
# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

---

## 4. 인수 기준

- [ ] AC-1: `Settings()` 인스턴스가 `.env` 파일에서 값을 로드
- [ ] AC-2: 필수 값(`JWT_SECRET_KEY`) 누락 시 `ValidationError` 발생
- [ ] AC-3: `APP_ENV` 패턴 검증 (`development|staging|production` 외 값 거부)
- [ ] AC-4: `settings` 싱글톤이 FastAPI `Depends()`에서 주입 가능

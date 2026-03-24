# Spec: DM-001, AG-001
"""NeuralDB application configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "NeuralDB"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = True
    APP_PORT: int = 8000
    APP_SECRET_KEY: str = "change-me-in-production"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # System Database (PostgreSQL 16 — meta + metrics + vector)
    DATABASE_URL: str = "postgresql+asyncpg://neuraldb:neuraldb@localhost:5432/neuraldb"
    DB_POOL_SIZE: int = 20
    DB_POOL_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False

    # Valkey (Redis-compatible cache + Celery broker)
    VALKEY_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # JWT Authentication
    JWT_SECRET_KEY: str = "jwt-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AI Configuration
    AI_MODE: Literal["online", "offline"] = "online"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral:7b"

    # Embedding
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSIONS: int = 384

    # Notifications
    SLACK_WEBHOOK_URL: str = ""
    SLACK_ALERT_COOLDOWN_MINUTES: int = 30

    # Credential Encryption (ADR-007)
    CREDENTIAL_ENCRYPTION_KEY: str = Field(
        default="change-me-32-byte-key-for-fernet",
        description="Fernet encryption key for target DB credentials",
    )

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()

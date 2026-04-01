# Spec: DM-001, AG-001
"""NeuralDB application configuration via Pydantic Settings."""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

# Resolve env_file path relative to this file (backend/app/config.py -> backend/.env)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "NeuralDB"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = True
    APP_PORT: int = 8000
    APP_SECRET_KEY: str = "change-me-in-production"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # System Database (PostgreSQL 16 -- meta + metrics + vector)
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
    # Spec: FS-AI-LLM-001 — unified provider selection
    AI_PROVIDER: Literal["ollama", "openai", "anthropic", "google"] = "ollama"
    AI_MODEL: str = "mistral:7b"  # Default model for the selected provider
    AI_MODE: Literal["online", "offline"] = (
        "online"  # Legacy compat: online→first cloud, offline→ollama
    )
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"  # Legacy compat (prefer AI_MODEL)
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral:7b"  # Legacy compat (prefer AI_MODEL)

    # Embedding
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSIONS: int = 384

    # Notifications — Slack Bot Token API (preferred) or Webhook URL (legacy)
    SLACK_BOT_TOKEN: str = ""  # xoxb-... Bot User OAuth Token
    SLACK_CHANNEL_ID: str = ""  # C0APZRZ4Y7M etc.
    SLACK_WEBHOOK_URL: str = ""  # Legacy: Incoming Webhook URL
    SLACK_ALERT_COOLDOWN_MINUTES: int = 30

    # SSO / External Auth (Spec: FS-ADMIN-002)
    SSO_ENABLED: bool = False
    OIDC_ISSUER_URL: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""
    LDAP_SERVER_URL: str = ""
    LDAP_BIND_DN: str = ""
    LDAP_BIND_PASSWORD: str = ""
    LDAP_USER_SEARCH_BASE: str = ""
    LDAP_USER_SEARCH_FILTER: str = "(uid={username})"
    API_KEY_HEADER: str = "X-API-Key"

    # Credential Encryption (ADR-007)
    CREDENTIAL_ENCRYPTION_KEY: str = Field(
        default="change-me-32-byte-key-for-fernet",
        description="Fernet encryption key for target DB credentials",
    )

    @model_validator(mode="after")
    def _reject_default_secrets_in_production(self) -> "Settings":
        """Prevent startup with placeholder secrets in production/staging."""
        if self.APP_ENV in ("production", "staging"):
            sentinel = "change-me"
            violations: list[str] = []
            if sentinel in self.APP_SECRET_KEY:
                violations.append("APP_SECRET_KEY")
            if sentinel in self.JWT_SECRET_KEY:
                violations.append("JWT_SECRET_KEY")
            if sentinel in self.CREDENTIAL_ENCRYPTION_KEY:
                violations.append("CREDENTIAL_ENCRYPTION_KEY")
            if violations:
                raise ValueError(
                    f"Insecure default secrets detected in {self.APP_ENV} mode: "
                    f"{', '.join(violations)}. "
                    "Set proper secret values via environment variables or .env file."
                )
        return self

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

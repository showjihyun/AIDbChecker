# Spec: CFG-001
"""Tests for CFG-001 Acceptance Criteria (Settings Configuration).

AC-1: Settings loads from env vars
AC-2: Production rejects default secrets
AC-3: APP_ENV validates allowed values
AC-4: settings singleton is importable and usable with FastAPI Depends

IMPORTANT: Do NOT delete the @spec_ref decorator -- it enables AC tracking in CI.
"""

import pytest
from pydantic import ValidationError

from tests.conftest import spec_ref


@spec_ref("CFG-001", "AC-1")
async def test_cfg_001_ac1_settings_loads_from_env(monkeypatch):
    """CFG-001 AC-1: Settings() loads values from environment variables.

    Verifies that environment variables override default values in the
    Settings class, simulating what happens when .env is loaded.
    """
    # Set env vars that override defaults
    monkeypatch.setenv("APP_NAME", "TestNeuralDB")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_PORT", "9000")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@db:5432/testdb")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key")
    monkeypatch.setenv("AI_MODE", "offline")

    # Import fresh Settings to pick up env vars
    from app.config import Settings

    s = Settings(
        _env_file=None,  # Don't read .env file during test
    )

    assert s.APP_NAME == "TestNeuralDB"
    assert s.APP_ENV == "development"
    assert s.APP_PORT == 9000
    assert "test:test@db:5432" in str(s.DATABASE_URL)
    assert s.JWT_SECRET_KEY == "test-jwt-secret-key"
    assert s.AI_MODE == "offline"


@spec_ref("CFG-001", "AC-2")
async def test_cfg_001_ac2_production_rejects_default_secrets(monkeypatch):
    """CFG-001 AC-2: Production mode raises ValidationError for default secrets.

    The _reject_default_secrets_in_production validator must block startup
    when APP_ENV=production and secrets still contain 'change-me'.
    """
    monkeypatch.setenv("APP_ENV", "production")
    # Leave default secret values (containing 'change-me')

    from app.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    # Should mention the offending fields
    error_text = str(exc_info.value)
    assert "APP_SECRET_KEY" in error_text or "JWT_SECRET_KEY" in error_text or "CREDENTIAL_ENCRYPTION_KEY" in error_text


@spec_ref("CFG-001", "AC-2")
async def test_cfg_001_ac2_staging_also_rejects_defaults(monkeypatch):
    """CFG-001 AC-2: Staging mode also rejects default secrets."""
    monkeypatch.setenv("APP_ENV", "staging")

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@spec_ref("CFG-001", "AC-2")
async def test_cfg_001_ac2_development_allows_defaults(monkeypatch):
    """CFG-001 AC-2: Development mode allows default secrets (for local dev)."""
    monkeypatch.setenv("APP_ENV", "development")

    from app.config import Settings

    # Should NOT raise -- development mode permits placeholder secrets
    s = Settings(_env_file=None)
    assert s.APP_ENV == "development"
    assert "change-me" in s.APP_SECRET_KEY  # default is present and allowed


@spec_ref("CFG-001", "AC-3")
async def test_cfg_001_ac3_app_env_rejects_invalid(monkeypatch):
    """CFG-001 AC-3: APP_ENV only accepts development|staging|production."""
    monkeypatch.setenv("APP_ENV", "testing")

    from app.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    # The Literal type should reject 'testing'
    error_text = str(exc_info.value)
    assert "APP_ENV" in error_text or "testing" in error_text


@spec_ref("CFG-001", "AC-3")
async def test_cfg_001_ac3_app_env_accepts_valid_values(monkeypatch):
    """CFG-001 AC-3: APP_ENV accepts all three valid environments."""
    from app.config import Settings

    # Secrets that do NOT contain the sentinel substring 'change-me'
    safe_secret = "a-properly-set-production-secret-value-2026"
    safe_jwt = "jwt-properly-set-production-secret-2026"
    safe_enc = "fernet-properly-set-encryption-key-2026"

    for env in ("development", "staging", "production"):
        monkeypatch.setenv("APP_ENV", env)
        if env in ("staging", "production"):
            # Must set proper secrets that do NOT contain 'change-me'
            monkeypatch.setenv("APP_SECRET_KEY", safe_secret)
            monkeypatch.setenv("JWT_SECRET_KEY", safe_jwt)
            monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", safe_enc)
        else:
            # Reset to defaults for development
            monkeypatch.delenv("APP_SECRET_KEY", raising=False)
            monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
            monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY", raising=False)

        s = Settings(_env_file=None)
        assert s.APP_ENV == env


@spec_ref("CFG-001", "AC-4")
async def test_cfg_001_ac4_settings_singleton_importable():
    """CFG-001 AC-4: settings singleton is importable and usable in FastAPI Depends.

    Verifies that `from app.config import settings` returns a valid
    Settings instance that can be injected into route handlers.
    """
    from app.config import settings

    # Must be a Settings instance (not None, not a class)
    from app.config import Settings

    assert isinstance(settings, Settings)
    assert settings.APP_NAME == "NeuralDB"
    assert settings.JWT_ALGORITHM == "HS256"

    # Verify it has the expected default values for JWT config
    assert settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS == 7

    # Verify AI_MODE is a valid Literal value
    assert settings.AI_MODE in ("online", "offline")

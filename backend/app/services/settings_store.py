# Spec: FS-AI-LLM-001
"""Persistent settings store — DB-backed key-value for runtime config.

Loads settings from DB on startup and syncs in-memory settings singleton.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting

logger = structlog.get_logger(__name__)

# Keys that map to settings attributes
_LLM_KEYS = {
    "ai_provider": "AI_PROVIDER",
    "ai_model": "AI_MODEL",
    "openai_api_key": "OPENAI_API_KEY",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "google_api_key": "GOOGLE_API_KEY",
    "ollama_base_url": "OLLAMA_BASE_URL",
    "slack_bot_token": "SLACK_BOT_TOKEN",
    "slack_channel_id": "SLACK_CHANNEL_ID",
    "slack_webhook_url": "SLACK_WEBHOOK_URL",
}


async def save_setting(session: AsyncSession, key: str, value: str) -> None:
    """Upsert a setting into the DB."""
    stmt = select(SystemSetting).where(SystemSetting.key == key)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.value = value
    else:
        session.add(SystemSetting(key=key, value=value))


async def load_llm_settings(session: AsyncSession) -> dict[str, str]:
    """Load all LLM-related settings from DB.

    Returns dict of {key: value} for found settings.
    """
    keys = list(_LLM_KEYS.keys())
    stmt = select(SystemSetting).where(SystemSetting.key.in_(keys))
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return {row.key: row.value for row in rows}


async def apply_llm_settings_from_db(session: AsyncSession) -> None:
    """Load LLM settings from DB and apply to in-memory settings singleton.

    Called on app startup to restore persisted configuration.
    """
    from app.config import settings

    stored = await load_llm_settings(session)
    applied = 0

    for db_key, attr_name in _LLM_KEYS.items():
        if db_key in stored and stored[db_key]:
            setattr(settings, attr_name, stored[db_key])
            applied += 1

    if applied:
        logger.info(
            "settings_store.applied",
            count=applied,
            provider=settings.AI_PROVIDER,
            model=settings.AI_MODEL,
        )

# Spec: FS-AI-LLM-001
"""LLM Settings API — manage AI provider, model, and API keys.

All endpoints require super_admin role.
API keys are NEVER exposed in responses (only has_*_key booleans).
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_role
from app.config import settings
from app.schemas.llm_settings import (
    LLMSettingsResponse,
    LLMSettingsUpdate,
    LLMTestRequest,
    LLMTestResponse,
    OllamaModel,
    ProviderInfo,
)
from app.services.llm_provider import get_llm_manager

logger = structlog.get_logger(__name__)

router = APIRouter()

# Spec: FS-AI-LLM-001 — all settings endpoints require super_admin
_admin_dep = Depends(require_role("super_admin"))


@router.get(
    "/settings/llm",
    response_model=LLMSettingsResponse,
    dependencies=[_admin_dep],
)
async def get_llm_settings() -> LLMSettingsResponse:
    """Return current LLM configuration.

    API keys are never exposed — only boolean flags indicating whether they are set.
    """
    return LLMSettingsResponse(
        provider=settings.AI_PROVIDER,
        model=settings.AI_MODEL,
        ollama_base_url=settings.OLLAMA_BASE_URL,
        has_openai_key=bool(settings.OPENAI_API_KEY),
        has_anthropic_key=bool(settings.ANTHROPIC_API_KEY),
        has_google_key=bool(settings.GOOGLE_API_KEY),
    )


@router.put(
    "/settings/llm",
    response_model=LLMSettingsResponse,
    dependencies=[_admin_dep],
)
async def update_llm_settings(
    body: LLMSettingsUpdate,
    session: AsyncSession = Depends(get_session),
) -> LLMSettingsResponse:
    """Update LLM provider, model, or API keys.

    Only fields that are provided (non-None) are updated.
    Changes are applied in-memory AND persisted to DB so they survive restarts.
    API keys are validated but never returned in the response.
    """
    from app.services.settings_store import save_setting

    # Spec: FS-AI-LLM-001 — partial update: apply in-memory + persist to DB
    if body.provider is not None:
        settings.AI_PROVIDER = body.provider
        await save_setting(session, "ai_provider", body.provider)
    if body.model is not None:
        settings.AI_MODEL = body.model
        await save_setting(session, "ai_model", body.model)
    if body.openai_api_key is not None:
        settings.OPENAI_API_KEY = body.openai_api_key
        await save_setting(session, "openai_api_key", body.openai_api_key)
    if body.anthropic_api_key is not None:
        settings.ANTHROPIC_API_KEY = body.anthropic_api_key
        await save_setting(session, "anthropic_api_key", body.anthropic_api_key)
    if body.google_api_key is not None:
        settings.GOOGLE_API_KEY = body.google_api_key
        await save_setting(session, "google_api_key", body.google_api_key)
    if body.ollama_base_url is not None:
        settings.OLLAMA_BASE_URL = body.ollama_base_url
        await save_setting(session, "ollama_base_url", body.ollama_base_url)

    await session.commit()

    logger.info(
        "llm_settings.updated",
        provider=settings.AI_PROVIDER,
        model=settings.AI_MODEL,
        persisted=True,
    )

    return LLMSettingsResponse(
        provider=settings.AI_PROVIDER,
        model=settings.AI_MODEL,
        ollama_base_url=settings.OLLAMA_BASE_URL,
        has_openai_key=bool(settings.OPENAI_API_KEY),
        has_anthropic_key=bool(settings.ANTHROPIC_API_KEY),
        has_google_key=bool(settings.GOOGLE_API_KEY),
    )


@router.get(
    "/settings/llm/providers",
    response_model=list[ProviderInfo],
    dependencies=[_admin_dep],
)
async def list_providers() -> list[ProviderInfo]:
    """Return all LLM providers with availability status.

    Spec: FS-AI-LLM-001 — AC-5: unavailable providers have available=false.
    """
    manager = get_llm_manager()
    return manager.list_providers()


@router.get(
    "/settings/llm/ollama-models",
    response_model=list[OllamaModel],
    dependencies=[_admin_dep],
)
async def list_ollama_models() -> list[OllamaModel]:
    """Query Ollama for locally available models.

    Returns empty list if Ollama is unreachable (no error raised).
    Spec: FS-AI-LLM-001 — AC-3.
    """
    manager = get_llm_manager()
    return await manager.list_ollama_models()


@router.post(
    "/settings/llm/test",
    response_model=LLMTestResponse,
    dependencies=[_admin_dep],
)
async def test_llm(body: LLMTestRequest) -> LLMTestResponse:
    """Test a specific provider+model by sending a simple prompt.

    Returns success/failure with latency and error details.
    Spec: FS-AI-LLM-001 — AC-7.
    """
    manager = get_llm_manager()
    result = await manager.test_llm(body.provider, body.model)

    return LLMTestResponse(
        success=result["success"],
        provider=body.provider,
        model=body.model,
        response_text=result.get("response_text", ""),
        error=result.get("error", ""),
        latency_ms=result.get("latency_ms", 0),
    )

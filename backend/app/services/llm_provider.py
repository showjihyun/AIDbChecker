# Spec: FS-AI-LLM-001
"""Unified LLM Provider Manager — single abstraction for all LLM calls.

Supports 4 providers:
  - Ollama (offline, local)
  - OpenAI (online, cloud)
  - Anthropic Claude (online, cloud)
  - Google Gemini (online, cloud)

All LLM imports are wrapped in try/except for graceful degradation when
a provider package is not installed.
"""

from __future__ import annotations

import time
from functools import lru_cache

import httpx
import structlog

from app.config import settings
from app.schemas.llm_settings import OllamaModel, ProviderInfo

logger = structlog.get_logger(__name__)

# Spec: FS-AI-LLM-001 Section 5 — known models per cloud provider
_OPENAI_MODELS = ["gpt-5.4", "gpt-4o", "gpt-4o-mini"]
_ANTHROPIC_MODELS = ["claude-opus-4-6", "claude-sonnet-4-6", "claude-sonnet-4-20250514"]
_GOOGLE_MODELS = ["gemini-3.1-pro", "gemini-2.0-flash", "gemini-1.5-pro"]

# Provider display names
_DISPLAY_NAMES = {
    "ollama": "Ollama (Local)",
    "openai": "OpenAI",
    "anthropic": "Anthropic Claude",
    "google": "Google Gemini",
}


class LLMProviderManager:
    """Unified LLM provider factory.

    Spec: FS-AI-LLM-001 Section 3.1
    """

    def get_llm(
        self,
        provider: str | None = None,
        model: str | None = None,
        *,
        temperature: float = 0.1,
        max_tokens: int = 1500,
        request_timeout: int = 30,
    ):
        """Get a LangChain BaseChatModel instance.

        Falls back to settings.AI_PROVIDER / settings.AI_MODEL if not specified.
        If the requested provider is unavailable, attempts fallback to next
        available provider.

        Returns:
            A LangChain BaseChatModel instance.

        Raises:
            RuntimeError: If no provider is available.
        """
        resolved_provider = provider or settings.AI_PROVIDER
        resolved_model = model or settings.AI_MODEL

        # Spec: FS-AI-LLM-001 — fallback chain
        fallback_order = [resolved_provider] + [
            p for p in ["ollama", "openai", "anthropic", "google"] if p != resolved_provider
        ]

        last_error: Exception | None = None
        for prov in fallback_order:
            try:
                llm = self._create_llm(
                    prov,
                    resolved_model if prov == resolved_provider else self._default_model(prov),
                    temperature=temperature,
                    max_tokens=max_tokens,
                    request_timeout=request_timeout,
                )
                if llm is not None:
                    return llm
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "llm_provider.fallback",
                    provider=prov,
                    error=str(exc),
                )
                continue

        raise RuntimeError(
            f"No LLM provider available. Last error: {last_error}. "
            "Configure at least one provider (Ollama running or cloud API key set)."
        )

    def _create_llm(
        self,
        provider: str,
        model: str,
        *,
        temperature: float,
        max_tokens: int,
        request_timeout: int,
    ):
        """Create a LangChain chat model for the given provider.

        Returns None if the provider package is not installed or API key is missing.
        """
        if provider == "ollama":
            return self._create_ollama(model, temperature, max_tokens)
        elif provider == "openai":
            return self._create_openai(model, temperature, max_tokens, request_timeout)
        elif provider == "anthropic":
            return self._create_anthropic(model, temperature, max_tokens, request_timeout)
        elif provider == "google":
            return self._create_google(model, temperature, max_tokens, request_timeout)
        else:
            raise ValueError(
                f"Unknown LLM provider: '{provider}'. Supported: ollama, openai, anthropic, google."
            )

    def _create_ollama(self, model: str, temperature: float, max_tokens: int):
        """Create Ollama ChatModel via langchain-community."""
        try:
            from langchain_community.chat_models import ChatOllama
        except ImportError:
            logger.debug("llm_provider.ollama_not_installed")
            return None

        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=model,
            temperature=temperature,
            num_predict=max_tokens,
        )

    def _create_openai(self, model: str, temperature: float, max_tokens: int, timeout: int):
        """Create OpenAI ChatModel."""
        if not settings.OPENAI_API_KEY:
            return None
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            logger.debug("llm_provider.openai_not_installed")
            return None

        return ChatOpenAI(
            model=model,
            api_key=settings.OPENAI_API_KEY,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout,
        )

    def _create_anthropic(self, model: str, temperature: float, max_tokens: int, timeout: int):
        """Create Anthropic Claude ChatModel."""
        if not settings.ANTHROPIC_API_KEY:
            return None
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            logger.debug("llm_provider.anthropic_not_installed")
            return None

        return ChatAnthropic(
            model=model,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=float(timeout),
        )

    def _create_google(self, model: str, temperature: float, max_tokens: int, timeout: int):
        """Create Google Gemini ChatModel."""
        if not settings.GOOGLE_API_KEY:
            return None
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            logger.debug("llm_provider.google_not_installed")
            return None

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=temperature,
            max_output_tokens=max_tokens,
            timeout=timeout,
        )

    def _default_model(self, provider: str) -> str:
        """Return the default model for a given provider."""
        defaults = {
            "ollama": settings.OLLAMA_MODEL,
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4-20250514",
            "google": "gemini-2.0-flash",
        }
        return defaults.get(provider, "unknown")

    async def list_ollama_models(self) -> list[OllamaModel]:
        """Query Ollama API for available local models.

        Spec: FS-AI-LLM-001 Section 3.1 — GET http://{OLLAMA_BASE_URL}/api/tags
        """
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            models: list[OllamaModel] = []
            for m in data.get("models", []):
                size_bytes = m.get("size", 0)
                size_str = f"{size_bytes / (1024**3):.1f} GB" if size_bytes else "unknown"
                models.append(
                    OllamaModel(
                        name=m.get("name", "unknown"),
                        size=size_str,
                        modified_at=m.get("modified_at", ""),
                    )
                )
            return models
        except httpx.ConnectError:
            logger.warning("llm_provider.ollama_unreachable", url=url)
            return []
        except Exception as exc:
            logger.warning("llm_provider.ollama_list_failed", error=str(exc))
            return []

    def list_providers(self) -> list[ProviderInfo]:
        """Return all configured providers with availability status.

        Spec: FS-AI-LLM-001 Section 3.1
        """
        providers: list[ProviderInfo] = []

        # Ollama — available if package is importable (actual reachability checked separately)
        ollama_available = False
        try:
            from langchain_community.chat_models import ChatOllama  # noqa: F401

            ollama_available = True
        except ImportError:
            pass

        providers.append(
            ProviderInfo(
                name="ollama",
                display_name=_DISPLAY_NAMES["ollama"],
                available=ollama_available,
                models=[],  # Populated dynamically via list_ollama_models()
            )
        )

        # OpenAI
        openai_available = False
        if settings.OPENAI_API_KEY:
            try:
                from langchain_openai import ChatOpenAI  # noqa: F401

                openai_available = True
            except ImportError:
                pass
        providers.append(
            ProviderInfo(
                name="openai",
                display_name=_DISPLAY_NAMES["openai"],
                available=openai_available,
                models=_OPENAI_MODELS if openai_available else [],
            )
        )

        # Anthropic
        anthropic_available = False
        if settings.ANTHROPIC_API_KEY:
            try:
                from langchain_anthropic import ChatAnthropic  # noqa: F401

                anthropic_available = True
            except ImportError:
                pass
        providers.append(
            ProviderInfo(
                name="anthropic",
                display_name=_DISPLAY_NAMES["anthropic"],
                available=anthropic_available,
                models=_ANTHROPIC_MODELS if anthropic_available else [],
            )
        )

        # Google
        google_available = False
        if settings.GOOGLE_API_KEY:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: F401

                google_available = True
            except ImportError:
                pass
        providers.append(
            ProviderInfo(
                name="google",
                display_name=_DISPLAY_NAMES["google"],
                available=google_available,
                models=_GOOGLE_MODELS if google_available else [],
            )
        )

        return providers

    async def test_llm(self, provider: str, model: str) -> dict:
        """Send a simple "Hello" message to verify provider+model works.

        Returns dict with keys: success, response_text, error, latency_ms.
        """
        from langchain_core.messages import HumanMessage

        start = time.monotonic()
        try:
            llm = self._create_llm(
                provider,
                model,
                temperature=0.0,
                max_tokens=50,
                request_timeout=15,
            )
            if llm is None:
                return {
                    "success": False,
                    "response_text": "",
                    "error": (
                        f"Provider '{provider}' is not available. "
                        "Check that the package is installed and API key is configured."
                    ),
                    "latency_ms": 0,
                }

            response = await llm.ainvoke([HumanMessage(content="Hello, respond with OK.")])
            elapsed_ms = int((time.monotonic() - start) * 1000)
            text = response.content if hasattr(response, "content") else str(response)
            return {
                "success": True,
                "response_text": text[:200],
                "error": "",
                "latency_ms": elapsed_ms,
            }
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.warning(
                "llm_provider.test_failed",
                provider=provider,
                model=model,
                error=str(exc),
            )
            return {
                "success": False,
                "response_text": "",
                "error": str(exc)[:500],
                "latency_ms": elapsed_ms,
            }


# Spec: FS-AI-LLM-001 — singleton pattern
@lru_cache(maxsize=1)
def get_llm_manager() -> LLMProviderManager:
    """Return the singleton LLMProviderManager instance."""
    return LLMProviderManager()

# Spec: FS-DBA-001 Tier 2 — J3: Agent Retry + Fallback
"""LLM call retry with exponential backoff and fallback model.

새벽 3시 장애 대응에서 Agent가 LLM 호출 실패로 멈추면 안 됨.
Retry (max 2) → Fallback model → Safe mode (규칙 기반 응답).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def retry_llm_call(
    func: Callable[..., Coroutine[Any, Any, Any]],
    *args: Any,
    max_retries: int = 2,
    backoff_base: float = 1.0,
    fallback_func: Callable[..., Coroutine[Any, Any, Any]] | None = None,
    safe_mode_response: Any = None,
    **kwargs: Any,
) -> Any:
    """Execute an LLM call with retry, fallback, and safe mode.

    Strategy:
    1. Try primary call (up to max_retries)
    2. If all retries fail and fallback_func provided → try fallback
    3. If fallback also fails → return safe_mode_response

    Args:
        func: Primary async function to call.
        max_retries: Max retry attempts (default 2).
        backoff_base: Base seconds for exponential backoff.
        fallback_func: Alternative function (e.g., different LLM model).
        safe_mode_response: Static response if everything fails.
        *args, **kwargs: Passed to func.

    Returns:
        Result from func, fallback_func, or safe_mode_response.
    """
    last_error = None

    # Phase 1: Retry primary
    for attempt in range(max_retries + 1):
        try:
            start = time.monotonic()
            result = await func(*args, **kwargs)
            elapsed = int((time.monotonic() - start) * 1000)
            if attempt > 0:
                logger.info(
                    "llm_retry.recovered",
                    attempt=attempt + 1,
                    elapsed_ms=elapsed,
                )
            return result
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                wait = backoff_base * (2**attempt)
                logger.warning(
                    "llm_retry.retrying",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    wait_seconds=wait,
                    error=str(exc)[:100],
                )
                await asyncio.sleep(wait)
            else:
                logger.error(
                    "llm_retry.exhausted",
                    attempts=max_retries + 1,
                    error=str(exc)[:200],
                )

    # Phase 2: Fallback model
    if fallback_func is not None:
        try:
            logger.info("llm_retry.fallback_attempt")
            result = await fallback_func(*args, **kwargs)
            logger.info("llm_retry.fallback_success")
            return result
        except Exception as exc:
            logger.error(
                "llm_retry.fallback_failed",
                error=str(exc)[:200],
            )

    # Phase 3: Safe mode
    if safe_mode_response is not None:
        logger.warning("llm_retry.safe_mode")
        return safe_mode_response

    # Nothing worked — re-raise last error
    raise last_error  # type: ignore[misc]


class LLMRetryConfig:
    """Configuration for retry behavior per agent type."""

    def __init__(
        self,
        max_retries: int = 2,
        backoff_base: float = 1.0,
        timeout_seconds: int = 30,
    ):
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout_seconds = timeout_seconds

    # Presets
    @classmethod
    def for_tuning(cls) -> LLMRetryConfig:
        """Tuning agent: moderate retry, patient."""
        return cls(max_retries=2, backoff_base=1.5, timeout_seconds=30)

    @classmethod
    def for_copilot(cls) -> LLMRetryConfig:
        """Copilot agent: more retries, critical path."""
        return cls(max_retries=3, backoff_base=1.0, timeout_seconds=45)

    @classmethod
    def for_nl2sql(cls) -> LLMRetryConfig:
        """NL2SQL: fast retry, user-facing."""
        return cls(max_retries=1, backoff_base=0.5, timeout_seconds=15)

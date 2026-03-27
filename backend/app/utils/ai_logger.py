# Spec: FS-ADMIN-004
"""AI Decision Log — decorator and helper to auto-log AI/LLM decisions to audit_logs.

Every AI call (MTL RCA, NL2SQL, RAG search, anomaly detection) is logged
as action="ai_decision" with structured details in the JSONB column.

Usage:
    @log_ai_decision("mtl_rca")
    async def mtl_lite_predict(context, *, session): ...

The decorated function MUST accept a `session` keyword argument (AsyncSession)
so the logger can write to audit_logs in the same transaction.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def create_ai_decision_log(
    session: AsyncSession,
    *,
    resource_type: str,
    resource_id: str | None = None,
    user_id: str | None = None,
    details: dict[str, Any],
) -> None:
    """Write an AI decision entry to audit_logs.

    Spec: FS-ADMIN-004 — uses existing audit_logs table with action="ai_decision".
    """
    try:
        import json

        await session.execute(
            text("""
                INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
                VALUES (
                    gen_random_uuid(),
                    CAST(:user_id AS uuid),
                    'ai_decision',
                    :resource_type,
                    CAST(:resource_id AS uuid),
                    CAST(:details AS jsonb)
                )
            """),
            {
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": json.dumps(details, default=str),
            },
        )
        await session.flush()
    except Exception as exc:
        # Never let logging failure break the main flow
        logger.error(
            "ai_logger.write_failed",
            resource_type=resource_type,
            error=str(exc),
        )


def truncate_prompt(prompt: str, max_len: int = 200) -> str:
    """Spec: FS-ADMIN-004 §4.2 — prompt summary 200 chars max."""
    if len(prompt) <= max_len:
        return prompt
    return prompt[: max_len - 3] + "..."


def log_ai_decision(resource_type: str):
    """Decorator to auto-log AI calls to audit_logs.

    Spec: FS-ADMIN-004 §4.1 — decorator pattern.
    Wraps an async function, records timing/tokens/confidence automatically.

    The decorated function MAY return an object with these attributes:
      - confidence (float)
      - tokens_used / total_tokens (int)
      - ai_model (str)

    Usage:
        @log_ai_decision("mtl_rca")
        async def predict(session, *, context): ...
    """
    import functools
    import time as _time

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = _time.monotonic()
            session = kwargs.get("session") or (args[0] if args else None)
            error_msg = None
            result = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as exc:
                error_msg = str(exc)
                raise
            finally:
                elapsed_ms = int((_time.monotonic() - start) * 1000)

                # Extract metadata from result if available
                confidence = None
                tokens = None
                model_name = "unknown"

                if result is not None:
                    confidence = getattr(result, "confidence", None)
                    tokens = getattr(result, "tokens_used", None) or getattr(
                        result, "total_tokens", None
                    )
                    model_name = getattr(result, "ai_model", None) or "unknown"

                details = build_ai_details(
                    ai_model=model_name,
                    inference_time_ms=elapsed_ms,
                    decision="completed" if error_msg is None else "failed",
                    confidence=confidence,
                    total_tokens=tokens,
                    error=error_msg,
                )

                if session is not None and hasattr(session, "execute"):
                    try:
                        await create_ai_decision_log(
                            session,
                            resource_type=resource_type,
                            details=details,
                        )
                    except Exception:
                        logger.debug("ai_logger.decorator_write_skipped")

        return wrapper

    return decorator


def build_ai_details(
    *,
    ai_model: str,
    inference_time_ms: int,
    decision: str,
    confidence: float | None = None,
    prompt_summary: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    reasoning_summary: str | None = None,
    input_summary: dict | None = None,
    output_summary: dict | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build structured AI decision details for audit_logs.details JSONB.

    Spec: FS-ADMIN-004 §3 — AIDecisionDetails schema.
    """
    from app.config import settings

    details: dict[str, Any] = {
        "ai_model": ai_model,
        "ai_mode": "offline" if settings.AI_PROVIDER == "ollama" else "online",
        "inference_time_ms": inference_time_ms,
        "decision": decision,
    }
    if confidence is not None:
        details["confidence"] = round(confidence, 4)
    if prompt_summary:
        details["prompt_summary"] = truncate_prompt(prompt_summary)
    if prompt_tokens is not None:
        details["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        details["completion_tokens"] = completion_tokens
    if total_tokens is not None:
        details["total_tokens"] = total_tokens
    if reasoning_summary:
        details["reasoning_summary"] = reasoning_summary
    if input_summary:
        details["input_summary"] = input_summary
    if output_summary:
        details["output_summary"] = output_summary
    if error:
        details["error"] = error
    return details

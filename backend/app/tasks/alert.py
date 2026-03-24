# Spec: MVP-ALERT-001, MVP-ALERT-002
"""Celery tasks for sending alert notifications.

Handles Slack webhook delivery with retry on 429 rate-limit responses.
Uses httpx for async HTTP calls.
"""

import asyncio
import time

import httpx
import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)

_MAX_RETRIES = 3
_RATE_LIMIT_BACKOFF_SECONDS = 1.0


async def _send_webhook(webhook_url: str, payload: dict) -> tuple[bool, str]:
    """POST JSON payload to a webhook URL with retry on 429.

    Returns (success, message).
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await client.post(webhook_url, json=payload)

                if response.status_code == 200:
                    return (True, "OK")

                if response.status_code == 429:
                    # Rate limited — back off and retry
                    retry_after = float(
                        response.headers.get("Retry-After", _RATE_LIMIT_BACKOFF_SECONDS)
                    )
                    logger.warning(
                        "alert.rate_limited",
                        attempt=attempt,
                        retry_after=retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                if 400 <= response.status_code < 500:
                    # Client error — do not retry
                    msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error("alert.client_error", status=response.status_code, body=response.text[:200])
                    return (False, msg)

                # Server error — retry
                logger.warning(
                    "alert.server_error",
                    attempt=attempt,
                    status=response.status_code,
                )

            except httpx.TimeoutException:
                logger.warning("alert.timeout", attempt=attempt)
            except httpx.ConnectError as exc:
                logger.warning("alert.connect_error", attempt=attempt, error=str(exc))

    return (False, f"Failed after {_MAX_RETRIES} attempts")


@shared_task(
    name="app.tasks.alert.send_slack_alert",
    soft_time_limit=30,
    acks_late=True,
    ignore_result=True,
)
def send_slack_alert(webhook_url: str, message_payload: dict) -> None:
    """Send a Slack alert via webhook.

    Args:
        webhook_url: Decrypted Slack incoming webhook URL.
        message_payload: Slack message payload ({"text": "..."} or blocks format).
    """
    loop = asyncio.new_event_loop()
    try:
        success, message = loop.run_until_complete(
            _send_webhook(webhook_url, message_payload)
        )
        if success:
            logger.info("alert.slack_sent")
        else:
            logger.error("alert.slack_failed", message=message)
    finally:
        loop.close()

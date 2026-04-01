# Spec: FS-AI-REPORT-001, FR-ALERT-001
"""Unified Slack messaging service — Bot Token API (preferred) or Webhook (legacy).

Bot Token API uses chat.postMessage with channel ID.
Webhook uses Incoming Webhook URL (channel fixed at webhook creation).

Priority: Bot Token > Webhook > skip (no-op).
"""

from __future__ import annotations

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Slack API endpoint
_SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"


async def send_slack_message(
    text: str,
    channel: str | None = None,
    *,
    blocks: list[dict] | None = None,
) -> bool:
    """Send a message to Slack.

    Uses Bot Token API if SLACK_BOT_TOKEN is set, otherwise falls back to Webhook.
    Returns True if sent successfully, False otherwise.
    """
    target_channel = channel or settings.SLACK_CHANNEL_ID

    # Priority 1: Bot Token + chat.postMessage
    if settings.SLACK_BOT_TOKEN:
        return await _send_via_bot_token(text, target_channel, blocks)

    # Priority 2: Webhook URL (legacy)
    if settings.SLACK_WEBHOOK_URL:
        return await _send_via_webhook(text)

    logger.debug("slack.no_config", msg="No Slack token or webhook configured")
    return False


async def _send_via_bot_token(
    text: str,
    channel: str,
    blocks: list[dict] | None = None,
) -> bool:
    """Send via Slack Bot Token API (chat.postMessage)."""
    import httpx

    if not channel:
        logger.warning("slack.no_channel", msg="SLACK_CHANNEL_ID not set")
        return False

    payload: dict = {
        "channel": channel,
        "text": text,
    }
    if blocks:
        payload["blocks"] = blocks

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                _SLACK_POST_MESSAGE_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json",
                },
            )
            data = resp.json()

            if data.get("ok"):
                logger.info("slack.sent", channel=channel, method="bot_token")
                return True

            logger.warning(
                "slack.api_error",
                error=data.get("error", "unknown"),
                channel=channel,
            )
            return False

    except Exception as exc:
        logger.warning("slack.send_failed", error=str(exc), method="bot_token")
        return False


async def _send_via_webhook(text: str) -> bool:
    """Send via Slack Incoming Webhook (legacy)."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                settings.SLACK_WEBHOOK_URL,
                json={"text": text},
            )
            if resp.status_code == 200:
                logger.info("slack.sent", method="webhook")
                return True

            logger.warning("slack.webhook_failed", status=resp.status_code)
            return False

    except Exception as exc:
        logger.warning("slack.send_failed", error=str(exc), method="webhook")
        return False

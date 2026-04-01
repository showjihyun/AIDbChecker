# Spec: FS-ALERT-002
"""Slack Integration Settings API — configure Bot Token + Channel ID."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_role
from app.config import settings

logger = structlog.get_logger(__name__)
router = APIRouter()

_admin_dep = Depends(require_role("super_admin", "db_admin"))


class SlackSettingsResponse(BaseModel):
    has_bot_token: bool
    channel_id: str
    has_webhook_url: bool


class SlackSettingsUpdate(BaseModel):
    bot_token: str | None = None
    channel_id: str | None = None
    webhook_url: str | None = None


class SlackTestResponse(BaseModel):
    success: bool
    error: str = ""


@router.get("/settings/slack", response_model=SlackSettingsResponse, dependencies=[_admin_dep])
async def get_slack_settings() -> SlackSettingsResponse:
    """AC-1: Return current Slack config (token masked)."""
    return SlackSettingsResponse(
        has_bot_token=bool(settings.SLACK_BOT_TOKEN),
        channel_id=settings.SLACK_CHANNEL_ID or "",
        has_webhook_url=bool(settings.SLACK_WEBHOOK_URL),
    )


@router.put("/settings/slack", response_model=SlackSettingsResponse, dependencies=[_admin_dep])
async def update_slack_settings(
    body: SlackSettingsUpdate,
    session: AsyncSession = Depends(get_session),
) -> SlackSettingsResponse:
    """AC-2: Save Slack settings (in-memory + DB persistent)."""
    from app.services.settings_store import save_setting

    if body.bot_token is not None:
        settings.SLACK_BOT_TOKEN = body.bot_token
        await save_setting(session, "slack_bot_token", body.bot_token)
    if body.channel_id is not None:
        settings.SLACK_CHANNEL_ID = body.channel_id
        await save_setting(session, "slack_channel_id", body.channel_id)
    if body.webhook_url is not None:
        settings.SLACK_WEBHOOK_URL = body.webhook_url
        await save_setting(session, "slack_webhook_url", body.webhook_url)

    await session.commit()

    logger.info("slack_settings.updated", channel=settings.SLACK_CHANNEL_ID)

    return SlackSettingsResponse(
        has_bot_token=bool(settings.SLACK_BOT_TOKEN),
        channel_id=settings.SLACK_CHANNEL_ID or "",
        has_webhook_url=bool(settings.SLACK_WEBHOOK_URL),
    )


@router.post("/settings/slack/test", response_model=SlackTestResponse, dependencies=[_admin_dep])
async def test_slack() -> SlackTestResponse:
    """AC-3: Send test message to configured Slack channel."""
    from app.services.slack import send_slack_message

    msg = "NeuralDB Slack 연동 테스트 메시지입니다. 이 메시지가 보이면 설정이 정상입니다."
    ok = await send_slack_message(msg)

    if ok:
        return SlackTestResponse(success=True)
    return SlackTestResponse(
        success=False,
        error="Slack 발송 실패. Bot Token, Channel ID를 확인하세요. Bot이 채널에 초대되어 있는지 확인하세요.",
    )

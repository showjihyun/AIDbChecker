# Spec: DM-001, MVP-ALERT-001
"""Alert channels API — manage Slack/Webhook notification channels."""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.alert_channel import AlertChannel
from app.utils.encryption import encrypt_value

logger = structlog.get_logger(__name__)

router = APIRouter()


# --- Schemas (co-located for small domain) ---


class AlertChannelCreate(BaseModel):
    """Request to create a new alert channel."""

    name: str = Field(..., max_length=255, description='Channel display name, e.g. "#db-alerts"')
    channel_type: str = Field(
        ..., pattern=r"^(slack|email|webhook|pagerduty)$"
    )
    config: dict = Field(
        ..., description="Channel-specific settings: {webhook_url} for slack/webhook"
    )
    severity_filter: list[str] = Field(
        default=["critical", "warning"],
        description="Severities to receive",
    )


class AlertChannelResponse(BaseModel):
    """Response for a single alert channel."""

    id: UUID
    name: str
    channel_type: str
    severity_filter: list[str]
    is_active: bool
    last_test_at: datetime | None = None
    last_test_result: bool | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertChannelListResponse(BaseModel):
    items: list[AlertChannelResponse]
    total: int


class AlertTestRequest(BaseModel):
    """Request to send a test alert."""

    channel_id: UUID


class AlertTestResponse(BaseModel):
    success: bool
    message: str


# --- Routes ---


@router.get("/alerts/channels", response_model=AlertChannelListResponse)
async def list_channels(
    session: AsyncSession = Depends(get_session),
) -> AlertChannelListResponse:
    """List all active (non-deleted) alert channels."""
    stmt = (
        select(AlertChannel)
        .where(AlertChannel.deleted_at.is_(None))
        .order_by(AlertChannel.name)
    )
    result = await session.execute(stmt)
    channels = list(result.scalars().all())

    return AlertChannelListResponse(
        items=[_to_response(ch) for ch in channels],
        total=len(channels),
    )


@router.post(
    "/alerts/channels",
    response_model=AlertChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    body: AlertChannelCreate,
    session: AsyncSession = Depends(get_session),
) -> AlertChannelResponse:
    """Create a new alert notification channel."""
    # Spec: ADR-007 — encrypt sensitive config fields
    encrypted_config: dict = {}
    sensitive_keys = {"webhook_url", "api_key", "smtp_password", "routing_key"}
    for key, value in body.config.items():
        if key in sensitive_keys:
            encrypted_config[key] = encrypt_value(str(value))
        else:
            encrypted_config[key] = value

    channel = AlertChannel(
        name=body.name,
        channel_type=body.channel_type,
        config=encrypted_config,
        severity_filter=body.severity_filter,
    )

    session.add(channel)
    await session.commit()
    await session.refresh(channel)

    logger.info("alert_channel.created", channel_id=str(channel.id), name=channel.name)
    return _to_response(channel)


@router.post("/alerts/test", response_model=AlertTestResponse)
async def test_alert(
    body: AlertTestRequest,
    session: AsyncSession = Depends(get_session),
) -> AlertTestResponse:
    """Send a test alert to verify channel configuration."""
    stmt = select(AlertChannel).where(
        AlertChannel.id == body.channel_id,
        AlertChannel.deleted_at.is_(None),
    )
    channel = (await session.execute(stmt)).scalar_one_or_none()
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert channel {body.channel_id} not found. Check available channels via GET /alerts/channels.",
        )

    # Import task here to avoid circular import at module level
    from app.tasks.alert import send_slack_alert
    from app.utils.encryption import decrypt_value as _decrypt

    config = channel.config or {}
    now = datetime.now(timezone.utc)

    if channel.channel_type in ("slack", "webhook"):
        webhook_url_enc = config.get("webhook_url", "")
        if not webhook_url_enc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Channel config missing 'webhook_url'. Update the channel configuration.",
            )

        webhook_url = _decrypt(webhook_url_enc)
        payload = {
            "text": f"[NeuralDB Test Alert] Channel '{channel.name}' is working. Sent at {now.isoformat()}."
        }

        # Fire async Celery task
        send_slack_alert.delay(webhook_url, payload)

        # Update test metadata
        channel.last_test_at = now
        channel.last_test_result = True  # optimistic; actual result logged by task
        await session.commit()

        return AlertTestResponse(success=True, message="Test alert dispatched to Celery worker.")
    else:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Test alert for channel type '{channel.channel_type}' is not implemented in MVP. "
            "Supported: slack, webhook.",
        )


def _to_response(channel: AlertChannel) -> AlertChannelResponse:
    """Convert ORM model to response (strips encrypted config)."""
    return AlertChannelResponse(
        id=channel.id,
        name=channel.name,
        channel_type=channel.channel_type,
        severity_filter=channel.severity_filter,
        is_active=channel.is_active,
        last_test_at=channel.last_test_at,
        last_test_result=channel.last_test_result,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )

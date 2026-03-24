# Spec: MVP-DASH-005, FR-SELF-001
"""System health API — check DB, Valkey, Celery component status."""

import structlog
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.config import settings
from app.db.session import system_engine

logger = structlog.get_logger(__name__)

router = APIRouter()


class HealthStatus(BaseModel):
    """Component health status response."""

    db: str  # "up" / "down"
    valkey: str  # "up" / "down"
    celery: str  # "up" / "down"
    status: str  # "healthy" / "degraded" / "unhealthy"


@router.get("/system/health", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """Check connectivity to PostgreSQL (system DB), Valkey, and Celery.

    Returns overall status:
    - healthy: all components up
    - degraded: some components down
    - unhealthy: critical components (db) down
    """
    db_status = await _check_db()
    valkey_status = await _check_valkey()
    celery_status = await _check_celery()

    components = {"db": db_status, "valkey": valkey_status, "celery": celery_status}

    if all(v == "up" for v in components.values()):
        overall = "healthy"
    elif db_status == "down":
        overall = "unhealthy"
    else:
        overall = "degraded"

    return HealthStatus(
        db=db_status,
        valkey=valkey_status,
        celery=celery_status,
        status=overall,
    )


async def _check_db() -> str:
    """Check system PostgreSQL via SELECT 1."""
    try:
        async with system_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "up"
    except Exception:
        logger.warning("health.db_down")
        return "down"


async def _check_valkey() -> str:
    """Check Valkey connectivity via PING."""
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.VALKEY_URL, socket_timeout=3)
        try:
            pong = await client.ping()
            return "up" if pong else "down"
        finally:
            await client.aclose()
    except Exception:
        logger.warning("health.valkey_down")
        return "down"


async def _check_celery() -> str:
    """Check Celery by inspecting active workers via Valkey-backed control."""
    try:
        from app.tasks import celery_app

        # Celery inspect is synchronous; use ping with a short timeout
        inspector = celery_app.control.inspect(timeout=2)
        ping_result = inspector.ping()
        if ping_result:
            return "up"
        return "down"
    except Exception:
        logger.warning("health.celery_down")
        return "down"

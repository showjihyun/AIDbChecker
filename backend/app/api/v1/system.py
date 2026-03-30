# Spec: MVP-DASH-005, FR-SELF-001, FS-SELF-001
"""System health API — check DB, Valkey, Celery component status."""

import time
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.config import settings
from app.db.session import system_engine

logger = structlog.get_logger(__name__)

router = APIRouter()

# Track process start time for uptime calculation
_PROCESS_START = time.monotonic()


class HealthStatus(BaseModel):
    """Component health status response."""

    db: str  # "up" / "down"
    valkey: str  # "up" / "down"
    celery: str  # "up" / "down"
    status: str  # "healthy" / "degraded" / "unhealthy"


class ComponentHealthDetail(BaseModel):
    """Spec: FS-SELF-001 §3.2 — per-component health detail."""

    status: str  # "up" / "down"
    latency_ms: int | None = None
    details: dict | None = None
    last_checked_at: datetime


class HealthDetail(BaseModel):
    """Spec: FS-SELF-001 §3.2 — detailed health response."""

    status: str  # "healthy" / "degraded" / "unhealthy"
    uptime_seconds: int
    version: str
    components: dict[str, ComponentHealthDetail]


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


@router.get("/system/health/detail", response_model=HealthDetail)
async def health_detail() -> HealthDetail:
    """Spec: FS-SELF-001 AC-6 — detailed health with uptime, version, latencies."""

    now = datetime.now(UTC)
    db_status, db_ms = await _check_db_detail()
    valkey_status, valkey_ms = await _check_valkey_detail()
    celery_status, celery_ms, celery_details = await _check_celery_detail()

    components_map = {"db": db_status, "valkey": valkey_status, "celery": celery_status}
    if all(v == "up" for v in components_map.values()):
        overall = "healthy"
    elif db_status == "down":
        overall = "unhealthy"
    else:
        overall = "degraded"

    return HealthDetail(
        status=overall,
        uptime_seconds=int(time.monotonic() - _PROCESS_START),
        version=_read_version(),
        components={
            "db": ComponentHealthDetail(
                status=db_status,
                latency_ms=db_ms,
                last_checked_at=now,
            ),
            "valkey": ComponentHealthDetail(
                status=valkey_status,
                latency_ms=valkey_ms,
                last_checked_at=now,
            ),
            "celery": ComponentHealthDetail(
                status=celery_status,
                latency_ms=celery_ms,
                details=celery_details,
                last_checked_at=now,
            ),
        },
    )


def _read_version() -> str:
    """Read VERSION file from project root."""
    try:
        from pathlib import Path

        vf = Path(__file__).resolve().parents[3] / "VERSION"
        return vf.read_text().strip() if vf.exists() else "unknown"
    except Exception:
        return "unknown"


async def _check_db() -> str:
    """Check system PostgreSQL via SELECT 1."""
    status, _ = await _check_db_detail()
    return status


async def _check_db_detail() -> tuple[str, int | None]:
    """Check system PostgreSQL with latency measurement."""
    try:
        start = time.monotonic()
        async with system_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        ms = int((time.monotonic() - start) * 1000)
        return "up", ms
    except Exception:
        logger.warning("health.db_down")
        return "down", None


async def _check_valkey() -> str:
    """Check Valkey connectivity via PING."""
    status, _ = await _check_valkey_detail()
    return status


async def _check_valkey_detail() -> tuple[str, int | None]:
    """Check Valkey with latency measurement."""
    try:
        import redis.asyncio as aioredis

        start = time.monotonic()
        client = aioredis.from_url(settings.VALKEY_URL, socket_timeout=3)
        try:
            pong = await client.ping()
            ms = int((time.monotonic() - start) * 1000)
            return ("up" if pong else "down"), ms
        finally:
            await client.aclose()
    except Exception:
        logger.warning("health.valkey_down")
        return "down", None


async def _check_celery() -> str:
    """Check Celery worker availability."""
    status, _, _ = await _check_celery_detail()
    return status


async def _check_celery_detail() -> tuple[str, int | None, dict | None]:
    """Check Celery with latency and worker count.

    AC-7: Fallback to active_queues check when ping fails (--pool solo busy workers
    don't respond to ping while processing tasks).
    """
    try:
        import asyncio

        from app.tasks import celery_app

        def _sync_ping() -> dict | None:
            inspector = celery_app.control.inspect(timeout=2)
            result = inspector.ping()
            if result:
                return result
            # Fallback: check active queues (works even when workers are busy)
            queues = inspector.active_queues()
            if queues:
                return {k: {"ok": "queue_active"} for k in queues}
            return None

        start = time.monotonic()
        loop = asyncio.get_running_loop()
        ping_result = await loop.run_in_executor(None, _sync_ping)
        ms = int((time.monotonic() - start) * 1000)

        if ping_result:
            return "up", ms, {"worker_count": len(ping_result)}
        return "down", ms, None
    except Exception:
        logger.warning("health.celery_down")
        return "down", None, None

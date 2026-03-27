# Spec: MVP-AI-002, MVP-AI-003
"""AnomalyDetector -- check hot metrics against baselines and create incidents.

Severity thresholds (sigma-based):
  >3 sigma  = critical
  >2 sigma  = warning
  >1.5 sigma = notice

Cooldown: Valkey key tracks last incident per (instance_id, metric_type).
  Default 30 minutes -- prevents duplicate incidents for the same metric.

Resilience: If no baseline exists, skip silently. If Valkey is unreachable,
  fall back to in-memory cache (best-effort deduplication).
"""

import time
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzers.baseline import HOT_METRIC_KEYS, BaselineAnalyzer, _extract_metric_value
from app.db.session import AsyncSessionLocal
from app.models.incident import Incident

logger = structlog.get_logger(__name__)

# Cooldown: 30 minutes between incidents for the same (instance, metric_type)
INCIDENT_COOLDOWN_SECONDS = 30 * 60

# In-memory fallback when Valkey is unreachable.
# Maps "instance_id:metric_type" -> last_incident_unix_timestamp
_cooldown_fallback: dict[str, float] = {}


async def _get_valkey_client():
    """Lazy-init Valkey async client. Returns None if unavailable."""
    try:
        import redis.asyncio as aioredis

        from app.config import settings

        client = aioredis.from_url(settings.VALKEY_URL, socket_timeout=2)
        await client.ping()
        return client
    except Exception:
        return None


def _cooldown_key(instance_id: UUID, metric_type: str) -> str:
    """Valkey key for incident cooldown tracking."""
    return f"neuraldb:incident_cooldown:{instance_id}:{metric_type}"


async def _is_in_cooldown(instance_id: UUID, metric_type: str) -> bool:
    """Check if an incident for this (instance, metric) is in cooldown.

    Uses Valkey with TTL. Falls back to in-memory dict if Valkey is down.
    """
    key = _cooldown_key(instance_id, metric_type)
    now = time.time()

    client = await _get_valkey_client()
    if client is not None:
        try:
            val = await client.get(key)
            await client.aclose()
            return val is not None
        except Exception:
            pass

    # Fallback: in-memory
    last_ts = _cooldown_fallback.get(f"{instance_id}:{metric_type}")
    return bool(last_ts is not None and now - last_ts < INCIDENT_COOLDOWN_SECONDS)


async def _set_cooldown(instance_id: UUID, metric_type: str) -> None:
    """Mark cooldown start for an (instance, metric_type) pair."""
    key = _cooldown_key(instance_id, metric_type)
    now = time.time()

    client = await _get_valkey_client()
    if client is not None:
        try:
            await client.setex(key, INCIDENT_COOLDOWN_SECONDS, "1")
            await client.aclose()
            return
        except Exception:
            pass

    # Fallback: in-memory
    _cooldown_fallback[f"{instance_id}:{metric_type}"] = now


class AnomalyDetector:
    """Check metric samples against baselines and create incidents on anomaly.

    Resilient: skips silently when baselines are missing or Valkey is down.
    """

    def __init__(self) -> None:
        self._analyzer = BaselineAnalyzer()

    async def check(
        self,
        instance_id: UUID,
        metric_sample: dict,
        sampled_at: datetime | None = None,
    ) -> list[Incident]:
        """Check all hot metrics in a sample against baselines.

        Args:
            instance_id: The DB instance UUID.
            metric_sample: The JSONB metrics dict from MetricSample.
            sampled_at: Timestamp of the sample (for time bucket classification).

        Returns:
            List of newly created Incident records (may be empty).
        """
        if sampled_at is None:
            sampled_at = datetime.now(UTC)

        created_incidents: list[Incident] = []

        async with AsyncSessionLocal() as session:
            for metric_type in HOT_METRIC_KEYS:
                value = _extract_metric_value(metric_sample, metric_type)
                if value is None:
                    continue

                try:
                    incident = await self._check_single_metric(
                        session=session,
                        instance_id=instance_id,
                        metric_type=metric_type,
                        value=value,
                        sampled_at=sampled_at,
                    )
                    if incident is not None:
                        created_incidents.append(incident)
                except Exception as exc:
                    # Silent skip -- never let one metric check block others
                    logger.warning(
                        "anomaly.check_error",
                        instance_id=str(instance_id),
                        metric_type=metric_type,
                        error=str(exc),
                    )

            if created_incidents:
                await session.commit()

        return created_incidents

    async def _check_single_metric(
        self,
        *,
        session: AsyncSession,
        instance_id: UUID,
        metric_type: str,
        value: float,
        sampled_at: datetime,
    ) -> Incident | None:
        """Check a single metric value against its baseline.

        Returns an Incident if anomaly detected and not in cooldown, else None.
        """
        z_score, severity = await self._analyzer.detect_anomaly(
            instance_id=instance_id,
            metric_type=metric_type,
            current_value=value,
            at_time=sampled_at,
            session=session,
        )

        if severity is None:
            return None

        # Cooldown check -- avoid duplicate incidents
        if await _is_in_cooldown(instance_id, metric_type):
            logger.debug(
                "anomaly.cooldown_active",
                instance_id=str(instance_id),
                metric_type=metric_type,
                severity=severity,
                z_score=round(z_score, 2),
            )
            return None

        # Get baseline for description context
        baseline = await self._analyzer.get_baseline(
            instance_id, metric_type, sampled_at, session=session
        )
        baseline_mean = baseline.mean if baseline else 0.0
        baseline_min = baseline.normal_min if baseline else 0.0
        baseline_max = baseline.normal_max if baseline else 0.0

        title = f"AI Baseline Alert: {metric_type} anomaly detected ({severity.upper()})"
        description = (
            f"Metric '{metric_type}' value {value:.2f} is {z_score:.1f} sigma "
            f"from baseline mean {baseline_mean:.2f} "
            f"(normal range: {baseline_min:.2f} - {baseline_max:.2f}). "
            f"Detected at {sampled_at.isoformat()}."
        )

        incident = Incident(
            instance_id=instance_id,
            severity=severity,
            status="open",
            title=title,
            description=description,
            source="ai_baseline",
            metric_type=metric_type,
            metric_value=value,
            baseline_value=baseline_mean,
            detected_at=sampled_at,
            metadata_={
                "z_score": round(z_score, 3),
                "baseline_normal_min": baseline_min,
                "baseline_normal_max": baseline_max,
                "baseline_stddev": baseline.stddev if baseline else 0.0,
            },
        )
        session.add(incident)

        # Set cooldown to prevent duplicate incidents
        await _set_cooldown(instance_id, metric_type)

        logger.info(
            "anomaly.incident_created",
            instance_id=str(instance_id),
            metric_type=metric_type,
            severity=severity,
            z_score=round(z_score, 2),
            value=value,
            baseline_mean=baseline_mean,
        )

        return incident

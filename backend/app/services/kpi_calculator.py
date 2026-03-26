# Spec: FS-KPI-001
"""KPI Calculator — derives 12 DB performance indicators from collected metrics.

Delta-based KPIs (TPS, QPS, Hit Ratio, IOPS, Deadlocks) use the last 2 hot
metric_samples to compute per-second rates.

Live-query KPIs (Active Sessions, Lock Waits, Slow Queries, Connection Usage)
are fetched directly from the target DB via the adapter when the KPI endpoint
is called, since these are point-in-time snapshot values not stored in
metric_samples.

Storage KPIs (DB Size, Replication Lag) use the latest cold metric_samples.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.postgresql.remote import PostgreSQLRemoteAdapter
from app.models.metric import MetricSample
from app.schemas.kpi import (
    ConnectionKPI,
    KPIAdvisory,
    KPIResponse,
    KPIValue,
    LockKPI,
    ResourceKPI,
    StorageKPI,
    ThroughputKPI,
)

logger = structlog.get_logger(__name__)


# Spec: FS-KPI-001 Section 2 — threshold definitions
# Format: (warning_threshold, critical_threshold)
# For "higher is worse" metrics (default direction)
_THRESHOLDS_UPPER = {
    "tps": (5000, 10000),
    "qps": (50000, 100000),
    "avg_response_time_ms": (100, 500),
    "slow_queries": (5, 20),
    "disk_iops": (1000, 5000),
    "active_sessions": (50, 100),
    "connection_usage_pct": (80, 95),
    "lock_waits": (5, 20),
    "deadlocks_per_sec": (0.1, 1.0),
    "replication_lag_sec": (10, 60),
}

# For "lower is worse" metrics (inverted: value < threshold = bad)
_THRESHOLDS_LOWER = {
    "buffer_hit_ratio": (95, 90),  # warn: <95%, crit: <90%
}


def _evaluate_status(
    metric_name: str, value: float | int | None
) -> str:
    """Determine KPI status based on spec-defined thresholds.

    Returns "normal", "warning", "critical", or "unknown".
    """
    if value is None:
        return "unknown"

    # Lower-is-worse metrics (inverted thresholds)
    if metric_name in _THRESHOLDS_LOWER:
        warn, crit = _THRESHOLDS_LOWER[metric_name]
        if value < crit:
            return "critical"
        if value < warn:
            return "warning"
        return "normal"

    # Upper-is-worse metrics (standard thresholds)
    if metric_name in _THRESHOLDS_UPPER:
        warn, crit = _THRESHOLDS_UPPER[metric_name]
        if value >= crit:
            return "critical"
        if value >= warn:
            return "warning"
        return "normal"

    return "normal"


def _make_kpi(
    metric_name: str, value: float | int | None, unit: str
) -> KPIValue:
    """Create a KPIValue with auto-evaluated status."""
    return KPIValue(
        value=value,
        unit=unit,
        status=_evaluate_status(metric_name, value),
    )


class KPICalculator:
    """Compute all 12 KPI values for a DB instance.

    Spec: FS-KPI-001 Section 5.2

    Uses:
    - Last 2 hot metric_samples for delta/s calculations
    - Latest cold metric_samples for storage KPIs
    - Live adapter queries for point-in-time session/lock metrics
    """

    @staticmethod
    def compute_delta_rate(
        current: int | float, previous: int | float, interval_sec: float
    ) -> float:
        """Compute per-second rate from cumulative counter delta.

        Spec: FS-KPI-001 Section 5.2
        Handles counter wraps by clamping to 0.
        """
        if interval_sec <= 0:
            return 0.0
        return max(0.0, (current - previous) / interval_sec)

    @staticmethod
    def compute_hit_ratio(
        delta_hit: int | float, delta_read: int | float
    ) -> float:
        """Buffer cache hit ratio from delta values.

        Spec: FS-KPI-001 Section 2.2 (KPI-05)
        When no I/O has occurred (total=0), returns 100.0 (all from cache).
        """
        total = delta_hit + delta_read
        if total <= 0:
            return 100.0
        return round((delta_hit / total) * 100, 2)

    @staticmethod
    async def _fetch_last_two_hot(
        session: AsyncSession, instance_id: UUID
    ) -> list[MetricSample]:
        """Fetch the 2 most recent hot metric_samples for delta calculation."""
        stmt = (
            select(MetricSample)
            .where(
                MetricSample.instance_id == instance_id,
                MetricSample.category == "hot",
            )
            .order_by(desc(MetricSample.sampled_at))
            .limit(2)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def _fetch_latest_cold(
        session: AsyncSession, instance_id: UUID
    ) -> MetricSample | None:
        """Fetch the latest cold metric_sample for storage KPIs."""
        stmt = (
            select(MetricSample)
            .where(
                MetricSample.instance_id == instance_id,
                MetricSample.category == "cold",
            )
            .order_by(desc(MetricSample.sampled_at))
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def _fetch_latest_warm(
        session: AsyncSession, instance_id: UUID
    ) -> MetricSample | None:
        """Fetch the latest warm metric_sample for avg response time."""
        stmt = (
            select(MetricSample)
            .where(
                MetricSample.instance_id == instance_id,
                MetricSample.category == "warm",
            )
            .order_by(desc(MetricSample.sampled_at))
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def compute_all_kpi(
        cls,
        instance_id: UUID,
        session: AsyncSession,
        adapter: PostgreSQLRemoteAdapter | None = None,
    ) -> KPIResponse:
        """Compute all 12 KPI values for an instance.

        Spec: FS-KPI-001

        Args:
            instance_id: Target DB instance UUID.
            session: System DB async session for reading metric_samples.
            adapter: Optional live adapter for point-in-time queries.
                     If None, live KPIs return unknown status.

        Returns:
            KPIResponse with all 5 categories populated.
        """
        now = datetime.now(timezone.utc)

        # --- Delta-based KPIs from stored hot metrics ---
        hot_samples = await cls._fetch_last_two_hot(session, instance_id)
        tps_val: float | None = None
        qps_val: float | None = None
        hit_ratio_val: float | None = None
        iops_val: float | None = None
        deadlocks_val: float | None = None

        if len(hot_samples) >= 2:
            current = hot_samples[0]  # most recent
            previous = hot_samples[1]  # second most recent
            interval = (
                current.sampled_at - previous.sampled_at
            ).total_seconds()

            if interval > 0:
                cm = current.metrics
                pm = previous.metrics

                # KPI-01: TPS (xact_commit delta/s)
                if "xact_commit" in cm and "xact_commit" in pm:
                    tps_val = round(
                        cls.compute_delta_rate(
                            cm["xact_commit"], pm["xact_commit"], interval
                        ),
                        2,
                    )

                # KPI-02: QPS (tup_returned delta/s)
                if "tup_returned" in cm and "tup_returned" in pm:
                    qps_val = round(
                        cls.compute_delta_rate(
                            cm["tup_returned"], pm["tup_returned"], interval
                        ),
                        2,
                    )

                # KPI-05: Buffer Hit Ratio (delta-based)
                if all(
                    k in cm and k in pm for k in ("blks_hit", "blks_read")
                ):
                    delta_hit = cm["blks_hit"] - pm["blks_hit"]
                    delta_read = cm["blks_read"] - pm["blks_read"]
                    hit_ratio_val = cls.compute_hit_ratio(delta_hit, delta_read)

                # KPI-06: Disk IOPS (blks_read delta/s)
                if "blks_read" in cm and "blks_read" in pm:
                    iops_val = round(
                        cls.compute_delta_rate(
                            cm["blks_read"], pm["blks_read"], interval
                        ),
                        2,
                    )

                # KPI-10: Deadlocks (delta/s) — from pg_stat_database
                if "deadlocks" in cm and "deadlocks" in pm:
                    deadlocks_val = round(
                        cls.compute_delta_rate(
                            cm["deadlocks"], pm["deadlocks"], interval
                        ),
                        4,
                    )

        # --- Storage KPIs from latest cold metrics ---
        cold_sample = await cls._fetch_latest_cold(session, instance_id)
        db_size_val: int | None = None
        replication_lag_val: float | None = None

        if cold_sample is not None:
            cm = cold_sample.metrics
            # KPI-11: DB Size
            db_size_val = cm.get("database_size_bytes")

            # KPI-12: Replication Lag (max across all replicas)
            replication = cm.get("replication", [])
            if replication:
                lags = [
                    r["replay_lag_seconds"]
                    for r in replication
                    if r.get("replay_lag_seconds") is not None
                ]
                if lags:
                    replication_lag_val = round(max(lags), 3)

        # --- Avg Response Time from warm metrics ---
        # KPI-03: pg_stat_statements mean_exec_time is in warm tables data
        # Since warm stores table stats, we get avg_response_time via live query
        avg_rt_val: float | None = None

        # --- Live KPIs from target DB adapter ---
        slow_queries_val: int | None = None
        active_sessions_val: int | None = None
        connection_usage_val: float | None = None
        lock_waits_val: int | None = None

        if adapter is not None:
            live_data = await cls._collect_live_kpis(adapter)
            if live_data is not None:
                slow_queries_val = live_data.get("slow_query_count")
                active_sessions_val = live_data.get("active_sessions")
                lock_waits_val = live_data.get("lock_waits")
                avg_rt_val = live_data.get("avg_response_time_ms")

                # KPI-08: Connection Usage %
                numbackends = live_data.get("numbackends")
                max_connections = live_data.get("max_connections")
                if numbackends is not None and max_connections and max_connections > 0:
                    connection_usage_val = round(
                        (numbackends / max_connections) * 100, 1
                    )

                # KPI-10: If no delta data, try getting deadlocks from live
                if deadlocks_val is None and "deadlocks" in live_data:
                    # Cannot compute delta from a single live value;
                    # leave as None
                    pass

        # --- Collect advisories ---
        advisories: list[KPIAdvisory] = []

        # Advisory: pg_stat_statements not installed (avg_response_time is None)
        if avg_rt_val is None and adapter is not None:
            advisories.append(
                KPIAdvisory(
                    level="warning",
                    title="pg_stat_statements 미설치",
                    message=(
                        "Avg Response Time, Top Slow Queries 등 "
                        "쿼리 성능 분석에 필요한 확장이 설치되어 있지 않습니다."
                    ),
                    action="CREATE EXTENSION IF NOT EXISTS pg_stat_statements;",
                )
            )

        # Advisory: Replication not configured
        if replication_lag_val is None:
            advisories.append(
                KPIAdvisory(
                    level="info",
                    title="Replication 미구성",
                    message=(
                        "이 인스턴스에 Replication이 구성되어 있지 않습니다. "
                        "단일 인스턴스 모드입니다."
                    ),
                    action=None,
                )
            )

        # --- Assemble response ---
        return KPIResponse(
            instance_id=instance_id,
            timestamp=now,
            throughput=ThroughputKPI(
                tps=_make_kpi("tps", tps_val, "tx/s"),
                qps=_make_kpi("qps", qps_val, "q/s"),
                avg_response_time_ms=_make_kpi(
                    "avg_response_time_ms", avg_rt_val, "ms"
                ),
                slow_queries=_make_kpi("slow_queries", slow_queries_val, "count"),
            ),
            resource=ResourceKPI(
                buffer_hit_ratio=_make_kpi(
                    "buffer_hit_ratio", hit_ratio_val, "%"
                ),
                disk_iops=_make_kpi("disk_iops", iops_val, "ops/s"),
            ),
            connection=ConnectionKPI(
                active_sessions=_make_kpi(
                    "active_sessions", active_sessions_val, "count"
                ),
                connection_usage_pct=_make_kpi(
                    "connection_usage_pct", connection_usage_val, "%"
                ),
            ),
            lock=LockKPI(
                lock_waits=_make_kpi("lock_waits", lock_waits_val, "count"),
                deadlocks_per_sec=_make_kpi(
                    "deadlocks_per_sec", deadlocks_val, "count/s"
                ),
            ),
            storage=StorageKPI(
                db_size_bytes=_make_kpi("db_size_bytes", db_size_val, "bytes"),
                replication_lag_sec=_make_kpi(
                    "replication_lag_sec", replication_lag_val, "sec"
                ),
            ),
            advisories=advisories,
        )

    @staticmethod
    async def _collect_live_kpis(
        adapter: PostgreSQLRemoteAdapter,
    ) -> dict[str, Any] | None:
        """Query live KPI data directly from the target DB.

        Spec: FS-KPI-001 Section 5.1
        Queries: slow queries, active sessions, max_connections,
                 lock waits, avg response time.
        Returns None on failure (silent skip).
        """
        try:
            return await adapter.collect_kpi_extras()
        except Exception as exc:
            logger.warning(
                "kpi.live_query_failed",
                error=str(exc),
            )
            return None

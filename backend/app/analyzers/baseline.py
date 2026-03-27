# Spec: MVP-AI-001, MVP-AI-002
"""BaselineAnalyzer -- STL decomposition + Isolation Forest for auto-baselining.

Trains baselines per (instance_id, metric_type, time_bucket) and stores results
in the `baselines` table. Used by AnomalyDetector for dynamic threshold checks.

Time buckets:
  - weekday_business: Mon-Fri 09:00-18:00 (local or UTC)
  - weekday_night: Mon-Fri 18:00-09:00
  - weekend: Sat-Sun all day

Training pipeline (MVP-AI-001):
  1. Fetch 2+ weeks of hot metric_samples for (instance, metric_type)
  2. Classify samples by time_bucket
  3. STL decomposition (statsmodels) to extract residuals
  4. Isolation Forest (scikit-learn) to determine normal range boundaries
  5. Compute mean, stddev, normal_min, normal_max
  6. UPSERT into baselines table
"""

from datetime import UTC, datetime
from uuid import UUID

import numpy as np
import structlog
from sklearn.ensemble import IsolationForest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from statsmodels.tsa.seasonal import STL

from app.db.session import AsyncSessionLocal
from app.models.baseline import Baseline
from app.models.metric import MetricSample

logger = structlog.get_logger(__name__)

# Minimum number of samples required per time bucket to train a baseline.
# At 1-second hot resolution, 2 weeks of weekday_business (5 days * 9 hours * 3600)
# gives ~162,000 samples. We set a lower floor to allow earlier training.
MIN_SAMPLES_FOR_TRAINING = 100

# Hot metric keys we build baselines for.
# Spec: MVP-COLLECT-001 -- CPU, Memory, Active Connections, TPS, Buffer Hit Ratio
HOT_METRIC_KEYS = [
    "cpu_usage",
    "memory_usage",
    "active_connections",
    "tps",
    "buffer_hit_ratio",
]

# STL period: hourly seasonality in seconds (for 1-second data).
# Using 60 as a practical period for sub-sampled data.
STL_PERIOD = 60

# Isolation Forest contamination parameter: expected anomaly fraction.
# Spec: AG-001 -- anomaly_sensitivity: 0.95 => contamination=0.05
IF_CONTAMINATION = 0.05


def classify_time_bucket(dt: datetime) -> str:
    """Classify a datetime into a time bucket.

    Categories:
      - weekday_business: Mon-Fri 09:00-18:00
      - weekday_night: Mon-Fri outside business hours
      - weekend: Sat-Sun all day
    """
    weekday = dt.weekday()  # 0=Mon, 6=Sun
    if weekday >= 5:
        return "weekend"
    hour = dt.hour
    if 9 <= hour < 18:
        return "weekday_business"
    return "weekday_night"


class BaselineAnalyzer:
    """Train and query baselines for anomaly detection.

    Stateless: all data flows through the system DB.
    """

    async def train(
        self,
        instance_id: UUID,
        metric_type: str,
        *,
        session: AsyncSession | None = None,
    ) -> bool:
        """Train baselines for a single (instance, metric_type) across all time buckets.

        Returns True if at least one time bucket was trained successfully.
        """
        own_session = session is None
        if own_session:
            session = AsyncSessionLocal()

        try:
            # Fetch hot metric samples (last 14 days minimum, up to 30 days)
            from datetime import timedelta

            now = datetime.now(UTC)
            cutoff = now - timedelta(days=30)

            stmt = (
                select(MetricSample)
                .where(
                    MetricSample.instance_id == instance_id,
                    MetricSample.category == "hot",
                    MetricSample.sampled_at >= cutoff,
                )
                .order_by(MetricSample.sampled_at)
            )
            result = await session.execute(stmt)
            samples = list(result.scalars().all())

            if not samples:
                logger.info(
                    "baseline.no_samples",
                    instance_id=str(instance_id),
                    metric_type=metric_type,
                )
                return False

            # Group samples by time bucket
            buckets: dict[str, list[tuple[datetime, float]]] = {
                "weekday_business": [],
                "weekday_night": [],
                "weekend": [],
            }

            for sample in samples:
                bucket = classify_time_bucket(sample.sampled_at)
                value = _extract_metric_value(sample.metrics, metric_type)
                if value is not None:
                    buckets[bucket].append((sample.sampled_at, value))

            trained_any = False
            for bucket_name, data_points in buckets.items():
                if len(data_points) < MIN_SAMPLES_FOR_TRAINING:
                    logger.debug(
                        "baseline.insufficient_samples",
                        instance_id=str(instance_id),
                        metric_type=metric_type,
                        time_bucket=bucket_name,
                        count=len(data_points),
                        required=MIN_SAMPLES_FOR_TRAINING,
                    )
                    continue

                try:
                    baseline_data = _compute_baseline(data_points)
                    await _upsert_baseline(
                        session,
                        instance_id=instance_id,
                        metric_type=metric_type,
                        time_bucket=bucket_name,
                        baseline_data=baseline_data,
                        training_samples=len(data_points),
                    )
                    trained_any = True
                    logger.info(
                        "baseline.trained",
                        instance_id=str(instance_id),
                        metric_type=metric_type,
                        time_bucket=bucket_name,
                        samples=len(data_points),
                        mean=baseline_data["mean"],
                        stddev=baseline_data["stddev"],
                    )
                except Exception as exc:
                    logger.warning(
                        "baseline.train_error",
                        instance_id=str(instance_id),
                        metric_type=metric_type,
                        time_bucket=bucket_name,
                        error=str(exc),
                    )

            if trained_any:
                await session.commit()

            return trained_any

        finally:
            if own_session:
                await session.close()

    async def get_baseline(
        self,
        instance_id: UUID,
        metric_type: str,
        at_time: datetime | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> Baseline | None:
        """Fetch the active baseline for a (instance, metric_type) at a given time.

        Uses at_time to determine the time bucket. Defaults to now().
        Returns None if no baseline exists (anomaly detection should skip silently).
        """
        if at_time is None:
            at_time = datetime.now(UTC)

        time_bucket = classify_time_bucket(at_time)

        own_session = session is None
        if own_session:
            session = AsyncSessionLocal()

        try:
            stmt = select(Baseline).where(
                Baseline.instance_id == instance_id,
                Baseline.metric_type == metric_type,
                Baseline.time_bucket == time_bucket,
                Baseline.is_active.is_(True),
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        finally:
            if own_session:
                await session.close()

    async def detect_anomaly(
        self,
        instance_id: UUID,
        metric_type: str,
        current_value: float,
        at_time: datetime | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> tuple[float, str | None]:
        """Compare a metric value against the learned baseline.

        Returns (z_score, severity).
          - z_score: number of standard deviations from the mean
          - severity: "critical" (>3sigma), "warning" (>2sigma),
                      "notice" (>1.5sigma), or None (normal)

        If no baseline exists, returns (0.0, None) -- skip silently.
        """
        baseline = await self.get_baseline(instance_id, metric_type, at_time, session=session)
        if baseline is None or baseline.stddev == 0:
            return 0.0, None

        z_score = abs(current_value - baseline.mean) / baseline.stddev

        # Spec: MVP-AI-002 -- >3sigma = critical, >2sigma = warning, >1.5sigma = notice
        severity: str | None = None
        if z_score > 3.0:
            severity = "critical"
        elif z_score > 2.0:
            severity = "warning"
        elif z_score > 1.5:
            severity = "notice"

        return z_score, severity


def _extract_metric_value(metrics: dict, metric_type: str) -> float | None:
    """Safely extract a numeric metric value from the JSONB metrics dict."""
    val = metrics.get(metric_type)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _compute_baseline(
    data_points: list[tuple[datetime, float]],
) -> dict:
    """Compute baseline statistics using STL decomposition + Isolation Forest.

    STL decomposes the time series to extract the residual component.
    Isolation Forest then identifies normal vs anomalous points in the residuals.
    The normal range is derived from the inlier subset.

    Returns dict with keys: normal_min, normal_max, mean, stddev, model_params.
    """
    values = np.array([v for _, v in data_points], dtype=np.float64)

    # Sub-sample if we have too many points (STL on 100k+ is slow)
    max_stl_samples = 10_000
    if len(values) > max_stl_samples:
        indices = np.linspace(0, len(values) - 1, max_stl_samples, dtype=int)
        values_for_stl = values[indices]
    else:
        values_for_stl = values

    # STL decomposition -- extract residual
    try:
        period = min(STL_PERIOD, len(values_for_stl) // 2)
        if period < 2:
            period = 2
        stl = STL(values_for_stl, period=period, robust=True)
        stl_result = stl.fit()
        residuals = stl_result.resid
    except Exception:
        # Fallback: use raw values if STL fails (e.g. too few unique values)
        residuals = values_for_stl

    # Isolation Forest -- identify inliers in residuals
    residuals_2d = residuals.reshape(-1, 1)
    iso_forest = IsolationForest(
        contamination=IF_CONTAMINATION,
        random_state=42,
        n_estimators=100,
    )
    predictions = iso_forest.fit_predict(residuals_2d)

    # Use original values corresponding to inlier residuals
    if len(values_for_stl) == len(values):
        inlier_values = values[predictions == 1]
    else:
        # When sub-sampled, map inlier mask back
        inlier_values = values_for_stl[predictions == 1]

    if len(inlier_values) < 2:
        # Fallback: use all values if Isolation Forest is too aggressive
        inlier_values = values

    mean = float(np.mean(inlier_values))
    stddev = float(np.std(inlier_values))
    if stddev == 0:
        stddev = 1e-6  # Avoid division by zero

    normal_min = float(np.min(inlier_values))
    normal_max = float(np.max(inlier_values))

    return {
        "normal_min": normal_min,
        "normal_max": normal_max,
        "mean": mean,
        "stddev": stddev,
        "model_params": {
            "stl_period": STL_PERIOD,
            "if_contamination": IF_CONTAMINATION,
            "if_n_estimators": 100,
            "sub_sampled": len(values) > max_stl_samples,
        },
    }


async def _upsert_baseline(
    session: AsyncSession,
    *,
    instance_id: UUID,
    metric_type: str,
    time_bucket: str,
    baseline_data: dict,
    training_samples: int,
) -> None:
    """Insert or update a baseline record (UPSERT by unique constraint)."""
    now = datetime.now(UTC)

    stmt = select(Baseline).where(
        Baseline.instance_id == instance_id,
        Baseline.metric_type == metric_type,
        Baseline.time_bucket == time_bucket,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.normal_min = baseline_data["normal_min"]
        existing.normal_max = baseline_data["normal_max"]
        existing.mean = baseline_data["mean"]
        existing.stddev = baseline_data["stddev"]
        existing.model_params = baseline_data["model_params"]
        existing.model_type = "stl"
        existing.training_samples = training_samples
        existing.last_trained_at = now
        existing.is_active = True
    else:
        baseline = Baseline(
            instance_id=instance_id,
            metric_type=metric_type,
            time_bucket=time_bucket,
            normal_min=baseline_data["normal_min"],
            normal_max=baseline_data["normal_max"],
            mean=baseline_data["mean"],
            stddev=baseline_data["stddev"],
            model_type="stl",
            model_params=baseline_data["model_params"],
            training_samples=training_samples,
            last_trained_at=now,
            is_active=True,
        )
        session.add(baseline)

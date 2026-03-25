# Spec: MVP-AI-001, MVP-AI-002
"""Unit tests for BaselineAnalyzer — time bucket classification and anomaly detection.

Tests the classify_time_bucket pure function and the BaselineAnalyzer.detect_anomaly
method with mocked DB sessions to avoid external dependencies.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.analyzers.baseline import BaselineAnalyzer, classify_time_bucket


class TestClassifyTimeBucket:
    """Tests for classify_time_bucket pure function — no DB needed."""

    # Spec: MVP-AI-001 — weekday_business: Mon-Fri 09:00-18:00

    def test_time_bucket_weekday_business(self) -> None:
        """Mon-Fri 09:00-17:59 classifies as weekday_business."""
        # Wednesday 10:30 UTC
        dt = datetime(2026, 3, 25, 10, 30, 0, tzinfo=timezone.utc)
        assert dt.weekday() == 2  # Wednesday
        assert classify_time_bucket(dt) == "weekday_business"

        # Monday 09:00 — boundary start
        dt_start = datetime(2026, 3, 23, 9, 0, 0, tzinfo=timezone.utc)
        assert dt_start.weekday() == 0  # Monday
        assert classify_time_bucket(dt_start) == "weekday_business"

        # Friday 17:59 — boundary end
        dt_end = datetime(2026, 3, 27, 17, 59, 0, tzinfo=timezone.utc)
        assert dt_end.weekday() == 4  # Friday
        assert classify_time_bucket(dt_end) == "weekday_business"

    def test_time_bucket_weekday_night(self) -> None:
        """Mon-Fri outside 09-18 classifies as weekday_night."""
        # Tuesday 08:59 — just before business hours
        dt_before = datetime(2026, 3, 24, 8, 59, 0, tzinfo=timezone.utc)
        assert dt_before.weekday() == 1  # Tuesday
        assert classify_time_bucket(dt_before) == "weekday_night"

        # Thursday 18:00 — business hours end boundary
        dt_evening = datetime(2026, 3, 26, 18, 0, 0, tzinfo=timezone.utc)
        assert dt_evening.weekday() == 3  # Thursday
        assert classify_time_bucket(dt_evening) == "weekday_night"

        # Monday 00:00 — midnight
        dt_midnight = datetime(2026, 3, 23, 0, 0, 0, tzinfo=timezone.utc)
        assert dt_midnight.weekday() == 0  # Monday
        assert classify_time_bucket(dt_midnight) == "weekday_night"

        # Wednesday 23:30 — late night
        dt_late = datetime(2026, 3, 25, 23, 30, 0, tzinfo=timezone.utc)
        assert classify_time_bucket(dt_late) == "weekday_night"

    def test_time_bucket_weekend(self) -> None:
        """Saturday and Sunday classify as weekend regardless of hour."""
        # Saturday 10:00 (business hours but weekend)
        dt_sat = datetime(2026, 3, 28, 10, 0, 0, tzinfo=timezone.utc)
        assert dt_sat.weekday() == 5  # Saturday
        assert classify_time_bucket(dt_sat) == "weekend"

        # Sunday 02:00 (night hours, weekend)
        dt_sun = datetime(2026, 3, 29, 2, 0, 0, tzinfo=timezone.utc)
        assert dt_sun.weekday() == 6  # Sunday
        assert classify_time_bucket(dt_sun) == "weekend"

        # Saturday 23:59
        dt_sat_late = datetime(2026, 3, 28, 23, 59, 0, tzinfo=timezone.utc)
        assert classify_time_bucket(dt_sat_late) == "weekend"


class TestDetectAnomaly:
    """Tests for BaselineAnalyzer.detect_anomaly with mocked DB baseline lookup."""

    @pytest.mark.asyncio
    async def test_detect_anomaly_critical(self) -> None:
        """Value >3 sigma from mean returns 'critical' severity."""
        # Spec: MVP-AI-002 — >3sigma = critical
        analyzer = BaselineAnalyzer()
        mock_baseline = MagicMock()
        mock_baseline.mean = 50.0
        mock_baseline.stddev = 5.0

        with patch.object(
            analyzer, "get_baseline", new_callable=AsyncMock, return_value=mock_baseline
        ):
            instance_id = uuid4()
            # value = 66.0 => z_score = |66 - 50| / 5 = 3.2 > 3.0
            z_score, severity = await analyzer.detect_anomaly(
                instance_id, "cpu_usage", 66.0
            )

        assert z_score > 3.0
        assert severity == "critical"

    @pytest.mark.asyncio
    async def test_detect_anomaly_warning(self) -> None:
        """Value >2 sigma but <=3 sigma returns 'warning' severity."""
        # Spec: MVP-AI-002 — >2sigma = warning
        analyzer = BaselineAnalyzer()
        mock_baseline = MagicMock()
        mock_baseline.mean = 50.0
        mock_baseline.stddev = 5.0

        with patch.object(
            analyzer, "get_baseline", new_callable=AsyncMock, return_value=mock_baseline
        ):
            instance_id = uuid4()
            # value = 61.0 => z_score = |61 - 50| / 5 = 2.2 (between 2 and 3)
            z_score, severity = await analyzer.detect_anomaly(
                instance_id, "cpu_usage", 61.0
            )

        assert 2.0 < z_score <= 3.0
        assert severity == "warning"

    @pytest.mark.asyncio
    async def test_detect_anomaly_normal(self) -> None:
        """Value within 1.5 sigma returns None severity (normal)."""
        analyzer = BaselineAnalyzer()
        mock_baseline = MagicMock()
        mock_baseline.mean = 50.0
        mock_baseline.stddev = 5.0

        with patch.object(
            analyzer, "get_baseline", new_callable=AsyncMock, return_value=mock_baseline
        ):
            instance_id = uuid4()
            # value = 52.0 => z_score = |52 - 50| / 5 = 0.4 < 1.5
            z_score, severity = await analyzer.detect_anomaly(
                instance_id, "cpu_usage", 52.0
            )

        assert z_score < 1.5
        assert severity is None

    @pytest.mark.asyncio
    async def test_detect_anomaly_no_baseline(self) -> None:
        """No baseline exists: returns (0.0, None) without error."""
        analyzer = BaselineAnalyzer()

        with patch.object(
            analyzer, "get_baseline", new_callable=AsyncMock, return_value=None
        ):
            instance_id = uuid4()
            z_score, severity = await analyzer.detect_anomaly(
                instance_id, "cpu_usage", 99.0
            )

        assert z_score == 0.0
        assert severity is None

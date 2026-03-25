# Spec: MVP-AI-002, MVP-AI-003
"""Unit tests for AnomalyDetector — skip on missing baseline, cooldown dedup.

Mocks: BaselineAnalyzer, Valkey client, AsyncSessionLocal.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.analyzers.anomaly import AnomalyDetector, _is_in_cooldown, _set_cooldown


class TestAnomalyDetectorCheck:
    """Tests for AnomalyDetector.check with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_check_skips_when_no_baseline(self) -> None:
        """When no baseline exists, detect_anomaly returns (0.0, None) and
        check produces no incidents — no crash.
        """
        detector = AnomalyDetector()
        instance_id = uuid4()
        sample = {"cpu_usage": 95.0, "memory_usage": 80.0}
        now = datetime(2026, 3, 25, 10, 0, 0, tzinfo=timezone.utc)

        # Mock the analyzer to return no anomaly (no baseline)
        with patch.object(
            detector._analyzer,
            "detect_anomaly",
            new_callable=AsyncMock,
            return_value=(0.0, None),
        ), patch(
            "app.analyzers.anomaly.AsyncSessionLocal",
        ) as mock_session_cls:
            # Set up async context manager for the session
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            incidents = await detector.check(instance_id, sample, now)

        assert incidents == []

    @pytest.mark.asyncio
    async def test_cooldown_prevents_duplicate_incidents(self) -> None:
        """When cooldown is active for a metric, no new incident is created
        even if the anomaly is detected.
        """
        detector = AnomalyDetector()
        instance_id = uuid4()
        sample = {"cpu_usage": 99.0}
        now = datetime(2026, 3, 25, 10, 0, 0, tzinfo=timezone.utc)

        # Mock detect_anomaly to return a critical anomaly
        mock_baseline = MagicMock()
        mock_baseline.mean = 50.0
        mock_baseline.normal_min = 30.0
        mock_baseline.normal_max = 70.0
        mock_baseline.stddev = 5.0

        with patch.object(
            detector._analyzer,
            "detect_anomaly",
            new_callable=AsyncMock,
            return_value=(4.0, "critical"),
        ), patch.object(
            detector._analyzer,
            "get_baseline",
            new_callable=AsyncMock,
            return_value=mock_baseline,
        ), patch(
            "app.analyzers.anomaly._is_in_cooldown",
            new_callable=AsyncMock,
            return_value=True,  # Cooldown active
        ), patch(
            "app.analyzers.anomaly.AsyncSessionLocal",
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.add = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            incidents = await detector.check(instance_id, sample, now)

        # Cooldown prevents incident creation despite anomaly detection
        assert incidents == []
        mock_session.add.assert_not_called()


class TestCooldownHelpers:
    """Tests for Valkey-based cooldown helpers with mocked Valkey."""

    @pytest.mark.asyncio
    async def test_is_in_cooldown_returns_true_when_key_exists(self) -> None:
        """When Valkey has the cooldown key, _is_in_cooldown returns True."""
        instance_id = uuid4()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=b"1")
        mock_client.aclose = AsyncMock()

        with patch(
            "app.analyzers.anomaly._get_valkey_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await _is_in_cooldown(instance_id, "cpu_usage")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_in_cooldown_returns_false_when_no_key(self) -> None:
        """When Valkey key does not exist, _is_in_cooldown returns False."""
        instance_id = uuid4()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        mock_client.aclose = AsyncMock()

        with patch(
            "app.analyzers.anomaly._get_valkey_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await _is_in_cooldown(instance_id, "cpu_usage")

        assert result is False

    @pytest.mark.asyncio
    async def test_is_in_cooldown_fallback_when_valkey_down(self) -> None:
        """When Valkey is unreachable, falls back to in-memory dict (returns False
        for a fresh key)."""
        instance_id = uuid4()

        with patch(
            "app.analyzers.anomaly._get_valkey_client",
            new_callable=AsyncMock,
            return_value=None,  # Valkey unavailable
        ), patch.dict(
            "app.analyzers.anomaly._cooldown_fallback", {}, clear=True
        ):
            result = await _is_in_cooldown(instance_id, "cpu_usage")

        assert result is False

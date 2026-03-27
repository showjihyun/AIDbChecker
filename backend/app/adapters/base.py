# Spec: AG-001, DM-001
"""BaseAdapter ABC — common interface for all target DB adapters.

Phase 1: PostgreSQLRemoteAdapter (remote pg_stat_* queries).
Phase 3: PostgreSQLLocalCollector (sidecar push via gRPC — ADR-011: Kafka 제거).
Both share the same interface — only deployment topology differs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class MetricSample:
    """Raw metric snapshot from a target DB instance."""

    instance_id: UUID
    sampled_at: datetime
    category: str  # hot / warm / cold
    metrics: dict = field(default_factory=dict)


@dataclass
class ActiveSessionSample:
    """Single ASH sample row from pg_stat_activity."""

    instance_id: UUID
    sampled_at: datetime
    pid: int
    query: str | None
    query_hash: int | None
    state: str
    wait_event_type: str | None
    wait_event: str | None
    backend_type: str | None
    client_addr: str | None
    application_name: str | None
    query_start: datetime | None
    duration_ms: float | None


class BaseAdapter(ABC):
    """Abstract base for all target DB adapters.

    Every adapter must support connect/disconnect lifecycle,
    metric collection by category, ASH sampling, and connection testing.
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection pool to target DB. Returns True on success."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection pool and release resources."""
        ...

    @abstractmethod
    async def collect_metrics(self, category: str) -> MetricSample | None:
        """Collect metrics for the given category (hot/warm/cold).

        Returns None on failure (silent skip to avoid blocking other instances).
        """
        ...

    @abstractmethod
    async def collect_ash(self) -> list[ActiveSessionSample]:
        """Sample active sessions from pg_stat_activity.

        Returns empty list on failure (silent skip).
        """
        ...

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Test connectivity to target DB.

        Returns (True, "OK") on success or (False, error_message) on failure.
        """
        ...

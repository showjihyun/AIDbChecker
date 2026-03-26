# Spec: FS-KPI-001
"""Pydantic v2 schemas for DB KPI API responses.

Defines the 5-category, 12-indicator KPI response structure with
threshold-based status evaluation (normal/warning/critical/unknown).
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class KPIValue(BaseModel):
    """Single KPI metric value with status evaluation.

    Status is determined by comparing value against spec-defined thresholds:
    - normal: below warning threshold
    - warning: at or above warning, below critical
    - critical: at or above critical threshold
    - unknown: value is None (data unavailable)
    """

    value: float | int | None = None
    unit: str
    status: Literal["normal", "warning", "critical", "unknown"] = "unknown"

    model_config = {"from_attributes": True}


class ThroughputKPI(BaseModel):
    """Throughput & Latency KPIs (KPI-01 ~ KPI-04)."""

    tps: KPIValue = Field(description="KPI-01: Transactions per second (delta/s)")
    qps: KPIValue = Field(description="KPI-02: Queries per second (delta/s)")
    avg_response_time_ms: KPIValue = Field(description="KPI-03: Avg response time")
    slow_queries: KPIValue = Field(description="KPI-04: Slow queries (duration > 1s)")


class ResourceKPI(BaseModel):
    """Resource & System KPIs (KPI-05 ~ KPI-06)."""

    buffer_hit_ratio: KPIValue = Field(description="KPI-05: Buffer cache hit ratio (%)")
    disk_iops: KPIValue = Field(description="KPI-06: Disk IOPS (delta/s)")


class ConnectionKPI(BaseModel):
    """Connection & Session KPIs (KPI-07 ~ KPI-08)."""

    active_sessions: KPIValue = Field(description="KPI-07: Active sessions count")
    connection_usage_pct: KPIValue = Field(description="KPI-08: Connection usage (%)")


class LockKPI(BaseModel):
    """Lock & Contention KPIs (KPI-09 ~ KPI-10)."""

    lock_waits: KPIValue = Field(description="KPI-09: Lock waits count")
    deadlocks_per_sec: KPIValue = Field(description="KPI-10: Deadlocks per second")


class StorageKPI(BaseModel):
    """Availability & Storage KPIs (KPI-11 ~ KPI-12)."""

    db_size_bytes: KPIValue = Field(description="KPI-11: Database size in bytes")
    replication_lag_sec: KPIValue = Field(description="KPI-12: Replication lag (seconds)")


class KPIAdvisory(BaseModel):
    """Advisory message attached to KPI response.

    Indicates missing extensions, misconfigurations, or
    informational notes about the monitored instance.
    """

    level: Literal["info", "warning", "error"]
    title: str
    message: str
    action: str | None = None  # e.g., "CREATE EXTENSION pg_stat_statements;"


class KPIResponse(BaseModel):
    """Full KPI response — 5 categories, 12 indicators.

    Spec: FS-KPI-001 Section 5.3
    """

    instance_id: UUID
    timestamp: datetime
    throughput: ThroughputKPI
    resource: ResourceKPI
    connection: ConnectionKPI
    lock: LockKPI
    storage: StorageKPI
    advisories: list[KPIAdvisory] = []

    model_config = {"from_attributes": True}

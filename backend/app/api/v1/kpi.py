# Spec: FS-KPI-001
"""KPI API — compute and return 12 DB performance indicators for an instance.

GET /api/v1/instances/{id}/kpi

Delta-based KPIs are derived from the last 2 hot metric_samples.
Live KPIs (active sessions, lock waits, slow queries, connection usage)
are queried directly from the target DB via a shared adapter cache.
Storage KPIs come from the latest cold metric_samples.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.postgresql.remote import PostgreSQLRemoteAdapter
from app.api.deps import get_session
from app.models.db_instance import DBInstance
from app.schemas.kpi import KPIResponse
from app.services.kpi_calculator import KPICalculator
from app.utils.dsn import build_target_dsn

logger = structlog.get_logger(__name__)

router = APIRouter()

# Shared adapter cache for KPI endpoint — avoids creating a new connection pool
# per request. Keyed by (instance_id, dsn) so DSN changes invalidate the cache.
_kpi_adapter_cache: dict[UUID, tuple[PostgreSQLRemoteAdapter, str]] = {}


async def _get_kpi_adapter(instance: DBInstance) -> PostgreSQLRemoteAdapter | None:
    """Get or create a cached adapter for KPI live queries.

    Reuses existing connections instead of creating a new pool per request.
    Invalidates cache when DSN changes (e.g., password rotation).
    """
    dsn = build_target_dsn(instance)

    if instance.id in _kpi_adapter_cache:
        cached_adapter, cached_dsn = _kpi_adapter_cache[instance.id]
        if cached_dsn == dsn:
            return cached_adapter
        # DSN changed — disconnect old adapter
        await cached_adapter.disconnect()
        del _kpi_adapter_cache[instance.id]

    adapter = PostgreSQLRemoteAdapter(instance_id=instance.id, dsn=dsn)
    connected = await adapter.connect()
    if not connected:
        # Always disconnect on failure to avoid partial pool leak
        await adapter.disconnect()
        return None

    _kpi_adapter_cache[instance.id] = (adapter, dsn)
    return adapter


@router.get(
    "/instances/{instance_id}/kpi",
    response_model=KPIResponse,
    summary="Get 12 KPI indicators for a DB instance",
    description=(
        "Returns 5-category, 12-indicator KPI snapshot. "
        "Delta KPIs use last 2 hot samples. "
        "Live KPIs are queried from the target DB via cached adapter."
    ),
)
async def get_instance_kpi(
    instance_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> KPIResponse:
    """Compute and return all 12 KPIs for a monitored instance.

    Spec: FS-KPI-001 Section 5.3
    """
    stmt = select(DBInstance).where(
        DBInstance.id == instance_id,
        DBInstance.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    instance = result.scalar_one_or_none()

    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance {instance_id} not found. Verify the ID is correct.",
        )

    adapter: PostgreSQLRemoteAdapter | None = None
    if instance.is_active and instance.db_type == "postgresql":
        adapter = await _get_kpi_adapter(instance)

    return await KPICalculator.compute_all_kpi(
        instance_id=instance_id,
        session=session,
        adapter=adapter,
    )

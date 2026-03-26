# Spec: FS-KPI-001
"""KPI API — compute and return 12 DB performance indicators for an instance.

GET /api/v1/instances/{id}/kpi

Delta-based KPIs are derived from the last 2 hot metric_samples.
Live KPIs (active sessions, lock waits, slow queries, connection usage)
are queried directly from the target DB via the adapter.
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


@router.get(
    "/instances/{instance_id}/kpi",
    response_model=KPIResponse,
    summary="Get 12 KPI indicators for a DB instance",
    description=(
        "Returns 5-category, 12-indicator KPI snapshot. "
        "Delta KPIs use last 2 hot samples. "
        "Live KPIs are queried from the target DB in real-time."
    ),
)
async def get_instance_kpi(
    instance_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> KPIResponse:
    """Compute and return all 12 KPIs for a monitored instance.

    Spec: FS-KPI-001 Section 5.3

    The endpoint:
    1. Fetches last 2 hot metric_samples for delta calculations
    2. Fetches latest cold sample for storage KPIs
    3. Opens a temporary adapter connection to the target DB for live KPIs
    4. Returns all 12 indicators with threshold-based status evaluation
    """
    # Verify instance exists and is not soft-deleted
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

    # Create a temporary adapter for live KPI queries
    adapter: PostgreSQLRemoteAdapter | None = None
    try:
        if instance.is_active and instance.db_type == "postgresql":
            dsn = build_target_dsn(instance)
            adapter = PostgreSQLRemoteAdapter(instance_id=instance.id, dsn=dsn)
            connected = await adapter.connect()
            if not connected:
                logger.warning(
                    "kpi.adapter_connect_failed",
                    instance_id=str(instance_id),
                )
                adapter = None

        kpi_response = await KPICalculator.compute_all_kpi(
            instance_id=instance_id,
            session=session,
            adapter=adapter,
        )
        return kpi_response

    finally:
        # Always clean up the temporary adapter connection
        if adapter is not None:
            await adapter.disconnect()

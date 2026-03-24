# Spec: DM-001, MVP-DASH-001
"""Instance CRUD API -- register, update, delete, test monitored DB instances."""

import urllib.parse
from datetime import datetime, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session, remove_target_pool
from app.models.db_instance import DBInstance
from app.schemas.instance import (
    ConnectionTestResponse,
    InstanceCreate,
    InstanceListResponse,
    InstanceResponse,
    InstanceUpdate,
)
from app.utils.encryption import encrypt_value, decrypt_value
from app.adapters.postgresql.remote import PostgreSQLRemoteAdapter

logger = structlog.get_logger(__name__)

router = APIRouter()

# Explicit allowlist of fields that can be set via the update endpoint.
# Prevents setattr from modifying internal/sensitive ORM attributes.
_ALLOWED_UPDATE_FIELDS = frozenset({
    "name",
    "host",
    "port",
    "database_name",
    "cluster_id",
    "environment",
    "is_active",
    "autonomy_level",
})


def _build_dsn(instance: DBInstance) -> str:
    """Build asyncpg DSN from instance fields + decrypted connection_config.

    Uses urllib.parse.quote_plus() for username and password to handle
    special characters (@, /, %, :, ?, #) safely in the URI.
    """
    config = instance.connection_config or {}
    username = decrypt_value(config["username"]) if "username" in config else "neuraldb"
    password = decrypt_value(config["password"]) if "password" in config else ""
    ssl_mode = config.get("sslmode", "prefer")
    return (
        f"postgresql://{urllib.parse.quote_plus(username)}:{urllib.parse.quote_plus(password)}"
        f"@{instance.host}:{instance.port}/{instance.database_name}"
        f"?sslmode={ssl_mode}"
    )


def _to_response(instance: DBInstance) -> InstanceResponse:
    """Convert ORM model to response schema (strips sensitive connection_config)."""
    return InstanceResponse(
        id=instance.id,
        name=instance.name,
        db_type=instance.db_type,
        host=instance.host,
        port=instance.port,
        database_name=instance.database_name,
        cluster_id=instance.cluster_id,
        environment=instance.environment,
        is_active=instance.is_active,
        autonomy_level=instance.autonomy_level,
        metadata_extra=instance.metadata_,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


@router.get("/instances", response_model=InstanceListResponse)
async def list_instances(
    session: AsyncSession = Depends(get_session),
) -> InstanceListResponse:
    """List all active (non-deleted) DB instances."""
    # Spec: DM-001 -- soft delete filter
    stmt = select(DBInstance).where(DBInstance.deleted_at.is_(None)).order_by(DBInstance.name)
    result = await session.execute(stmt)
    instances = list(result.scalars().all())

    count_stmt = select(func.count()).select_from(DBInstance).where(DBInstance.deleted_at.is_(None))
    total = (await session.execute(count_stmt)).scalar_one()

    return InstanceListResponse(
        items=[_to_response(i) for i in instances],
        total=total,
    )


@router.post(
    "/instances",
    response_model=InstanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_instance(
    body: InstanceCreate,
    session: AsyncSession = Depends(get_session),
) -> InstanceResponse:
    """Register a new monitored DB instance."""
    # Check uniqueness
    exists_stmt = select(DBInstance.id).where(
        DBInstance.name == body.name,
        DBInstance.deleted_at.is_(None),
    )
    existing = (await session.execute(exists_stmt)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Instance name '{body.name}' already exists. Use a unique name.",
        )

    # Spec: ADR-007 -- encrypt credentials in connection_config
    encrypted_config: dict = {}
    for key, value in body.connection_config.items():
        if key in ("username", "password", "ssl_key", "ssl_cert"):
            encrypted_config[key] = encrypt_value(str(value))
        else:
            encrypted_config[key] = value

    instance = DBInstance(
        name=body.name,
        db_type=body.db_type,
        host=body.host,
        port=body.port,
        database_name=body.database_name,
        cluster_id=body.cluster_id,
        environment=body.environment,
        connection_config=encrypted_config,
        metadata_=body.metadata_extra,
    )

    session.add(instance)
    await session.commit()
    await session.refresh(instance)

    logger.info("instance.created", instance_id=str(instance.id), name=instance.name)
    return _to_response(instance)


@router.get("/instances/{instance_id}", response_model=InstanceResponse)
async def get_instance(
    instance_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> InstanceResponse:
    """Get a single DB instance by ID."""
    instance = await _get_instance_or_404(session, instance_id)
    return _to_response(instance)


@router.put("/instances/{instance_id}", response_model=InstanceResponse)
async def update_instance(
    instance_id: UUID,
    body: InstanceUpdate,
    session: AsyncSession = Depends(get_session),
) -> InstanceResponse:
    """Update a monitored DB instance."""
    instance = await _get_instance_or_404(session, instance_id)

    update_data = body.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        if field_name == "metadata_extra":
            instance.metadata_ = value
        elif field_name == "connection_config" and value is not None:
            # Spec: ADR-007 -- re-encrypt credentials on update
            encrypted: dict = {}
            for k, v in value.items():
                if k in ("username", "password", "ssl_key", "ssl_cert"):
                    encrypted[k] = encrypt_value(str(v))
                else:
                    encrypted[k] = v
            instance.connection_config = encrypted
        elif field_name in _ALLOWED_UPDATE_FIELDS:
            setattr(instance, field_name, value)
        else:
            logger.warning(
                "instance.update_field_rejected",
                instance_id=str(instance_id),
                field=field_name,
            )

    await session.commit()
    await session.refresh(instance)

    logger.info("instance.updated", instance_id=str(instance.id))
    return _to_response(instance)


@router.delete(
    "/instances/{instance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_instance(
    instance_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Soft-delete a monitored DB instance."""
    # Spec: DM-001 -- soft delete via deleted_at
    instance = await _get_instance_or_404(session, instance_id)
    instance.deleted_at = datetime.now(timezone.utc)
    instance.is_active = False
    await session.commit()

    # Clean up any target DB pool associated with this instance
    await remove_target_pool(instance_id)

    logger.info("instance.soft_deleted", instance_id=str(instance.id))


@router.post(
    "/instances/{instance_id}/test-connection",
    response_model=ConnectionTestResponse,
)
async def test_connection(
    instance_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ConnectionTestResponse:
    """Test connectivity to the target DB using the adapter."""
    instance = await _get_instance_or_404(session, instance_id)

    if instance.db_type != "postgresql":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Adapter for '{instance.db_type}' is not implemented yet. "
            "Only PostgreSQL is supported in MVP.",
        )

    dsn = _build_dsn(instance)
    adapter = PostgreSQLRemoteAdapter(instance_id=instance.id, dsn=dsn)
    success, message = await adapter.test_connection()

    return ConnectionTestResponse(success=success, message=message)


async def _get_instance_or_404(session: AsyncSession, instance_id: UUID) -> DBInstance:
    """Fetch a non-deleted instance or raise 404."""
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
    return instance

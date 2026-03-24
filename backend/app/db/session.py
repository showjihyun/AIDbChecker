# Spec: DM-001
"""Database session management -- System DB + Target DB pool separation.

Note on _target_pools:
  The PostgreSQL Remote Adapter creates its own asyncpg pools directly
  (not SQLAlchemy engines). The _target_pools dict and its helper functions
  (get_target_pool / remove_target_pool) exist for API-level cleanup:
  - remove_target_pool is called from the instance delete endpoint.
  - _target_pools is iterated during shutdown to dispose any engines.
  The adapter itself does NOT use these functions; it manages raw asyncpg
  pools independently. This separation is intentional per ADR-006.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# Pool A: System DB (read+write, pool_size=20, max_overflow=10)
system_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_POOL_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    echo=settings.DB_ECHO,
)

AsyncSessionLocal = async_sessionmaker(
    system_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Pool B: Target DB (readonly, per-instance, statement_timeout=500ms)
# Currently used only for shutdown cleanup and instance deletion.
# The adapter creates its own asyncpg pools separately.
_target_pools: dict[UUID, AsyncEngine] = {}


async def get_target_pool(instance_id: UUID, dsn: str) -> AsyncEngine:
    """Get or create a readonly connection pool for a target DB instance.

    Reserved for future use. The PostgreSQL adapter currently creates
    its own asyncpg pools directly for lower-level control.
    """
    if instance_id not in _target_pools:
        _target_pools[instance_id] = create_async_engine(
            dsn,
            pool_size=2,
            max_overflow=0,
            connect_args={
                "server_settings": {
                    "statement_timeout": "500",
                    "default_transaction_read_only": "on",
                }
            },
        )
    return _target_pools[instance_id]


async def remove_target_pool(instance_id: UUID) -> None:
    """Dispose and remove a target DB connection pool."""
    if instance_id in _target_pools:
        await _target_pools[instance_id].dispose()
        del _target_pools[instance_id]


async def get_session() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency -- yields a System DB session."""
    async with AsyncSessionLocal() as session:
        yield session

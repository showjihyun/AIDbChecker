# Spec: DM-MIG-001
"""Alembic migration environment — supports both sync and async PostgreSQL."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.models import Base  # noqa: F401 — triggers all model imports

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_sync_url() -> str:
    """Convert async URL to sync URL for psycopg2."""
    url = str(settings.DATABASE_URL)
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = str(settings.DATABASE_URL)
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online_sync() -> None:
    """Run migrations using synchronous psycopg2 driver (more reliable on Windows)."""
    connectable = create_engine(_get_sync_url())
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


async def run_migrations_online_async() -> None:
    """Run migrations using async engine (asyncpg)."""
    connectable = create_async_engine(str(settings.DATABASE_URL))
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    # Use sync driver by default (avoids asyncpg segfault on Windows).
    # Set ALEMBIC_USE_ASYNC=1 to use asyncpg instead.
    if os.getenv("ALEMBIC_USE_ASYNC"):
        asyncio.run(run_migrations_online_async())
    else:
        run_migrations_online_sync()

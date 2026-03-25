# Spec: MVP-ADMIN-001
"""Seed script -- create default super_admin user.

Usage:
    uv run python -m app.db.seed
"""

import asyncio
import os

import structlog
from sqlalchemy import select

from app.api.v1.auth import pwd_context
from app.db.session import AsyncSessionLocal
from app.models.user import User

logger = structlog.get_logger(__name__)

DEFAULT_ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@neuraldb.local")
DEFAULT_ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "change-me-in-production")
DEFAULT_ADMIN_NAME = "System Administrator"


async def seed_default_admin() -> None:
    """Create default super_admin user if it does not already exist."""
    async with AsyncSessionLocal() as session:
        stmt = select(User.id).where(
            User.email == DEFAULT_ADMIN_EMAIL,
            User.deleted_at.is_(None),
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()

        if existing is not None:
            logger.info(
                "seed.skip",
                reason="Default admin user already exists",
                email=DEFAULT_ADMIN_EMAIL,
            )
            return

        admin = User(
            email=DEFAULT_ADMIN_EMAIL,
            name=DEFAULT_ADMIN_NAME,
            hashed_password=pwd_context.hash(DEFAULT_ADMIN_PASSWORD),
            role="super_admin",
            auth_provider="local",
        )
        session.add(admin)
        await session.commit()

        logger.info(
            "seed.created",
            email=DEFAULT_ADMIN_EMAIL,
            role="super_admin",
            user_id=str(admin.id),
        )


def main() -> None:
    """Entry point for `uv run python -m app.db.seed`."""
    asyncio.run(seed_default_admin())
    print(f"Seed complete. Default admin: {DEFAULT_ADMIN_EMAIL}")


if __name__ == "__main__":
    main()

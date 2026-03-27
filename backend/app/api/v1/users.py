# Spec: MVP-ADMIN-001, MVP-ADMIN-002, MVP-ADMIN-003
"""User CRUD API -- list, create, update, soft-delete users (admin only)."""

from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_role
from app.api.v1.auth import pwd_context
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)

logger = structlog.get_logger(__name__)

router = APIRouter()

# Explicit allowlist of fields that can be set via the update endpoint.
_ALLOWED_UPDATE_FIELDS = frozenset({"name", "role", "is_active"})


def _to_response(user: User) -> UserResponse:
    """Convert ORM model to response schema (strips sensitive fields)."""
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        auth_provider=user.auth_provider,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@router.get(
    "/users",
    response_model=UserListResponse,
    dependencies=[Depends(require_role("super_admin"))],
)
async def list_users(
    session: AsyncSession = Depends(get_session),
) -> UserListResponse:
    """List all active (non-deleted) users. Requires super_admin role."""
    # Spec: DM-001 -- soft delete filter
    stmt = select(User).where(User.deleted_at.is_(None)).order_by(User.name)
    result = await session.execute(stmt)
    users = list(result.scalars().all())

    count_stmt = select(func.count()).select_from(User).where(User.deleted_at.is_(None))
    total = (await session.execute(count_stmt)).scalar_one()

    return UserListResponse(
        items=[_to_response(u) for u in users],
        total=total,
    )


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin"))],
)
async def create_user(
    body: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """Create a new user. Requires super_admin role."""
    # Check uniqueness
    exists_stmt = select(User.id).where(
        User.email == body.email,
        User.deleted_at.is_(None),
    )
    existing = (await session.execute(exists_stmt)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{body.email}' already exists. Use a unique email.",
        )

    user = User(
        email=body.email,
        name=body.name,
        hashed_password=pwd_context.hash(body.password),
        role=body.role,
        auth_provider="local",
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    logger.info("user.created", user_id=str(user.id), email=user.email, role=user.role)
    return _to_response(user)


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_role("super_admin"))],
)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """Update a user. Requires super_admin role."""
    user = await _get_user_or_404(session, user_id)

    update_data = body.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        if field_name == "password" and value is not None:
            user.hashed_password = pwd_context.hash(value)
        elif field_name in _ALLOWED_UPDATE_FIELDS:
            setattr(user, field_name, value)
        else:
            logger.warning(
                "user.update_field_rejected",
                user_id=str(user_id),
                field=field_name,
            )

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User update conflict. Check for duplicate values.",
        )
    await session.refresh(user)

    logger.info("user.updated", user_id=str(user.id))
    return _to_response(user)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("super_admin"))],
)
async def delete_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Soft-delete a user. Requires super_admin role."""
    # Spec: DM-001 -- soft delete via deleted_at
    user = await _get_user_or_404(session, user_id)
    user.deleted_at = datetime.now(UTC)
    user.is_active = False
    await session.commit()

    logger.info("user.soft_deleted", user_id=str(user.id))


async def _get_user_or_404(session: AsyncSession, user_id: UUID) -> User:
    """Fetch a non-deleted user or raise 404."""
    stmt = select(User).where(
        User.id == user_id,
        User.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found. Verify the ID is correct.",
        )
    return user

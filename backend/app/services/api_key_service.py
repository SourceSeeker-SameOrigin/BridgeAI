import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.user import ApiKey, User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse

PREFIX_LENGTH = 8
KEY_BYTES = 32


def _generate_raw_key() -> str:
    """Generate a cryptographically secure random API key."""
    return secrets.token_urlsafe(KEY_BYTES)


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash for storage (constant-time comparison not needed at lookup stage)."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _to_response(api_key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=str(api_key.id),
        name=api_key.name,
        prefix=api_key.prefix,
        scopes=api_key.scopes or [],
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
    )


async def create_api_key(
    request: ApiKeyCreate,
    user: User,
    db: AsyncSession,
) -> ApiKeyCreatedResponse:
    raw_key = _generate_raw_key()
    prefix = raw_key[:PREFIX_LENGTH]
    key_hash = _hash_key(raw_key)

    expires_at = None
    if request.expires_in_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)

    api_key = ApiKey(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=request.name,
        key_hash=key_hash,
        prefix=prefix,
        scopes=request.scopes,
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.flush()

    return ApiKeyCreatedResponse(
        id=str(api_key.id),
        name=api_key.name,
        prefix=api_key.prefix,
        scopes=api_key.scopes or [],
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        plain_key=raw_key,
    )


async def list_api_keys(
    user: User,
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
) -> tuple[list[ApiKeyResponse], int]:
    base_query = select(ApiKey).where(ApiKey.user_id == user.id)

    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        base_query.order_by(ApiKey.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    keys = result.scalars().all()
    return [_to_response(k) for k in keys], total


async def get_api_key(
    api_key_id: UUID,
    user: User,
    db: AsyncSession,
) -> ApiKeyResponse:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == api_key_id, ApiKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise NotFoundException(message="API Key not found")
    return _to_response(api_key)


async def revoke_api_key(
    api_key_id: UUID,
    user: User,
    db: AsyncSession,
) -> ApiKeyResponse:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == api_key_id, ApiKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise NotFoundException(message="API Key not found")
    if not api_key.is_active:
        raise BadRequestException(message="API Key is already revoked")

    api_key.is_active = False
    await db.flush()
    return _to_response(api_key)


async def delete_api_key(
    api_key_id: UUID,
    user: User,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == api_key_id, ApiKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise NotFoundException(message="API Key not found")
    await db.delete(api_key)
    await db.flush()


async def verify_api_key(raw_key: str, db: AsyncSession) -> Optional[User]:
    """Verify an API key and return the associated user, or None if invalid."""
    key_hash = _hash_key(raw_key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None

    # Check expiration
    if api_key.expires_at is not None and api_key.expires_at < datetime.now(timezone.utc):
        return None

    # Update last_used_at
    api_key.last_used_at = datetime.now(timezone.utc)

    # Load the user
    user_result = await db.execute(
        select(User).where(User.id == api_key.user_id, User.is_active.is_(True))
    )
    return user_result.scalar_one_or_none()

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, UnauthorizedException
from app.core.security import create_access_token, hash_password, verify_password
from app.config import settings
from app.models.user import Tenant, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse


async def _get_or_create_default_tenant(db: AsyncSession) -> Tenant:
    """Get or create a default tenant for new user registration."""
    result = await db.execute(select(Tenant).where(Tenant.slug == "default"))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(name="Default", slug="default", plan="free")
        db.add(tenant)
        await db.flush()
    return tenant


async def register_user(request: RegisterRequest, db: AsyncSession) -> UserResponse:
    # Check if username already exists
    result = await db.execute(select(User).where(User.username == request.username))
    if result.scalar_one_or_none() is not None:
        raise ConflictException(message="Username already exists")

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none() is not None:
        raise ConflictException(message="Email already exists")

    # Get or create default tenant
    tenant = await _get_or_create_default_tenant(db)

    user = User(
        tenant_id=tenant.id,
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        role="user",
    )
    db.add(user)
    await db.flush()

    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        tenant_id=str(user.tenant_id),
    )


async def login_user(request: LoginRequest, db: AsyncSession) -> TokenResponse:
    # Try login by username or email
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()

    if user is None:
        # Also try by email
        result = await db.execute(select(User).where(User.email == request.username))
        user = result.scalar_one_or_none()

    if user is None or not verify_password(request.password, user.hashed_password):
        raise UnauthorizedException(message="Invalid username or password")

    if not user.is_active:
        raise UnauthorizedException(message="User account is disabled")

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


async def get_user_profile(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        tenant_id=str(user.tenant_id) if user.tenant_id else None,
    )

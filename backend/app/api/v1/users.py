"""Users API — tenant user management (admin only)."""

import logging
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.core.security import get_current_user, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


# ------------------------------------------------------------------
# Request schemas
# ------------------------------------------------------------------

class InviteUserRequest(BaseModel):
    username: str
    email: EmailStr
    role: str = "user"


class ChangeRoleRequest(BaseModel):
    role: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _require_admin(user: User) -> None:
    """Raise ForbiddenException if user is not admin."""
    if user.role != "admin":
        raise ForbiddenException(message="仅管理员可执行此操作")


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        tenant_id=str(user.tenant_id) if user.tenant_id else None,
    )


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/me/password", response_model=ApiResponse)
async def change_my_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Change the authenticated user's own password (verifies old password)."""
    if not verify_password(request.old_password, current_user.hashed_password):
        raise BadRequestException(message="旧密码不正确")
    if len(request.new_password) < 8:
        raise BadRequestException(message="新密码至少 8 位")
    if request.new_password == request.old_password:
        raise BadRequestException(message="新密码不能与旧密码相同")

    current_user.hashed_password = hash_password(request.new_password)
    await db.flush()
    await db.commit()
    logger.info("User %s changed password", current_user.username)
    return ApiResponse.success(message="密码已更新")


@router.get("", response_model=ApiResponse[list[UserResponse]])
async def list_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List all users in the current tenant (admin only)."""
    _require_admin(current_user)

    result = await db.execute(
        select(User)
        .where(User.tenant_id == current_user.tenant_id, User.is_active.is_(True))
        .order_by(User.created_at.desc())
        .limit(200)
    )
    users = result.scalars().all()
    return ApiResponse.success(data=[_user_to_response(u) for u in users])


@router.post("/invite", response_model=ApiResponse[UserResponse])
async def invite_user(
    request: InviteUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Invite a new user to the current tenant with a temporary password."""
    _require_admin(current_user)

    if request.role not in ("user", "admin"):
        raise BadRequestException(message="角色必须为 user 或 admin")

    # Check duplicate username within tenant
    existing = await db.execute(
        select(User).where(
            User.tenant_id == current_user.tenant_id,
            User.username == request.username,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise BadRequestException(message=f"用户名 {request.username} 已存在")

    # Check duplicate email within tenant
    existing_email = await db.execute(
        select(User).where(
            User.tenant_id == current_user.tenant_id,
            User.email == request.email,
        )
    )
    if existing_email.scalar_one_or_none() is not None:
        raise BadRequestException(message=f"邮箱 {request.email} 已存在")

    # Create user with temporary password
    temp_password = uuid.uuid4().hex[:12]
    new_user = User(
        tenant_id=current_user.tenant_id,
        username=request.username,
        email=request.email,
        hashed_password=hash_password(temp_password),
        role=request.role,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    await db.commit()

    resp = _user_to_response(new_user)
    logger.info("User invited: %s (temp_password=%s)", request.username, temp_password)
    return ApiResponse.success(
        data=resp,
        message=f"用户已邀请，临时密码: {temp_password}",
    )


@router.put("/{user_id}/role", response_model=ApiResponse[UserResponse])
async def change_role(
    user_id: str,
    request: ChangeRoleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Change a user's role (admin only)."""
    _require_admin(current_user)

    if request.role not in ("user", "admin"):
        raise BadRequestException(message="角色必须为 user 或 admin")

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise NotFoundException(message="用户不存在")

    result = await db.execute(
        select(User).where(
            User.id == uid,
            User.tenant_id == current_user.tenant_id,
        )
    )
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise NotFoundException(message="用户不存在")

    if str(target_user.id) == str(current_user.id):
        raise BadRequestException(message="不能修改自己的角色")

    target_user.role = request.role
    await db.flush()
    await db.refresh(target_user)
    await db.commit()

    return ApiResponse.success(data=_user_to_response(target_user))


@router.delete("/{user_id}", response_model=ApiResponse)
async def remove_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Remove (deactivate) a user from the tenant (admin only)."""
    _require_admin(current_user)

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise NotFoundException(message="用户不存在")

    result = await db.execute(
        select(User).where(
            User.id == uid,
            User.tenant_id == current_user.tenant_id,
        )
    )
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise NotFoundException(message="用户不存在")

    if str(target_user.id) == str(current_user.id):
        raise BadRequestException(message="不能删除自己")

    target_user.is_active = False
    await db.flush()
    await db.commit()

    return ApiResponse.success(message="用户已移除")

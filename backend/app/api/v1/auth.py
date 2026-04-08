import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import create_access_token, get_current_user, hash_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.schemas.common import ApiResponse
from app.services import auth_service
from app.services.wechat_oauth import wechat_oauth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=ApiResponse[UserResponse])
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    user = await auth_service.register_user(request, db)
    return ApiResponse.success(data=user)


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    token = await auth_service.login_user(request, db)
    return ApiResponse.success(data=token)


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_me(current_user: User = Depends(get_current_user)) -> ApiResponse:
    profile = await auth_service.get_user_profile(current_user)
    return ApiResponse.success(data=profile)


# ──────────────────────────────────────────────
# WeChat OAuth (微信开放平台扫码登录)
# ──────────────────────────────────────────────


@router.get("/wechat/qrcode")
async def wechat_qr_url() -> ApiResponse:
    """Get WeChat QR code login URL.

    Returns auth_url for the frontend to redirect the user.
    If WeChat login is not configured, returns configured=False with a message.
    """
    if not wechat_oauth.is_configured():
        return ApiResponse.success(
            data={
                "auth_url": None,
                "configured": False,
                "message": "微信登录未配置，请在 .env 中配置 WECHAT_OPEN_APP_ID 和 WECHAT_OPEN_APP_SECRET",
            }
        )

    state = uuid.uuid4().hex[:8]
    redis = await get_redis()
    await redis.setex(f"wechat_oauth_state:{state}", 300, "1")

    auth_url = wechat_oauth.get_auth_url(state=state)
    return ApiResponse.success(
        data={"auth_url": auth_url, "configured": True, "state": state}
    )


@router.get("/wechat/callback")
async def wechat_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """WeChat OAuth callback.

    Called by WeChat after user scans QR code.
    Exchanges code for user info, creates/links account, returns JWT.
    """
    if not wechat_oauth.is_configured():
        raise HTTPException(status_code=400, detail="微信登录未配置")

    # Verify state (CSRF protection)
    redis = await get_redis()
    valid = await redis.get(f"wechat_oauth_state:{state}")
    if not valid:
        raise HTTPException(status_code=400, detail="无效的 state 参数，可能已过期")
    await redis.delete(f"wechat_oauth_state:{state}")

    # Exchange code for token
    try:
        token_data = await wechat_oauth.exchange_code(code)
    except ValueError as e:
        logger.error("WeChat exchange_code failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    access_token = token_data["access_token"]
    openid = token_data["openid"]
    unionid = token_data.get("unionid", "")

    # Get user info
    try:
        user_info = await wechat_oauth.get_user_info(access_token, openid)
    except ValueError as e:
        logger.error("WeChat get_user_info failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    nickname = user_info.get("nickname", f"wx_{openid[:8]}")
    avatar = user_info.get("headimgurl", "")

    # Find or create user by wechat_openid
    result = await db.execute(select(User).where(User.wechat_openid == openid))
    user = result.scalar_one_or_none()

    if not user:
        # Create new user linked to WeChat
        user = User(
            username=f"wx_{openid[:8]}_{uuid.uuid4().hex[:4]}",
            email=f"{openid[:8]}@wechat.user",
            hashed_password=hash_password(uuid.uuid4().hex),
            wechat_openid=openid,
            wechat_unionid=unionid,
            tenant_id="00000000-0000-0000-0000-000000000001",
            is_active=True,
        )
        db.add(user)
        await db.flush()

    # Generate JWT
    jwt_token = create_access_token(data={"sub": str(user.id), "role": user.role})

    await db.commit()

    return ApiResponse.success(
        data={
            "access_token": jwt_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "username": user.username,
                "nickname": nickname,
                "avatar": avatar,
            },
        }
    )

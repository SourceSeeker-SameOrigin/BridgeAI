from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.schemas.common import ApiResponse
from app.services import auth_service

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

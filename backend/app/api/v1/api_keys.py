import math
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse
from app.schemas.common import ApiResponse, PageResponse
from app.services import api_key_service

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.post("", response_model=ApiResponse[ApiKeyCreatedResponse])
async def create_api_key(
    request: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await api_key_service.create_api_key(request, current_user, db)
    return ApiResponse.success(data=result)


@router.get("", response_model=ApiResponse[PageResponse[ApiKeyResponse]])
async def list_api_keys(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    items, total = await api_key_service.list_api_keys(current_user, db, page, size)
    return ApiResponse.success(data=PageResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    ))


@router.get("/{api_key_id}", response_model=ApiResponse[ApiKeyResponse])
async def get_api_key(
    api_key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await api_key_service.get_api_key(api_key_id, current_user, db)
    return ApiResponse.success(data=result)


@router.post("/{api_key_id}/revoke", response_model=ApiResponse[ApiKeyResponse])
async def revoke_api_key(
    api_key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await api_key_service.revoke_api_key(api_key_id, current_user, db)
    return ApiResponse.success(data=result, message="API Key revoked")


@router.delete("/{api_key_id}", response_model=ApiResponse)
async def delete_api_key(
    api_key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    await api_key_service.delete_api_key(api_key_id, current_user, db)
    return ApiResponse.success(message="API Key deleted")

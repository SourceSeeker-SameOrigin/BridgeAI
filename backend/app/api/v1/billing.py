"""Billing API — 用量查询与套餐信息。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.billing import PlanInfo, UsageSummary
from app.schemas.common import ApiResponse
from app.services.billing_service import billing_service

router = APIRouter(prefix="/billing", tags=["Billing"])


@router.get("/usage", response_model=ApiResponse[UsageSummary])
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """获取当月用量汇总。"""
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    if not tenant_id:
        return ApiResponse.error(code=400, message="租户信息缺失")

    usage = await billing_service.get_monthly_usage(db, tenant_id)
    return ApiResponse.success(data=usage)


@router.get("/plan", response_model=ApiResponse[PlanInfo])
async def get_plan(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """获取当前套餐信息和剩余配额。"""
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    if not tenant_id:
        return ApiResponse.error(code=400, message="租户信息缺失")

    plan_info = await billing_service.get_plan_info(db, tenant_id)
    return ApiResponse.success(data=plan_info)

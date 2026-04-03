"""Audit Log API — 审计日志查询与导出。"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse, PageResponse
from app.services.audit_service import audit_service

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=ApiResponse[PageResponse])
async def list_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    log_type: str = Query(None, description="日志类型: chat, mcp, plugin, rag"),
    user_id: str = Query(None, description="用户ID"),
    start_date: str = Query(None, description="开始日期 ISO格式"),
    end_date: str = Query(None, description="结束日期 ISO格式"),
    status: str = Query(None, description="状态: success, error"),
    action: str = Query(None, description="操作动作关键词"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """分页查询审计日志，支持多种过滤条件。"""
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    if not tenant_id:
        return ApiResponse.error(code=400, message="租户信息缺失")

    result = await audit_service.get_audit_logs(
        db=db,
        tenant_id=tenant_id,
        page=page,
        size=size,
        log_type=log_type,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        action=action,
    )
    return ApiResponse.success(data=result)


@router.get("/export")
async def export_audit_logs(
    log_type: str = Query(None),
    user_id: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """导出审计日志为 CSV 文件。"""
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    if not tenant_id:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"code": 400, "message": "租户信息缺失", "data": None},
        )

    csv_content = await audit_service.export_csv(
        db=db,
        tenant_id=tenant_id,
        log_type=log_type,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )

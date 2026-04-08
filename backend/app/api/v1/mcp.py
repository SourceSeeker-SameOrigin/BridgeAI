import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.security import get_current_user
from app.mcp.gateway import mcp_gateway
from app.models.mcp import McpConnector
from app.models.user import User
from app.schemas.common import ApiResponse, PageResponse
from app.schemas.mcp import (
    ConnectorCreate,
    ConnectorResponse,
    ConnectorUpdate,
    ToolExecuteRequest,
    ToolExecuteResponse,
    ToolResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["MCP Connectors"])


def _connector_to_response(connector: McpConnector) -> ConnectorResponse:
    return ConnectorResponse(
        id=str(connector.id),
        name=connector.name,
        description=connector.description,
        connector_type=connector.connector_type,
        endpoint_url=connector.endpoint_url,
        is_active=connector.is_active,
        created_at=connector.created_at.isoformat(),
        updated_at=connector.updated_at.isoformat(),
    )


async def _get_connector_or_404(
    connector_id: str, db: AsyncSession, tenant_id: object = None
) -> McpConnector:
    query = select(McpConnector).where(McpConnector.id == connector_id)
    if tenant_id is not None:
        query = query.where(McpConnector.tenant_id == tenant_id)
    result = await db.execute(query)
    connector = result.scalar_one_or_none()
    if connector is None:
        raise NotFoundException(message="Connector not found")
    return connector


async def _ensure_registered(connector: McpConnector) -> None:
    """Ensure the connector is registered in the gateway (lazy init)."""
    cid = str(connector.id)
    try:
        mcp_gateway._get_connector(cid)
    except ValueError:
        # Build config from DB fields
        config = {
            "connector_type": connector.connector_type,
            "endpoint_url": connector.endpoint_url,
            **(connector.auth_config or {}),
        }
        await mcp_gateway.register_connector(cid, config)


# ------------------------------------------------------------------
# CRUD endpoints (unchanged logic, refactored slightly)
# ------------------------------------------------------------------

@router.post("", response_model=ApiResponse[ConnectorResponse])
async def create_connector(
    request: ConnectorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    # Merge config into auth_config for storage
    auth_config = request.auth_config or {}
    if request.config:
        auth_config.update(request.config)

    connector = McpConnector(
        tenant_id=current_user.tenant_id,
        name=request.name,
        description=request.description,
        connector_type=request.connector_type,
        endpoint_url=request.endpoint_url,
        auth_config=auth_config,
        capabilities=request.capabilities or [],
    )
    db.add(connector)
    await db.flush()
    return ApiResponse.success(data=_connector_to_response(connector))


@router.get("", response_model=ApiResponse[PageResponse[ConnectorResponse]])
async def list_connectors(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    query = select(McpConnector).where(
        McpConnector.is_active.is_(True),
        McpConnector.tenant_id == current_user.tenant_id,
    )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        query.offset((page - 1) * size).limit(size).order_by(McpConnector.created_at.desc())
    )
    items = [_connector_to_response(c) for c in result.scalars().all()]
    pages = (total + size - 1) // size

    return ApiResponse.success(
        data=PageResponse(items=items, total=total, page=page, size=size, pages=pages)
    )


@router.get("/{connector_id}", response_model=ApiResponse[ConnectorResponse])
async def get_connector(
    connector_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    connector = await _get_connector_or_404(connector_id, db, tenant_id=current_user.tenant_id)
    return ApiResponse.success(data=_connector_to_response(connector))


@router.put("/{connector_id}", response_model=ApiResponse[ConnectorResponse])
async def update_connector(
    connector_id: str,
    request: ConnectorUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    connector = await _get_connector_or_404(connector_id, db, tenant_id=current_user.tenant_id)

    update_data = request.dict(exclude_unset=True)

    # Merge config into auth_config
    extra_config = update_data.pop("config", None)
    if extra_config:
        existing = dict(connector.auth_config or {})
        existing.update(extra_config)
        update_data["auth_config"] = existing

    for field, value in update_data.items():
        setattr(connector, field, value)

    # Force re-registration on next use
    await mcp_gateway.unregister_connector(str(connector.id))

    await db.flush()
    return ApiResponse.success(data=_connector_to_response(connector))


@router.delete("/{connector_id}", response_model=ApiResponse)
async def delete_connector(
    connector_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    connector = await _get_connector_or_404(connector_id, db, tenant_id=current_user.tenant_id)
    connector.is_active = False
    await mcp_gateway.unregister_connector(str(connector.id))
    await db.flush()
    return ApiResponse.success(message="Connector deleted")


# ------------------------------------------------------------------
# New endpoints: test / tools / execute
# ------------------------------------------------------------------

@router.post("/{connector_id}/test", response_model=ApiResponse)
async def test_connector(
    connector_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Test if a connector can connect and pass health check."""
    connector = await _get_connector_or_404(connector_id, db, tenant_id=current_user.tenant_id)
    try:
        await _ensure_registered(connector)
        healthy = await mcp_gateway.health_check(str(connector.id))
        if healthy:
            return ApiResponse.success(message="连接测试成功", data={"healthy": True})
        return ApiResponse.error(code=503, message="连接器健康检查失败", data={"healthy": False})
    except Exception as exc:
        logger.exception("Connector test failed for %s", connector_id)
        return ApiResponse.error(code=503, message=f"连接测试失败: {exc}")


@router.get("/{connector_id}/tools", response_model=ApiResponse[list[ToolResponse]])
async def list_connector_tools(
    connector_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List all tools available on a connector."""
    connector = await _get_connector_or_404(connector_id, db, tenant_id=current_user.tenant_id)
    try:
        await _ensure_registered(connector)
        tools = await mcp_gateway.list_tools(str(connector.id))
        return ApiResponse.success(data=tools)
    except Exception as exc:
        logger.exception("Failed to list tools for connector %s", connector_id)
        raise BadRequestException(message=f"获取工具列表失败: {exc}")


@router.post("/{connector_id}/execute", response_model=ApiResponse[ToolExecuteResponse])
async def execute_connector_tool(
    connector_id: str,
    request: ToolExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Execute a tool on a connector (for testing / debugging)."""
    connector = await _get_connector_or_404(connector_id, db, tenant_id=current_user.tenant_id)
    try:
        await _ensure_registered(connector)
        result = await mcp_gateway.execute_tool(
            connector_id=str(connector.id),
            tool_name=request.tool_name,
            arguments=request.arguments,
            user_id=str(current_user.id),
            tenant_id=str(current_user.tenant_id),
            db=db,
        )
        return ApiResponse.success(
            data=ToolExecuteResponse(
                success=result["success"],
                data=result["data"],
                error=result["error"],
                duration_ms=result["duration_ms"],
            )
        )
    except Exception as exc:
        logger.exception("Tool execution failed for connector %s", connector_id)
        raise BadRequestException(message=f"工具执行失败: {exc}")

from typing import Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.templates import get_all_templates
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate
from app.schemas.common import ApiResponse, PageResponse
from app.services import agent_service

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("/templates", response_model=ApiResponse[List[Any]])
async def list_agent_templates(
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """Return available pre-built agent templates."""
    templates = get_all_templates()
    return ApiResponse.success(data=templates)


@router.post("", response_model=ApiResponse[AgentResponse])
async def create_agent(
    request: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    agent = await agent_service.create_agent(request, db, tenant_id=tenant_id)
    return ApiResponse.success(data=agent)


@router.get("", response_model=ApiResponse[PageResponse[AgentResponse]])
async def list_agents(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    result = await agent_service.list_agents(db, page=page, size=size, tenant_id=tenant_id)
    return ApiResponse.success(data=result)


@router.get("/{agent_id}", response_model=ApiResponse[AgentResponse])
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    agent = await agent_service.get_agent(agent_id, db)
    return ApiResponse.success(data=agent)


@router.put("/{agent_id}", response_model=ApiResponse[AgentResponse])
async def update_agent(
    agent_id: str,
    request: AgentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    agent = await agent_service.update_agent(agent_id, request, db)
    return ApiResponse.success(data=agent)


@router.delete("/{agent_id}", response_model=ApiResponse)
async def delete_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    await agent_service.delete_agent(agent_id, db)
    return ApiResponse.success(message="Agent deleted")

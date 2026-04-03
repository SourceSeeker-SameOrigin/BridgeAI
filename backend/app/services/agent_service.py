from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.agent import Agent
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate
from app.schemas.common import PageResponse


def _agent_to_response(agent: Agent) -> AgentResponse:
    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        description=agent.description,
        parent_agent_id=str(agent.parent_agent_id) if agent.parent_agent_id else None,
        task_key=agent.task_key,
        system_prompt=agent.system_prompt,
        knowledge_base_id=str(agent.knowledge_base_id) if agent.knowledge_base_id else None,
        model_config_data=agent.model_config_ if agent.model_config_ else None,
        tools=agent.tools if agent.tools else None,
        is_active=agent.is_active,
        version=agent.version,
        created_at=agent.created_at.isoformat(),
        updated_at=agent.updated_at.isoformat(),
    )


async def create_agent(
    request: AgentCreate, db: AsyncSession, tenant_id: Optional[str] = None
) -> AgentResponse:
    agent = Agent(
        tenant_id=tenant_id,
        name=request.name,
        description=request.description,
        parent_agent_id=request.parent_agent_id,
        task_key=request.task_key,
        system_prompt=request.system_prompt,
        knowledge_base_id=request.knowledge_base_id,
        model_config_=request.model_config_data or {},
        tools=request.tools or [],
    )
    db.add(agent)
    await db.flush()
    return _agent_to_response(agent)


async def get_agent(agent_id: str, db: AsyncSession) -> AgentResponse:
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise NotFoundException(message="Agent not found")
    return _agent_to_response(agent)


async def list_agents(
    db: AsyncSession, page: int = 1, size: int = 20, tenant_id: Optional[str] = None
) -> PageResponse[AgentResponse]:
    query = select(Agent).where(Agent.is_active.is_(True))
    if tenant_id:
        query = query.where(Agent.tenant_id == tenant_id)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * size).limit(size).order_by(Agent.created_at.desc())
    result = await db.execute(query)
    agents = result.scalars().all()

    items = [_agent_to_response(a) for a in agents]
    pages = (total + size - 1) // size

    return PageResponse(items=items, total=total, page=page, size=size, pages=pages)


async def update_agent(agent_id: str, request: AgentUpdate, db: AsyncSession) -> AgentResponse:
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise NotFoundException(message="Agent not found")

    update_data = request.dict(exclude_unset=True)

    # Map schema field names to ORM attribute names
    field_mapping = {
        "model_config_data": "model_config_",
    }

    for field, value in update_data.items():
        orm_field = field_mapping.get(field, field)
        setattr(agent, orm_field, value)

    await db.flush()
    return _agent_to_response(agent)


async def delete_agent(agent_id: str, db: AsyncSession) -> None:
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise NotFoundException(message="Agent not found")

    agent.is_active = False
    await db.flush()

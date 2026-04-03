"""Workflow CRUD service."""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.workflow import AgentWorkflow
from app.schemas.common import PageResponse
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowResponse,
    WorkflowUpdate,
)


def _workflow_to_response(wf: AgentWorkflow) -> WorkflowResponse:
    return WorkflowResponse(
        id=str(wf.id),
        name=wf.name,
        description=wf.description,
        agent_id=str(wf.agent_id) if wf.agent_id else None,
        nodes=wf.nodes or [],
        edges=wf.edges or [],
        is_active=wf.is_active,
        created_at=wf.created_at.isoformat(),
        updated_at=wf.updated_at.isoformat(),
    )


async def create_workflow(
    request: WorkflowCreate,
    db: AsyncSession,
    tenant_id: Optional[str] = None,
) -> WorkflowResponse:
    wf = AgentWorkflow(
        tenant_id=tenant_id,
        agent_id=request.agent_id,
        name=request.name,
        description=request.description,
        nodes=[n.model_dump() for n in request.nodes],
        edges=[e.model_dump() for e in request.edges],
    )
    db.add(wf)
    await db.flush()
    return _workflow_to_response(wf)


async def get_workflow(workflow_id: str, db: AsyncSession) -> WorkflowResponse:
    result = await db.execute(
        select(AgentWorkflow).where(AgentWorkflow.id == workflow_id)
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise NotFoundException(message="Workflow not found")
    return _workflow_to_response(wf)


async def get_workflow_model(workflow_id: str, db: AsyncSession) -> AgentWorkflow:
    """Return raw ORM model for executor usage."""
    result = await db.execute(
        select(AgentWorkflow).where(AgentWorkflow.id == workflow_id)
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise NotFoundException(message="Workflow not found")
    return wf


async def list_workflows(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    tenant_id: Optional[str] = None,
) -> PageResponse[WorkflowResponse]:
    query = select(AgentWorkflow).where(AgentWorkflow.is_active.is_(True))
    if tenant_id:
        query = query.where(AgentWorkflow.tenant_id == tenant_id)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * size).limit(size).order_by(
        AgentWorkflow.created_at.desc()
    )
    result = await db.execute(query)
    workflows = result.scalars().all()

    items = [_workflow_to_response(w) for w in workflows]
    pages = (total + size - 1) // size

    return PageResponse(items=items, total=total, page=page, size=size, pages=pages)


async def update_workflow(
    workflow_id: str,
    request: WorkflowUpdate,
    db: AsyncSession,
) -> WorkflowResponse:
    result = await db.execute(
        select(AgentWorkflow).where(AgentWorkflow.id == workflow_id)
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise NotFoundException(message="Workflow not found")

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "nodes" and value is not None:
            value = [n if isinstance(n, dict) else n.model_dump() for n in value]
        if field == "edges" and value is not None:
            value = [e if isinstance(e, dict) else e.model_dump() for e in value]
        setattr(wf, field, value)

    await db.flush()
    return _workflow_to_response(wf)


async def delete_workflow(workflow_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(AgentWorkflow).where(AgentWorkflow.id == workflow_id)
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise NotFoundException(message="Workflow not found")

    wf.is_active = False
    await db.flush()

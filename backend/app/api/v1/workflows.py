"""Workflow CRUD and execution API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse, PageResponse
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowExecuteRequest,
    WorkflowExecuteResponse,
    WorkflowResponse,
    WorkflowUpdate,
)
from app.services import workflow_service
from app.services.workflow_executor import execute_workflow

router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.post("", response_model=ApiResponse[WorkflowResponse])
async def create_workflow(
    request: WorkflowCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    wf = await workflow_service.create_workflow(request, db, tenant_id=tenant_id)
    return ApiResponse.success(data=wf)


@router.get("", response_model=ApiResponse[PageResponse[WorkflowResponse]])
async def list_workflows(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    result = await workflow_service.list_workflows(db, page=page, size=size, tenant_id=tenant_id)
    return ApiResponse.success(data=result)


@router.get("/{workflow_id}", response_model=ApiResponse[WorkflowResponse])
async def get_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    wf = await workflow_service.get_workflow(workflow_id, db)
    return ApiResponse.success(data=wf)


@router.put("/{workflow_id}", response_model=ApiResponse[WorkflowResponse])
async def update_workflow(
    workflow_id: str,
    request: WorkflowUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    wf = await workflow_service.update_workflow(workflow_id, request, db)
    return ApiResponse.success(data=wf)


@router.delete("/{workflow_id}", response_model=ApiResponse)
async def delete_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    await workflow_service.delete_workflow(workflow_id, db)
    return ApiResponse.success(message="Workflow deleted")


@router.post("/{workflow_id}/execute", response_model=ApiResponse[WorkflowExecuteResponse])
async def execute_workflow_endpoint(
    workflow_id: str,
    request: WorkflowExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    wf = await workflow_service.get_workflow_model(workflow_id, db)
    result = await execute_workflow(
        workflow_id=str(wf.id),
        nodes=wf.nodes or [],
        edges=wf.edges or [],
        input_text=request.input,
        variables=request.variables,
    )
    return ApiResponse.success(data=result)

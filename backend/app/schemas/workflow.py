"""Workflow request/response schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WorkflowNodePosition(BaseModel):
    x: float = 0
    y: float = 0


class WorkflowNode(BaseModel):
    id: str
    type: str  # llm_call, tool_call, condition, loop, parallel, human_input
    config: Dict[str, Any] = Field(default_factory=dict)
    position: WorkflowNodePosition = Field(default_factory=WorkflowNodePosition)


class WorkflowEdge(BaseModel):
    source: str
    target: str
    condition: Optional[str] = None


class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    agent_id: Optional[str] = None
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    agent_id: Optional[str] = None
    nodes: Optional[List[WorkflowNode]] = None
    edges: Optional[List[WorkflowEdge]] = None
    is_active: Optional[bool] = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    agent_id: Optional[str] = None
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    is_active: bool = True
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class WorkflowExecuteRequest(BaseModel):
    input: str
    variables: Dict[str, Any] = Field(default_factory=dict)


class WorkflowStepResult(BaseModel):
    node_id: str
    node_type: str
    status: str  # success, error, skipped
    output: Optional[str] = None
    error: Optional[str] = None


class WorkflowExecuteResponse(BaseModel):
    workflow_id: str
    status: str  # completed, error
    steps: List[WorkflowStepResult] = Field(default_factory=list)
    final_output: Optional[str] = None

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ConnectorCreate(BaseModel):
    name: str
    description: Optional[str] = None
    connector_type: str
    endpoint_url: str
    auth_config: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[Any]] = None
    config: Optional[Dict[str, Any]] = None


class ConnectorUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    connector_type: Optional[str] = None
    endpoint_url: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[Any]] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ConnectorResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    connector_type: str
    endpoint_url: str
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ToolExecuteRequest(BaseModel):
    """Request body for executing a tool on an MCP connector."""

    tool_name: str
    arguments: Dict[str, Any] = {}


class ToolResponse(BaseModel):
    """Single tool definition returned by list_tools."""

    name: str
    description: str
    parameters: Dict[str, Any] = {}


class ToolExecuteResponse(BaseModel):
    """Response from executing a tool."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None

"""Pydantic schemas for plugin API endpoints."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class PluginInstallRequest(BaseModel):
    plugin_name: str


class InstalledPluginUpdate(BaseModel):
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class PluginExecuteRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}


class PluginToolResponse(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = {}


class PluginMetadataResponse(BaseModel):
    name: str
    display_name: str
    description: str
    version: str
    category: str
    tools: List[PluginToolResponse] = []
    prompt_templates: List[Dict[str, str]] = []


class InstalledPluginResponse(BaseModel):
    id: str
    plugin_name: str
    plugin_version: str
    description: Optional[str] = None
    config: Dict[str, Any] = {}
    is_active: bool = True
    installed_by: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True

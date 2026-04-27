from typing import Any, Dict, List, Optional

from pydantic import BaseModel, model_validator


class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_agent_id: Optional[str] = None
    task_key: Optional[str] = None
    system_prompt: Optional[str] = None
    model_config_data: Optional[Dict[str, Any]] = None  # maps to model_config JSONB
    tools: Optional[List[Any]] = None
    knowledge_base_id: Optional[str] = None
    # Convenience fields — merged into model_config_data if provided
    model_provider: Optional[str] = None
    model_name: Optional[str] = None

    @model_validator(mode="after")
    def merge_model_fields(self) -> "AgentCreate":
        """Merge top-level model_provider/model_name into model_config_data."""
        if self.model_provider or self.model_name:
            config = dict(self.model_config_data) if self.model_config_data else {}
            if self.model_provider:
                config["model_provider"] = self.model_provider
            if self.model_name:
                config["model_name"] = self.model_name
            self.model_config_data = config
        return self


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_agent_id: Optional[str] = None
    task_key: Optional[str] = None
    system_prompt: Optional[str] = None
    model_config_data: Optional[Dict[str, Any]] = None
    tools: Optional[List[Any]] = None
    knowledge_base_id: Optional[str] = None
    is_active: Optional[bool] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    parent_agent_id: Optional[str] = None
    task_key: Optional[str] = None
    system_prompt: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    model_config_data: Optional[Dict[str, Any]] = None
    tools: Optional[List[Any]] = None
    is_active: bool
    version: int = 1
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

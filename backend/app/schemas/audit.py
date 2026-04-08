from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    tenant_id: str
    connector_id: Optional[str] = None
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    log_type: str = "mcp"  # mcp, chat, plugin
    action: str
    request_payload: Optional[Dict[str, Any]] = None
    response_payload: Optional[Dict[str, Any]] = None
    status: str = "success"
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    model_used: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    created_at: str

    class Config:
        from_attributes = True


class AuditLogFilter(BaseModel):
    log_type: Optional[str] = None
    user_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None
    action: Optional[str] = None

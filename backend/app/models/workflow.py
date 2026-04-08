"""Workflow model — stores visual workflow definitions for agents."""

from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import BaseModel


class AgentWorkflow(BaseModel):
    __tablename__ = "agent_workflows"
    __table_args__ = (
        Index("idx_agent_workflows_agent_id", "agent_id"),
        Index("idx_agent_workflows_tenant_id", "tenant_id"),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    nodes = Column(JSONB, default=list, nullable=False)
    edges = Column(JSONB, default=list, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

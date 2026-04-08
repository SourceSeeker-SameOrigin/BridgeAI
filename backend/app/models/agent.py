from sqlalchemy import Boolean, Column, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Agent(BaseModel):
    __tablename__ = "agents"
    __table_args__ = (
        Index("idx_agents_tenant_id", "tenant_id"),
        Index("idx_agents_parent_id", "parent_agent_id"),
        Index("idx_agents_task_key", "task_key"),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    parent_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    task_key = Column(String(128), nullable=True)
    system_prompt = Column(Text, nullable=True)
    knowledge_base_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True)
    model_config_ = Column("model_config", JSONB, default=dict, nullable=False)
    tools = Column(JSONB, default=list, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)

    parent_agent = relationship("Agent", remote_side="Agent.id", backref="sub_agents")


class AgentMemory(BaseModel):
    __tablename__ = "agent_memories"
    __table_args__ = (
        Index("idx_agent_memories_agent_id", "agent_id"),
        Index("idx_agent_memories_tenant_id", "tenant_id"),
        Index("idx_agent_memories_user_id", "user_id"),
        Index("idx_agent_memories_type", "memory_type"),
    )

    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content = Column(Text, nullable=False)
    memory_type = Column(String(64), default="episodic", nullable=False)
    importance = Column(Float, default=0.5, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict, nullable=False)

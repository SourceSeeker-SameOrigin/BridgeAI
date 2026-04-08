from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, BaseModelCreatedOnly


class McpConnector(BaseModel):
    __tablename__ = "mcp_connectors"
    __table_args__ = (
        Index("idx_mcp_connectors_tenant_id", "tenant_id"),
        Index("idx_mcp_connectors_type", "connector_type"),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    connector_type = Column(String(64), nullable=False)
    endpoint_url = Column(Text, nullable=False)
    auth_config = Column(JSONB, default=dict, nullable=False)
    capabilities = Column(JSONB, default=list, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    audit_logs = relationship("McpAuditLog", back_populates="connector", lazy="selectin")


class McpAuditLog(BaseModelCreatedOnly):
    __tablename__ = "mcp_audit_logs"
    __table_args__ = (
        Index("idx_mcp_audit_logs_connector_id", "connector_id"),
        Index("idx_mcp_audit_logs_tenant_id", "tenant_id"),
        Index("idx_mcp_audit_logs_action", "action"),
        Index("idx_mcp_audit_logs_created_at", "created_at"),
    )

    connector_id = Column(UUID(as_uuid=True), ForeignKey("mcp_connectors.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(128), nullable=False)
    request_payload = Column(JSONB, nullable=True)
    response_payload = Column(JSONB, nullable=True)
    status = Column(String(64), default="success", nullable=False)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    connector = relationship("McpConnector", back_populates="audit_logs")

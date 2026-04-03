import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, BaseModel


class InstalledPlugin(BaseModel):
    __tablename__ = "installed_plugins"
    __table_args__ = (
        UniqueConstraint("tenant_id", "plugin_name", name="installed_plugins_tenant_id_plugin_name_key"),
        Index("idx_installed_plugins_tenant_id", "tenant_id"),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    plugin_name = Column(String(255), nullable=False)
    plugin_version = Column(String(64), default="1.0.0", nullable=False)
    description = Column(Text, nullable=True)
    config = Column(JSONB, default=dict, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    installed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class UsageRecord(Base):
    """Usage records use recorded_at instead of created_at/updated_at."""

    __tablename__ = "usage_records"
    __table_args__ = (
        Index("idx_usage_records_tenant_id", "tenant_id"),
        Index("idx_usage_records_user_id", "user_id"),
        Index("idx_usage_records_resource_type", "resource_type"),
        Index("idx_usage_records_recorded_at", "recorded_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    resource_type = Column(String(64), nullable=False)
    quantity = Column(Float, default=0, nullable=False)
    unit = Column(String(32), default="tokens", nullable=False)
    model = Column(String(128), nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict, nullable=False)
    recorded_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

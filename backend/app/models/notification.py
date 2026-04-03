from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelCreatedOnly


class Notification(BaseModelCreatedOnly):
    """System notification for users."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notifications_tenant_id", "tenant_id"),
        Index("idx_notifications_user_id", "user_id"),
        Index("idx_notifications_is_read", "is_read"),
        Index("idx_notifications_type", "type"),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)
    type = Column(String(50), default="info", nullable=False)  # info/success/warning/error
    is_read = Column(Boolean, default=False, nullable=False)

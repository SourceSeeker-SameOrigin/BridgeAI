"""Payment order model."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import BaseModel


class PaymentOrder(BaseModel):
    __tablename__ = "payment_orders"
    __table_args__ = (
        Index("idx_payment_orders_tenant_id", "tenant_id"),
        Index("idx_payment_orders_status", "status"),
        Index("idx_payment_orders_order_no", "order_no", unique=True),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    order_no = Column(String(64), unique=True, nullable=False)
    plan = Column(String(64), nullable=False)
    months = Column(Integer, default=1, nullable=False)
    amount = Column(Float, default=0.0, nullable=False)
    currency = Column(String(16), default="CNY", nullable=False)
    status = Column(String(32), default="pending", nullable=False)  # pending / paid / cancelled / refunded
    payment_method = Column(String(32), nullable=True)  # wechat / alipay / stripe
    paid_at = Column(DateTime(timezone=True), nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict, nullable=False)

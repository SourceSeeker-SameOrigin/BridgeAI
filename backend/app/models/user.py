from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, BaseModelCreatedOnly


class Tenant(BaseModel):
    __tablename__ = "tenants"
    __table_args__ = (
        Index("idx_tenants_slug", "slug"),
        Index("idx_tenants_is_active", "is_active"),
    )

    name = Column(String(255), nullable=False)
    slug = Column(String(128), unique=True, nullable=False)
    plan = Column(String(64), default="free", nullable=False)
    config = Column(JSONB, default=dict, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class User(BaseModel):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="users_tenant_id_email_key"),
        UniqueConstraint("tenant_id", "username", name="users_tenant_id_username_key"),
        Index("idx_users_tenant_id", "tenant_id"),
        Index("idx_users_email", "email"),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    username = Column(String(128), nullable=False)
    email = Column(String(255), nullable=False)
    hashed_password = Column("password_hash", String(255), nullable=False)
    role = Column(String(64), default="user", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # WeChat Open Platform (微信开放平台扫码登录)
    wechat_openid = Column(String(128), unique=True, nullable=True, index=True)
    wechat_unionid = Column(String(128), nullable=True)

    tenant = relationship("Tenant", backref="users", lazy="selectin")
    api_keys = relationship("ApiKey", back_populates="user", lazy="selectin")


class ApiKey(BaseModelCreatedOnly):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index("idx_api_keys_tenant_id", "tenant_id"),
        Index("idx_api_keys_key_hash", "key_hash"),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)
    prefix = Column(String(16), nullable=False)
    scopes = Column(JSONB, default=list, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="api_keys")

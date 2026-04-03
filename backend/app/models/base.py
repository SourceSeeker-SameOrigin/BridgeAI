import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Mixin for models with both created_at and updated_at."""

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class CreatedAtMixin:
    """Mixin for models with only created_at (no updated_at)."""

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class BaseModel(Base, TimestampMixin):
    """Abstract base with id, created_at, updated_at for most models."""

    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class BaseModelCreatedOnly(Base, CreatedAtMixin):
    """Abstract base with id, created_at only (no updated_at)."""

    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

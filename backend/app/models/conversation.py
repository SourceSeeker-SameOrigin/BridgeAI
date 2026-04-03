from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, BaseModelCreatedOnly


class Conversation(BaseModel):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("idx_conversations_tenant_id", "tenant_id"),
        Index("idx_conversations_user_id", "user_id"),
        Index("idx_conversations_agent_id", "agent_id"),
        Index("idx_conversations_status", "status"),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(512), nullable=True)
    status = Column(String(64), default="active", nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict, nullable=False)

    user = relationship("User", backref="conversations", lazy="selectin")
    agent = relationship("Agent", backref="conversations", lazy="selectin")
    messages = relationship("Message", back_populates="conversation", lazy="selectin")


class Message(BaseModelCreatedOnly):
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_messages_conversation_id", "conversation_id"),
        Index("idx_messages_tenant_id", "tenant_id"),
        Index("idx_messages_role", "role"),
        Index("idx_messages_intent", "intent"),
        Index("idx_messages_created_at", "created_at"),
    )

    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    intent = Column(String(128), nullable=True)
    emotion = Column(String(128), nullable=True)
    task_key = Column(String(128), nullable=True)
    model_used = Column(String(128), nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    first_token_ms = Column(Integer, nullable=True)
    system_prompt_snapshot = Column(Text, nullable=True)
    token_input = Column(Integer, default=0, nullable=False)
    token_output = Column(Integer, default=0, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
    intents = relationship("MessageIntent", back_populates="message", lazy="selectin")
    emotions = relationship("MessageEmotion", back_populates="message", lazy="selectin")
    ratings = relationship("MessageRating", back_populates="message", lazy="selectin")


class MessageIntent(BaseModelCreatedOnly):
    __tablename__ = "message_intents"
    __table_args__ = (
        Index("idx_message_intents_message_id", "message_id"),
        Index("idx_message_intents_intent", "intent"),
    )

    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    intent = Column(String(128), nullable=False)
    confidence = Column(Float, default=0.0, nullable=False)

    message = relationship("Message", back_populates="intents")


class MessageEmotion(BaseModelCreatedOnly):
    __tablename__ = "message_emotions"
    __table_args__ = (
        Index("idx_message_emotions_message_id", "message_id"),
        Index("idx_message_emotions_emotion", "emotion"),
    )

    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    emotion = Column(String(128), nullable=False)
    confidence = Column(Float, default=0.0, nullable=False)

    message = relationship("Message", back_populates="emotions")


class MessageRating(BaseModelCreatedOnly):
    __tablename__ = "message_ratings"
    __table_args__ = (
        Index("idx_message_ratings_message_id", "message_id"),
    )

    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rating = Column(Integer, nullable=False)
    feedback = Column(Text, nullable=True)

    message = relationship("Message", back_populates="ratings")

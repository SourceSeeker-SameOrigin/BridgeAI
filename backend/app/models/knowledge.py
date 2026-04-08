from sqlalchemy import BigInteger, Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class KnowledgeBase(BaseModel):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        Index("idx_knowledge_bases_tenant_id", "tenant_id"),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    embedding_model = Column(String(128), default="bge-m3", nullable=False)
    chunk_size = Column(Integer, default=512, nullable=False)
    chunk_overlap = Column(Integer, default=64, nullable=False)
    status = Column(String(64), default="active", nullable=False)
    config = Column(JSONB, default=dict, nullable=False)

    documents = relationship("KnowledgeDocument", back_populates="knowledge_base", lazy="selectin")


class KnowledgeDocument(BaseModel):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("idx_knowledge_documents_kb_id", "knowledge_base_id"),
        Index("idx_knowledge_documents_tenant_id", "tenant_id"),
        Index("idx_knowledge_documents_status", "status"),
    )

    knowledge_base_id = Column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(512), nullable=False)
    file_type = Column(String(64), nullable=False)
    file_size = Column(BigInteger, default=0, nullable=False)
    file_url = Column(Text, nullable=True)
    storage_key = Column(String(1024), nullable=True, comment="MinIO object key")
    status = Column(String(64), default="pending", nullable=False)
    chunk_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict, nullable=False)

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("KnowledgeChunk", back_populates="document", lazy="selectin")


class KnowledgeChunk(BaseModel):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index("idx_knowledge_chunks_doc_id", "document_id"),
        Index("idx_knowledge_chunks_kb_id", "knowledge_base_id"),
        Index("idx_knowledge_chunks_tenant_id", "tenant_id"),
    )

    document_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False)
    knowledge_base_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, default=0, nullable=False)
    token_count = Column(Integer, default=0, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict, nullable=False)

    document = relationship("KnowledgeDocument", back_populates="chunks")

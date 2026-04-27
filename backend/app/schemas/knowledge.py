from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    embedding_model: str = "bge-m3"
    chunk_size: int = 512
    chunk_overlap: int = 64
    config: Optional[Dict[str, Any]] = None


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    embedding_model: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    status: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    status: str = "active"
    config: Dict[str, Any] = {}
    document_count: int = 0
    total_size: int = 0
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: str
    knowledge_base_id: str
    filename: str
    file_type: str
    file_size: int = 0
    status: str
    chunk_count: int
    storage_key: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query text")
    top_k: int = Field(5, ge=1, le=50, description="Number of results to return")


class SearchResultItem(BaseModel):
    chunk_id: str
    content: str
    similarity: float
    chunk_index: int
    document_id: str


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem] = []
    total: int = 0

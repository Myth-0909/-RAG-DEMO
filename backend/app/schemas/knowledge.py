from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    domain_id: Optional[int] = None
    embedding_model: Optional[str] = None
    chunk_strategy: str = "recursive"


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    domain_id: Optional[int] = None
    embedding_model: Optional[str] = None
    chunk_strategy: Optional[str] = None
    is_active: Optional[bool] = None


class KnowledgeBaseResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    domain_id: Optional[int] = None
    embedding_model: Optional[str] = None
    chunk_strategy: str
    is_active: bool
    document_count: Optional[int] = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: int
    knowledge_base_id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: Optional[int] = None
    status: str
    chunk_count: int
    metadata_json: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChunkMetadata(BaseModel):
    author: Optional[str] = None
    style: Optional[str] = None
    scene: Optional[str] = None
    content: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class UploadRequest(BaseModel):
    knowledge_base_id: int
    metadata_json: Optional[Dict[str, Any]] = None
    chunk_strategy: Optional[str] = None


class ChunkResponse(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    chunk_text: str
    parent_text: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    token_count: Optional[int] = None

    class Config:
        from_attributes = True


class DomainCreate(BaseModel):
    name: str
    description: Optional[str] = None
    system_prompt: Optional[str] = None


class DomainUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None


class DomainResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    question: str
    knowledge_base_ids: List[int]
    domain_id: Optional[int] = None
    top_k: int = 5


class ChatSource(BaseModel):
    text: str
    document_name: str
    chunk_index: int
    score: float
    metadata: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSource]

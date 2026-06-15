from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.database import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    domain_id = Column(Integer, ForeignKey("domains.id"), nullable=True)
    embedding_model = Column(String(100), nullable=True)
    chunk_strategy = Column(String(50), default="recursive")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")
    domain = relationship("Domain", back_populates="knowledge_bases")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_size = Column(Integer, nullable=True)
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    chunk_count = Column(Integer, default=0)
    metadata_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    parent_text = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    milvus_id = Column(String(100), nullable=True)
    token_count = Column(Integer, nullable=True)

    document = relationship("Document", back_populates="chunks")


class Domain(Base):
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    knowledge_bases = relationship("KnowledgeBase", back_populates="domain")

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.database import Base


class ProcessingTask(Base):
    __tablename__ = "processing_tasks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    current_step = Column(String(50), nullable=True)
    events = Column(JSON, default=list)
    error_message = Column(Text, nullable=True)
    result_summary = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    document = relationship("Document", backref="processing_tasks")
    knowledge_base = relationship("KnowledgeBase")

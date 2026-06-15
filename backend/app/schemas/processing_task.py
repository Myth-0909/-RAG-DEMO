from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class ProcessingTaskResponse(BaseModel):
    id: int
    document_id: int
    knowledge_base_id: int
    status: str
    current_step: Optional[str] = None
    events: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None
    result_summary: Optional[Dict[str, Any]] = None
    document_name: Optional[str] = None
    knowledge_base_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProcessingTaskListResponse(BaseModel):
    id: int
    document_id: int
    knowledge_base_id: int
    status: str
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    document_name: Optional[str] = None
    knowledge_base_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

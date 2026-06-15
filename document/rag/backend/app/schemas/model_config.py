from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ModelConfigCreate(BaseModel):
    name: str
    base_url: str
    model_name: str
    api_key: str
    config_type: str = "llm"


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    config_type: Optional[str] = None
    is_active: Optional[bool] = None


class ModelConfigResponse(BaseModel):
    id: int
    name: str
    base_url: str
    model_name: str
    api_key: str
    config_type: str
    is_active: bool
    is_current: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ModelConfigHistoryResponse(BaseModel):
    id: int
    config_id: int
    action: str
    name: str
    base_url: str
    model_name: str
    api_key: str
    config_type: str
    changed_by: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PermissionBase(BaseModel):
    code: str
    name: str
    type: str  # menu, button, api
    parent_id: Optional[int] = None
    path: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    parent_id: Optional[int] = None
    path: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class PermissionResponse(PermissionBase):
    id: int
    children: Optional[List["PermissionResponse"]] = None

    class Config:
        from_attributes = True


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    permission_ids: Optional[List[int]] = None


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[int]] = None


class RoleResponse(RoleBase):
    id: int
    is_system: bool
    created_at: Optional[datetime] = None
    permissions: Optional[List[PermissionResponse]] = None

    class Config:
        from_attributes = True

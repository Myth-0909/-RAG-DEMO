from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.user import User
from app.models.role import Role, Permission, UserRole
from app.schemas.role import RoleCreate, RoleUpdate, RoleResponse, PermissionCreate, PermissionUpdate, PermissionResponse
from app.core.deps import get_current_superuser

router = APIRouter(prefix="/roles", tags=["角色管理"])


@router.get("/", response_model=List[RoleResponse])
def list_roles(db: Session = Depends(get_db), _user: User = Depends(get_current_superuser)):
    roles = db.query(Role).all()
    return roles


@router.post("/", response_model=RoleResponse)
def create_role(
    role_in: RoleCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_superuser),
):
    existing = db.query(Role).filter(Role.name == role_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="角色名已存在")

    role = Role(name=role_in.name, description=role_in.description)
    db.add(role)
    db.flush()

    if role_in.permission_ids:
        perms = db.query(Permission).filter(Permission.id.in_(role_in.permission_ids)).all()
        role.permissions = perms

    db.commit()
    db.refresh(role)
    return role


@router.put("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: int,
    role_in: RoleUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_superuser),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=400, detail="系统角色不可修改")

    if role_in.name is not None:
        role.name = role_in.name
    if role_in.description is not None:
        role.description = role_in.description
    if role_in.permission_ids is not None:
        perms = db.query(Permission).filter(Permission.id.in_(role_in.permission_ids)).all()
        role.permissions = perms

    db.commit()
    db.refresh(role)
    return role


@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_superuser),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=400, detail="系统角色不可删除")
    db.delete(role)
    db.commit()
    return {"detail": "删除成功"}


# --- Permissions ---
@router.get("/permissions/tree", response_model=List[PermissionResponse])
def get_permission_tree(db: Session = Depends(get_db), _user: User = Depends(get_current_superuser)):
    all_perms = db.query(Permission).order_by(Permission.sort_order).all()

    perm_map = {}
    for p in all_perms:
        resp = PermissionResponse.model_validate(p)
        resp.children = []
        perm_map[p.id] = resp

    roots = []
    for p in all_perms:
        if p.parent_id and p.parent_id in perm_map:
            perm_map[p.parent_id].children.append(perm_map[p.id])
        else:
            roots.append(perm_map[p.id])

    return roots


@router.post("/permissions", response_model=PermissionResponse)
def create_permission(
    perm_in: PermissionCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_superuser),
):
    perm = Permission(**perm_in.model_dump())
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


@router.put("/permissions/{perm_id}", response_model=PermissionResponse)
def update_permission(
    perm_id: int,
    perm_in: PermissionUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_superuser),
):
    perm = db.query(Permission).filter(Permission.id == perm_id).first()
    if not perm:
        raise HTTPException(status_code=404, detail="权限不存在")

    for key, value in perm_in.model_dump(exclude_unset=True).items():
        setattr(perm, key, value)

    db.commit()
    db.refresh(perm)
    return perm


@router.delete("/permissions/{perm_id}")
def delete_permission(
    perm_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_superuser),
):
    perm = db.query(Permission).filter(Permission.id == perm_id).first()
    if not perm:
        raise HTTPException(status_code=404, detail="权限不存在")
    db.delete(perm)
    db.commit()
    return {"detail": "删除成功"}

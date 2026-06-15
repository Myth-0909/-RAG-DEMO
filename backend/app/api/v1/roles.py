from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.user import User
from app.models.role import Role, Permission, UserRole
from app.schemas.role import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    PermissionCreate,
    PermissionUpdate,
    PermissionResponse,
    PermissionSortItem,
)
from app.core.deps import get_current_superuser, get_current_user

router = APIRouter(prefix="/roles", tags=["角色管理"])

DEFAULT_MENU_PERMISSIONS = [
    ("system", "系统管理", None, "/system", "SettingOutlined", 1),
    ("system:user", "用户管理", "system", "/system/users", "UserOutlined", 2),
    ("system:role", "角色管理", "system", "/system/roles", "TeamOutlined", 3),
    ("system:menu", "菜单管理", "system", "/system/menus", "MenuOutlined", 4),
    ("knowledge", "知识库管理", None, "/knowledge", "DatabaseOutlined", 5),
    ("chat", "智能问答", None, "/chat", "MessageOutlined", 6),
    ("domain", "专业领域", None, "/domain", "GlobalOutlined", 7),
    ("model_config", "模型配置", None, "/model-config", "RobotOutlined", 8),
    ("processing_tasks", "处理任务", None, "/processing-tasks", "ThunderboltOutlined", 9),
]


def build_permission_tree(permissions: List[Permission]) -> List[PermissionResponse]:
    perm_map = {}
    for permission in permissions:
        response = PermissionResponse.model_validate(permission)
        response.children = []
        perm_map[permission.id] = response

    roots = []
    for permission in permissions:
        if permission.parent_id and permission.parent_id in perm_map:
            perm_map[permission.parent_id].children.append(perm_map[permission.id])
        else:
            roots.append(perm_map[permission.id])

    return roots


def ensure_default_menu_permissions(db: Session) -> None:
    existing_permissions = {
        permission.code: permission
        for permission in db.query(Permission).filter(
            Permission.code.in_([item[0] for item in DEFAULT_MENU_PERMISSIONS])
        )
    }
    changed = False

    for code, name, parent_code, path, icon, sort_order in DEFAULT_MENU_PERMISSIONS:
        parent_id = existing_permissions[parent_code].id if parent_code and parent_code in existing_permissions else None
        permission = existing_permissions.get(code)

        if permission is None:
            permission = Permission(
                code=code,
                name=name,
                type="menu",
                parent_id=parent_id,
                path=path,
                icon=icon,
                sort_order=sort_order,
                is_active=True,
            )
            db.add(permission)
            db.flush()
            existing_permissions[code] = permission
            changed = True
            continue

        if permission.type != "menu":
            permission.type = "menu"
            changed = True
        if permission.path is None:
            permission.path = path
            changed = True
        if permission.icon is None:
            permission.icon = icon
            changed = True

    admin_role = db.query(Role).filter(Role.name == "管理员").first()
    if admin_role:
        admin_permission_ids = {permission.id for permission in admin_role.permissions}
        for permission in existing_permissions.values():
            if permission.id not in admin_permission_ids:
                admin_role.permissions.append(permission)
                changed = True

    if changed:
        db.commit()


def validate_permission_parent(
    db: Session,
    permission_id: Optional[int],
    parent_id: Optional[int],
) -> None:
    if parent_id is None:
        return
    if permission_id is not None and parent_id == permission_id:
        raise HTTPException(status_code=400, detail="不能选择自己作为上级")

    parent = db.query(Permission).filter(Permission.id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="上级菜单不存在")

    current_parent_id = parent.parent_id
    visited = {parent_id}
    while current_parent_id is not None:
        if permission_id is not None and current_parent_id == permission_id:
            raise HTTPException(status_code=400, detail="不能选择子菜单作为上级")
        if current_parent_id in visited:
            raise HTTPException(status_code=400, detail="菜单层级存在循环")
        visited.add(current_parent_id)
        ancestor = db.query(Permission).filter(Permission.id == current_parent_id).first()
        current_parent_id = ancestor.parent_id if ancestor else None


def validate_reorder_cycles(db: Session, items: List[PermissionSortItem]) -> None:
    parent_by_id = {
        permission.id: permission.parent_id
        for permission in db.query(Permission).all()
    }
    for item in items:
        parent_by_id[item.id] = item.parent_id

    for item in items:
        seen = {item.id}
        parent_id = parent_by_id.get(item.id)
        while parent_id is not None:
            if parent_id in seen:
                raise HTTPException(status_code=400, detail="菜单层级存在循环")
            seen.add(parent_id)
            parent_id = parent_by_id.get(parent_id)


@router.get("/", response_model=List[RoleResponse])
def list_roles(db: Session = Depends(get_db), _user: User = Depends(get_current_superuser)):
    ensure_default_menu_permissions(db)
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
    ensure_default_menu_permissions(db)
    all_perms = db.query(Permission).order_by(Permission.sort_order).all()
    return build_permission_tree(all_perms)


@router.get("/permissions/menus", response_model=List[PermissionResponse])
def get_visible_menu_tree(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_default_menu_permissions(db)
    all_menus = (
        db.query(Permission)
        .filter(Permission.type == "menu", Permission.is_active.is_(True))
        .order_by(Permission.sort_order)
        .all()
    )

    if current_user.is_superuser:
        return build_permission_tree(all_menus)

    allowed_codes = set()
    for user_role in current_user.roles:
        if user_role.role:
            for permission in user_role.role.permissions:
                if permission.is_active:
                    allowed_codes.add(permission.code)

    menu_by_id = {menu.id: menu for menu in all_menus}
    visible_ids = set()

    for menu in all_menus:
        if menu.code not in allowed_codes:
            continue
        current = menu
        while current:
            visible_ids.add(current.id)
            current = menu_by_id.get(current.parent_id) if current.parent_id else None

    visible_menus = [menu for menu in all_menus if menu.id in visible_ids]
    return build_permission_tree(visible_menus)


@router.post("/permissions", response_model=PermissionResponse)
def create_permission(
    perm_in: PermissionCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_superuser),
):
    existing = db.query(Permission).filter(Permission.code == perm_in.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="权限编码已存在")

    validate_permission_parent(db, None, perm_in.parent_id)
    perm = Permission(**perm_in.model_dump())
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


@router.put("/permissions/reorder", response_model=List[PermissionResponse])
def reorder_permissions(
    items: List[PermissionSortItem],
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_superuser),
):
    if not items:
        return get_permission_tree(db, _user)

    item_ids = [item.id for item in items]
    if len(item_ids) != len(set(item_ids)):
        raise HTTPException(status_code=400, detail="存在重复的菜单项")

    permissions = db.query(Permission).filter(Permission.id.in_(item_ids)).all()
    if len(permissions) != len(item_ids):
        raise HTTPException(status_code=404, detail="部分菜单项不存在")
    validate_reorder_cycles(db, items)

    permission_map = {permission.id: permission for permission in permissions}
    for item in items:
        if item.parent_id == item.id:
            raise HTTPException(status_code=400, detail="菜单不能作为自己的上级")
        if item.parent_id is not None and item.parent_id not in permission_map:
            parent = db.query(Permission).filter(Permission.id == item.parent_id).first()
            if not parent:
                raise HTTPException(status_code=404, detail="上级菜单不存在")

        permission = permission_map[item.id]
        permission.parent_id = item.parent_id
        permission.sort_order = item.sort_order

    db.commit()
    return get_permission_tree(db, _user)


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

    update_data = perm_in.model_dump(exclude_unset=True)
    if "code" in update_data:
        existing = db.query(Permission).filter(
            Permission.code == update_data["code"],
            Permission.id != perm_id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="权限编码已存在")
    if "parent_id" in update_data:
        validate_permission_parent(db, perm_id, update_data["parent_id"])

    for key, value in update_data.items():
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

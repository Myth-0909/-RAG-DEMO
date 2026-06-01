from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, Token, UserCreate, UserResponse, UserUpdate, RoleBrief
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.deps import get_current_user, get_current_superuser
from app.models.role import UserRole, Role
from typing import List

router = APIRouter(prefix="/auth", tags=["认证"])


def _user_to_response(user: User, db: Session = None) -> UserResponse:
    if db is not None:
        # Fresh query for roles to avoid identity map caching
        user_roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()
        role_briefs = [RoleBrief.model_validate(ur.role) for ur in user_roles if ur.role is not None]
    else:
        role_briefs = [RoleBrief.model_validate(ur.role) for ur in user.roles if ur.role is not None]
    data = {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "created_at": user.created_at,
        "roles": role_briefs,
    }
    return UserResponse(**data)


@router.post("/login", response_model=Token)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已禁用")

    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user.id).first()
    return _user_to_response(user, db)


@router.post("/users", response_model=UserResponse)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_superuser),
):
    existing = db.query(User).filter(User.username == user_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # Validate role_ids exist
    if user_in.role_ids:
        existing_roles = db.query(Role).filter(Role.id.in_(user_in.role_ids)).all()
        found_ids = {r.id for r in existing_roles}
        invalid_ids = set(user_in.role_ids) - found_ids
        if invalid_ids:
            raise HTTPException(status_code=400, detail=f"角色不存在: {invalid_ids}")

    user = User(
        username=user_in.username,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
    )
    db.add(user)
    db.flush()

    if user_in.role_ids:
        for role_id in user_in.role_ids:
            db.add(UserRole(user_id=user.id, role_id=role_id))

    db.commit()
    new_user_id = user.id
    db.expire_all()

    user = db.query(User).filter(User.id == new_user_id).first()
    return _user_to_response(user, db)


@router.get("/users", response_model=List[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_superuser),
):
    users = db.query(User).offset(skip).limit(limit).all()
    return [_user_to_response(u, db) for u in users]


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_superuser),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.is_active is not None:
        user.is_active = user_in.is_active

    if user_in.role_ids is not None:
        db.query(UserRole).filter(UserRole.user_id == user_id).delete()
        for role_id in user_in.role_ids:
            db.add(UserRole(user_id=user_id, role_id=role_id))

    db.commit()
    db.expire_all()

    user = db.query(User).filter(User.id == user_id).first()
    return _user_to_response(user, db)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_superuser),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.delete(user)
    db.commit()
    return {"detail": "删除成功"}

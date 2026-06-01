from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, Token, UserCreate, UserResponse, UserUpdate
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.deps import get_current_user, get_current_superuser
from app.models.role import UserRole, Role
from typing import List

router = APIRouter(prefix="/auth", tags=["认证"])


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
def get_me(current_user: User = Depends(get_current_user)):
    roles = [ur.role for ur in current_user.roles]
    resp = UserResponse.model_validate(current_user)
    resp.roles = roles
    return resp


@router.post("/users", response_model=UserResponse)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_superuser),
):
    existing = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

    user = User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
    )
    db.add(user)
    db.flush()

    if user_in.role_ids:
        for role_id in user_in.role_ids:
            db.add(UserRole(user_id=user.id, role_id=role_id))

    db.commit()
    db.refresh(user)
    roles = [ur.role for ur in user.roles]
    resp = UserResponse.model_validate(user)
    resp.roles = roles
    return resp


@router.get("/users", response_model=List[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_superuser),
):
    users = db.query(User).offset(skip).limit(limit).all()
    result = []
    for u in users:
        resp = UserResponse.model_validate(u)
        resp.roles = [ur.role for ur in u.roles]
        result.append(resp)
    return result


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

    if user_in.email is not None:
        user.email = user_in.email
    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.is_active is not None:
        user.is_active = user_in.is_active

    if user_in.role_ids is not None:
        db.query(UserRole).filter(UserRole.user_id == user_id).delete()
        for role_id in user_in.role_ids:
            db.add(UserRole(user_id=user_id, role_id=role_id))

    db.commit()
    db.refresh(user)
    resp = UserResponse.model_validate(user)
    resp.roles = [ur.role for ur in user.roles]
    return resp


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

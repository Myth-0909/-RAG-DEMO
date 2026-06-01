from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table, func
from sqlalchemy.orm import relationship
from app.database import Base

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(200), nullable=True)
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    users = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # menu, button, api
    parent_id = Column(Integer, ForeignKey("permissions.id"), nullable=True)
    path = Column(String(200), nullable=True)
    icon = Column(String(50), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    parent = relationship("Permission", remote_side=[id])
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")


class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)

    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="users")

"""Create initial tables and seed data."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import engine, Base, SessionLocal
from app.models.user import User
from app.models.role import Role, Permission, UserRole
from app.models.knowledge import KnowledgeBase, Document, DocumentChunk, Domain
from app.models.model_config import ModelConfig, ModelConfigHistory
from app.core.security import get_password_hash


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if db.query(User).filter(User.username == "admin").first():
            print("Admin user already exists, skipping seed.")
            return

        # Create permissions
        perm_data = [
            # Menus
            ("system", "系统管理", "menu", None, "/system", "SettingOutlined", 1),
            ("system:user", "用户管理", "menu", "system", "/system/users", "UserOutlined", 2),
            ("system:role", "角色管理", "menu", "system", "/system/roles", "TeamOutlined", 3),
            ("system:menu", "菜单管理", "menu", "system", "/system/menus", "MenuOutlined", 4),
            ("knowledge", "知识库管理", "menu", None, "/knowledge", "DatabaseOutlined", 5),
            ("chat", "智能问答", "menu", None, "/chat", "MessageOutlined", 6),
            ("domain", "专业领域", "menu", None, "/domain", "GlobalOutlined", 7),
            ("model_config", "模型配置", "menu", None, "/model-config", "RobotOutlined", 8),
            ("processing_tasks", "处理任务", "menu", None, "/processing-tasks", "ThunderboltOutlined", 9),
            # Buttons / Operations
            ("system:user:create", "创建用户", "button", "system:user", None, None, 10),
            ("system:user:update", "编辑用户", "button", "system:user", None, None, 11),
            ("system:user:delete", "删除用户", "button", "system:user", None, None, 12),
            ("system:role:create", "创建角色", "button", "system:role", None, None, 13),
            ("system:role:update", "编辑角色", "button", "system:role", None, None, 14),
            ("system:role:delete", "删除角色", "button", "system:role", None, None, 15),
            ("knowledge:create", "创建知识库", "button", "knowledge", None, None, 20),
            ("knowledge:upload", "上传文档", "button", "knowledge", None, None, 21),
            ("knowledge:delete", "删除知识库", "button", "knowledge", None, None, 22),
            ("domain:create", "创建领域", "button", "domain", None, None, 30),
            ("domain:update", "编辑领域", "button", "domain", None, None, 31),
            ("domain:delete", "删除领域", "button", "domain", None, None, 32),
        ]

        perm_map = {}
        for code, name, ptype, parent_code, path, icon, sort in perm_data:
            parent_id = perm_map.get(parent_code) if parent_code else None
            perm = Permission(
                code=code, name=name, type=ptype,
                parent_id=parent_id, path=path, icon=icon, sort_order=sort,
            )
            db.add(perm)
            db.flush()
            perm_map[code] = perm.id

        # Create roles
        admin_role = Role(name="管理员", description="系统管理员，拥有所有权限")
        db.add(admin_role)
        db.flush()

        all_perm_ids = list(perm_map.values())
        admin_role.permissions = db.query(Permission).filter(Permission.id.in_(all_perm_ids)).all()

        user_role = Role(
            name="普通用户", description="可以使用知识库和智能问答",
        )
        db.add(user_role)
        db.flush()

        user_perm_codes = ["knowledge", "chat", "domain", "knowledge:upload"]
        user_perm_ids = [perm_map[c] for c in user_perm_codes if c in perm_map]
        user_role.permissions = db.query(Permission).filter(Permission.id.in_(user_perm_ids)).all()

        # Create admin user
        admin_user = User(
            username="admin",
            full_name="系统管理员",
            hashed_password=get_password_hash("admin123"),
            is_superuser=True,
        )
        db.add(admin_user)
        db.flush()

        db.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))

        # Create default domain
        default_domain = Domain(
            name="通用",
            description="通用知识问答",
            system_prompt="你是一个通用的知识库问答助手，能够回答各类问题。",
        )
        db.add(default_domain)

        db.commit()
        print("Seed data created successfully!")
        print("  Admin user: admin / admin123")
        print(f"  Permissions: {len(perm_data)}")
        print("  Roles: 管理员, 普通用户")
        print("  Domains: 通用")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()

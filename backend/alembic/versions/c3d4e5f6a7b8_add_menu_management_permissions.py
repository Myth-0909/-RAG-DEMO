"""add menu management permissions

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


permissions = sa.table(
    "permissions",
    sa.column("id", sa.Integer),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("type", sa.String),
    sa.column("parent_id", sa.Integer),
    sa.column("path", sa.String),
    sa.column("icon", sa.String),
    sa.column("sort_order", sa.Integer),
    sa.column("is_active", sa.Boolean),
)

roles = sa.table(
    "roles",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
)

role_permissions = sa.table(
    "role_permissions",
    sa.column("role_id", sa.Integer),
    sa.column("permission_id", sa.Integer),
)


def _scalar(connection, statement):
    return connection.execute(statement).scalar()


def _ensure_permission(connection, code, name, parent_code, path, icon, sort_order):
    permission_id = _scalar(
        connection,
        sa.select(permissions.c.id).where(permissions.c.code == code),
    )
    parent_id = None
    if parent_code:
        parent_id = _scalar(
            connection,
            sa.select(permissions.c.id).where(permissions.c.code == parent_code),
        )

    if permission_id:
        current = connection.execute(
            sa.select(
                permissions.c.type,
                permissions.c.path,
                permissions.c.icon,
            ).where(permissions.c.id == permission_id)
        ).first()
        connection.execute(
            permissions.update()
            .where(permissions.c.id == permission_id)
            .values(
                type="menu" if current.type != "menu" else current.type,
                path=path if current.path is None else current.path,
                icon=icon if current.icon is None else current.icon,
            )
        )
        return permission_id

    result = connection.execute(
        permissions.insert().values(
            code=code,
            name=name,
            type="menu",
            parent_id=parent_id,
            path=path,
            icon=icon,
            sort_order=sort_order,
            is_active=True,
        )
    )
    return result.inserted_primary_key[0]


def _grant_to_admin_role(connection, permission_id):
    admin_role_id = _scalar(
        connection,
        sa.select(roles.c.id).where(roles.c.name == "管理员"),
    )
    if not admin_role_id:
        return

    exists = _scalar(
        connection,
        sa.select(role_permissions.c.role_id).where(
            role_permissions.c.role_id == admin_role_id,
            role_permissions.c.permission_id == permission_id,
        ),
    )
    if not exists:
        connection.execute(
            role_permissions.insert().values(
                role_id=admin_role_id,
                permission_id=permission_id,
            )
        )


def upgrade():
    connection = op.get_bind()
    menu_permission_id = _ensure_permission(
        connection,
        "system:menu",
        "菜单管理",
        "system",
        "/system/menus",
        "MenuOutlined",
        4,
    )
    processing_permission_id = _ensure_permission(
        connection,
        "processing_tasks",
        "处理任务",
        None,
        "/processing-tasks",
        "ThunderboltOutlined",
        9,
    )

    _grant_to_admin_role(connection, menu_permission_id)
    _grant_to_admin_role(connection, processing_permission_id)


def downgrade():
    connection = op.get_bind()
    for code in ("system:menu", "processing_tasks"):
        permission_id = _scalar(
            connection,
            sa.select(permissions.c.id).where(permissions.c.code == code),
        )
        if permission_id:
            connection.execute(
                role_permissions.delete().where(
                    role_permissions.c.permission_id == permission_id,
                )
            )
            connection.execute(
                permissions.delete().where(permissions.c.id == permission_id)
            )

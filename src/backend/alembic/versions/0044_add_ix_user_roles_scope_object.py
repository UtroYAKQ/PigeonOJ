"""user_roles 补 (scope, object_id) 索引：团队/组织成员列表按 scope+object_id 过滤缺前导列索引

- 当前唯一约束以 user_id 开头，scope+object_id 查询走全表扫描
- 新增 ix_user_roles_scope_object 优化 TeamService._team_admin_ids、
  count_org_admins、解散清角色等高频路径

Revision ID: 0044
Revises: 0043
"""
from __future__ import annotations

from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_user_roles_scope_object",
        "user_roles",
        ["scope", "object_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_roles_scope_object", table_name="user_roles")

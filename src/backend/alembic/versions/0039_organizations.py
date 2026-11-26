"""组织模块：organizations + org_members，teams 补 org_id 外键，组织角色种子

- organizations：组织（名称全站唯一 / 简介 / 头像 / 状态 / 创建操作人署名），解散为软解散
- org_members：组织成员身份与拉人来源（PARTIAL UNIQUE 防重复在册）；组织角色经
  user_roles（scope='org'、object_id=org_id）授权，本迁移补 org_admin / org_member 种子
- teams.org_id：归属组织（新建团队必填；存量可空，由 admin 指派）

Revision ID: 0039
Revises: 0038
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

ORG_ROLE_SEEDS = [
    (
        "77777777-7777-7777-7777-777777777777",
        "org_admin",
        "组织管理员",
        "组织成员管理（拉人 / 移出 / 授管理员）、组织信息编辑、组织内创建团队",
    ),
    (
        "88888888-8888-8888-8888-888888888888",
        "org_member",
        "组织成员",
        "组织题库全量读写：创建 / 编辑 / 验题 / 发布 / 归档 / 交题",
    ),
]


def upgrade() -> None:
    now = sa.text("now()")
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("disbanded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_organizations_status", "organizations", ["status"])

    op.create_table(
        "org_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "added_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(64), nullable=True),
    )
    op.create_index(
        "uq_org_members_active",
        "org_members",
        ["org_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_org_members_user", "org_members", ["user_id"])

    # teams 补归属组织外键（新建团队经组织端点创建必填；存量可空）
    op.add_column(
        "teams", sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key("fk_teams_org", "teams", "organizations", ["org_id"], ["id"])
    op.create_index("ix_teams_org", "teams", ["org_id"])

    # 组织角色种子（固定 UUID，与 tests/conftest.py ROLE_SEEDS 对齐）
    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("description", sa.Text),
        ),
        [
            {
                "id": role_id,
                "code": code,
                "name": name,
                "description": description,
            }
            for role_id, code, name, description in ORG_ROLE_SEEDS
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM user_roles WHERE role_id IN ("
            "SELECT id FROM roles WHERE code IN ('org_admin','org_member'))"
        )
    )
    op.execute(sa.text("DELETE FROM roles WHERE code IN ('org_admin','org_member')"))
    op.drop_index("ix_teams_org", table_name="teams")
    op.drop_constraint("fk_teams_org", "teams", type_="foreignkey")
    op.drop_column("teams", "org_id")
    op.drop_index("ix_org_members_user", table_name="org_members")
    op.drop_index("uq_org_members_active", table_name="org_members")
    op.drop_table("org_members")
    op.drop_index("ix_organizations_status", table_name="organizations")
    op.drop_table("organizations")

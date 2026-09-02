"""团队模块：teams + team_members + team_member_applications，并补齐既有表 team_id 外键

- teams：团队（名称 / 简介 / 头像 / 创建人 / 状态），解散为软解散
- team_members：成员身份与入 / 退队状态（PARTIAL UNIQUE 防重复在册）
- team_member_applications：加入申请（PARTIAL UNIQUE 防重复 pending）
- 为 problems.team_id / problem_sets.team_id / contests.team_id 补 FK → teams.id
  （0018 / 0019 预留列时注明「teams 表建立后补 FK」）

Revision ID: 0022
Revises: 0021
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = sa.text("now()")
    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column(
            "creator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("disbanded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_teams_creator", "teams", ["creator_id"])
    op.create_index("ix_teams_status", "teams", ["status"])

    op.create_table(
        "team_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id"), nullable=False
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_team_members_active",
        "team_members",
        ["team_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_team_members_user", "team_members", ["user_id"])

    op.create_table(
        "team_member_applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id"), nullable=False
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("invite_token", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column(
            "reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_team_applications_pending",
        "team_member_applications",
        ["team_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_team_applications_user_status", "team_member_applications", ["user_id", "status"]
    )

    # 0018 / 0019 预留的 team_id 列补外键（teams 表建立后补 FK）
    op.create_foreign_key(
        "fk_problem_sets_team", "problem_sets", "teams", ["team_id"], ["id"]
    )
    op.create_foreign_key("fk_contests_team", "contests", "teams", ["team_id"], ["id"])

    # problems：0003 预留注释「team_id 随 teams 模块迁移补齐」——补列 + FK + 索引，
    # 并把全站可见性 CHECK 扩展为契约双分支（全站 private/public，团队 admin_visible/team_visible）
    op.add_column(
        "problems",
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key("fk_problems_team", "problems", "teams", ["team_id"], ["id"])
    op.create_index(
        "ix_problems_team_visibility_status", "problems", ["team_id", "visibility", "status"]
    )
    op.drop_constraint("ck_problems_site_visibility", "problems", type_="check")
    op.create_check_constraint(
        "ck_problems_owner_visibility",
        "problems",
        "("
        "(team_id IS NULL     AND visibility IN ('private','public')) OR"
        "(team_id IS NOT NULL AND visibility IN ('admin_visible','team_visible'))"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_problems_owner_visibility", "problems", type_="check")
    op.create_check_constraint(
        "ck_problems_site_visibility",
        "problems",
        "visibility IN ('private','public')",
    )
    op.drop_index("ix_problems_team_visibility_status", table_name="problems")
    op.drop_constraint("fk_problems_team", "problems", type_="foreignkey")
    op.drop_column("problems", "team_id")
    op.drop_constraint("fk_contests_team", "contests", type_="foreignkey")
    op.drop_constraint("fk_problem_sets_team", "problem_sets", type_="foreignkey")
    op.drop_index("ix_team_applications_user_status", table_name="team_member_applications")
    op.drop_index("uq_team_applications_pending", table_name="team_member_applications")
    op.drop_table("team_member_applications")
    op.drop_index("ix_team_members_user", table_name="team_members")
    op.drop_index("uq_team_members_active", table_name="team_members")
    op.drop_table("team_members")
    op.drop_index("ix_teams_status", table_name="teams")
    op.drop_index("ix_teams_creator", table_name="teams")
    op.drop_table("teams")

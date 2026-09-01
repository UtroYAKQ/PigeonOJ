"""题单模块：problem_sets + problem_set_items

题单（公开 / 团队）按配置顺序编排题目：
- problem_sets：标题 / 说明 / 归属（team_id NULL=全站）/ 可见性 / 生命周期（active / archived），
  CHECK 约束归属与可见性匹配（全站 public|private，团队 team）
- problem_set_items：题单内题目编排，UNIQUE(set, problem) 防重复加入，
  added_by 记录添加人；排序由 sort_order 表达，刷题不强制按序完成

团队题单（team_id 非空）随 teams 模块开放：列与 CHECK 先落齐，teams 表建立后补 FK。

Revision ID: 0018
Revises: 0017
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = sa.text("now()")
    op.create_table(
        "problem_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # FK → teams.id 随 teams 模块迁移补齐
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="public"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.CheckConstraint(
            "("
            "(team_id IS NULL     AND visibility IN ('public','private')) OR"
            "(team_id IS NOT NULL AND visibility = 'team')"
            ")",
            name="ck_problem_sets_owner_visibility",
        ),
    )
    op.create_index("ix_problem_sets_owner_status", "problem_sets", ["owner_id", "status"])
    op.create_index("ix_problem_sets_team_visibility", "problem_sets", ["team_id", "visibility"])

    op.create_table(
        "problem_set_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "problem_set_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("problem_sets.id"),
            nullable=False,
        ),
        sa.Column(
            "problem_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("problems.id"), nullable=False
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint("problem_set_id", "problem_id", name="uq_problem_set_items_set_problem"),
    )
    op.create_index("ix_problem_set_items_problem", "problem_set_items", ["problem_id"])


def downgrade() -> None:
    op.drop_index("ix_problem_set_items_problem", table_name="problem_set_items")
    op.drop_table("problem_set_items")
    op.drop_index("ix_problem_sets_team_visibility", table_name="problem_sets")
    op.drop_index("ix_problem_sets_owner_status", table_name="problem_sets")
    op.drop_table("problem_sets")

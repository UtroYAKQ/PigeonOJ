"""社区模块：solutions（用户题解）+ comments（评论）表

- solutions：用户题解分享（draft / published / removed；官方题解为 problems.solution，不建表）
- comments：多态评论（一期仅 target_type='solution'），两级回复（parent_id 仅挂一级评论）+ 软删除
- 可见性继承题目（services/community.py 复用 ProblemService 门控），本迁移只建表与索引

Revision ID: 0046
Revises: 0045
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = sa.text("now()")
    op.create_table(
        "solutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "problem_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("problems.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="published"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.CheckConstraint(
            "status IN ('draft','published','removed')", name="ck_solutions_status"
        ),
    )
    op.create_index("ix_solutions_problem_status", "solutions", ["problem_id", "status"])
    op.create_index("ix_solutions_user_status", "solutions", ["user_id", "status"])

    op.create_table(
        "comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comments.id"),
            nullable=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.CheckConstraint(
            "target_type IN ('solution','problem','post','submission')",
            name="ck_comments_target_type",
        ),
    )
    op.create_index(
        "ix_comments_target", "comments", ["target_type", "target_id", "created_at"]
    )
    op.create_index("ix_comments_parent", "comments", ["parent_id"])


def downgrade() -> None:
    op.drop_table("comments")
    op.drop_table("solutions")

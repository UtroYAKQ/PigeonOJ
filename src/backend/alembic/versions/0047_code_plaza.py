"""代码广场：code_shares 表 + 评论目标类型扩展 code_share

- code_shares：代码广场分享（published / removed；无草稿态，语言首批与判题语言一致；不关联题目）
- comments 的 ck_comments_target_type 重建以纳入 'code_share'

Revision ID: 0047
Revises: 0046
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = sa.text("now()")
    op.create_table(
        "code_shares",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("language", sa.String(32), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="published"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.CheckConstraint("status IN ('published','removed')", name="ck_code_shares_status"),
        sa.CheckConstraint(
            "language IN ('cpp17','python3.12','java21')", name="ck_code_shares_language"
        ),
    )
    op.create_index("ix_code_shares_status_created", "code_shares", ["status", "created_at"])
    op.create_index("ix_code_shares_user_status", "code_shares", ["user_id", "status"])

    # 评论目标类型扩展：纳入 code_share（重建 CHECK）
    op.drop_constraint("ck_comments_target_type", "comments", type_="check")
    op.create_check_constraint(
        "ck_comments_target_type",
        "comments",
        "target_type IN ('solution','code_share','problem','post','submission')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_comments_target_type", "comments", type_="check")
    op.create_check_constraint(
        "ck_comments_target_type",
        "comments",
        "target_type IN ('solution','problem','post','submission')",
    )
    op.drop_table("code_shares")

"""移除题目难度字段；标签体系补全（status / updated_at）

- problems 删除 difficulty 列（三档枚举由 admin 维护的标签体系替代，无自动映射，数据随迁移丢弃）
- problem_tags 增加 status（active/archived）与 updated_at

Revision ID: 0009
Revises: 0008
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("problems", "difficulty")
    op.add_column(
        "problem_tags",
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
    )
    op.add_column(
        "problem_tags",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_column("problem_tags", "updated_at")
    op.drop_column("problem_tags", "status")
    op.add_column(
        "problems",
        sa.Column("difficulty", sa.String(16), nullable=False, server_default="easy"),
    )

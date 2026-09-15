"""移除 problem_sets.referenced_at：团队题单 copy_items_from 复制机制随组织化改造下线后
无任何写入方（恒 NULL 死字段），一并从模型 / 契约 / 文档下线

Revision ID: 0042
Revises: 0041
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("problem_sets", "referenced_at")


def downgrade() -> None:
    op.add_column(
        "problem_sets",
        sa.Column("referenced_at", sa.DateTime(timezone=True), nullable=True),
    )
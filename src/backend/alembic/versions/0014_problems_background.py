"""新增题目背景字段 problems.background（必填，Markdown）

题目背景为必填题面要素，详情页渲染于题面之前（docs/contracts/problems.md）。
存量行以 ADD COLUMN ... NOT NULL DEFAULT '无' 一次性回填；
server_default 保留，兜底直接 ORM 建题等未显式传值的路径。

Revision ID: 0014
Revises: 0013
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "problems",
        sa.Column("background", sa.Text(), nullable=False, server_default=sa.text("'无'")),
    )


def downgrade() -> None:
    op.drop_column("problems", "background")

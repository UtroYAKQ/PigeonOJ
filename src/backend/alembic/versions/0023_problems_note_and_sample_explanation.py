"""新增题面说明字段 problems.note；展示样例 samples 增加 explanation 解释键

- note：可选题面说明（Markdown，NULL=未填写），详情页渲染于题面最后
- samples：JSONB 数组项由 {"input", "output"} 扩展为可选 {"input", "output", "explanation"}；
  JSONB 无结构变更，无 DDL，存量样例按无解释处理

Revision ID: 0023
Revises: 0022
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("problems", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("problems", "note")

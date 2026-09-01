"""沙箱输出上限对齐行业水平：各语言 output_limit_kb 1024KB → 5120KB（5MB）

1MB 单点输出上限低于主流 OJ（HydroOJ / HustOJ 默认 64MB），大输出题目
（如 n≥500 的矩阵构造题）在合法数据范围内即触发 output_limit_exceeded。
上调至 5MB：覆盖常规构造题输出，同时保留防失控输出的护栏意义
（executor 仍按该值截断并判 output_limit_exceeded）。

Revision ID: 0021
Revises: 0020
"""
from __future__ import annotations

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE sandbox_configs SET output_limit_kb = 5120, updated_at = now()")


def downgrade() -> None:
    op.execute("UPDATE sandbox_configs SET output_limit_kb = 1024, updated_at = now()")

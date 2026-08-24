"""移除 SPJ、团队题升级通道与出题分值

docs/decisions/2026-08-24-team-first-problem-production.md：
判题统一标准比对，无 checker 机制；团队题为封闭空间；出题不设测试点
分值，提交得分由服务端按通过比例派生（比赛计分随 contests 模块另行配置）。

Revision ID: 0006
Revises: 0005
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("problems", "promoted_at")
    op.drop_column("problems", "spj_code")
    op.drop_column("problems", "spj")
    op.drop_column("test_cases", "score")


def downgrade() -> None:
    op.add_column("test_cases", sa.Column("score", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("problems", sa.Column("spj", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("problems", sa.Column("spj_code", sa.String(512), nullable=True))
    op.add_column("problems", sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True))

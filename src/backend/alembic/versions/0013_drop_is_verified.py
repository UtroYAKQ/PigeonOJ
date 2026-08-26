"""移除冗余列 problems.is_verified（≡ verified_at IS NOT NULL）

验题通过与晋升解耦修订的配套清理：verified_at 是「已验题」唯一事实载体，
CHECK 约束同步改写；API 的 is_verified 字段改为模型派生属性，输出形状不变。

Revision ID: 0013
Revises: 0012
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_CONSTRAINT = "ck_problems_published_verified"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "problems", type_="check")
    op.drop_column("problems", "is_verified")
    op.create_check_constraint(
        _CONSTRAINT,
        "problems",
        "(status <> 'published' OR verified_at IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "problems", type_="check")
    op.add_column(
        "problems",
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_check_constraint(
        _CONSTRAINT,
        "problems",
        "(status <> 'published' OR is_verified)",
    )

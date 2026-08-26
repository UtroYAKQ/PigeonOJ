"""测试点「已验待生效」：暂存集通过验题后需显式应用才晋升

docs/decisions/2026-08-26-test-case-staged-promotion.md 修订：
验题通过与晋升解耦——complete_verification 只置 pending_verified 标记，
管理角色调 POST /problems/{id}/test-cases/apply 显式生效；
任何新的暂存写入都会清除该标记。

Revision ID: 0012
Revises: 0011
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "problems",
        sa.Column("pending_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("problems", "pending_verified")

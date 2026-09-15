"""团队空间开放：题目 / 题单增加「引用」来源字段

- problems.referenced_at：非空 = 经团队引用进入团队题库（区别于其他途径；引用时间）
- problem_sets.referenced_at：非空 = 经团队引用进入团队题单
- 团队比赛为团队空间直接创建（contest_type='team'），无引用语义，不加列

团队题库 / 题单 / 比赛的归属列（team_id）与可见性 CHECK 已随 0022 落库，
本迁移仅补引用来源字段，配套端点见 docs/contracts/teams.md「团队空间」节。

Revision ID: 0029
Revises: 0028
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "problems",
        sa.Column("referenced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "problem_sets",
        sa.Column("referenced_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("problem_sets", "referenced_at")
    op.drop_column("problems", "referenced_at")

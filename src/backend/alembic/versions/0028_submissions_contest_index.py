"""submissions 增加 (contest_id, created_at) 复合索引。

比赛所有提交查询（提交记录列表 / 榜单解冻重算 / 单格 AC / 昵称映射 / 本场作答状态）
均以 contest_id 过滤 + created_at 排序，此前无对应索引，随提交量累积退化为顺序扫描。
练习 / 验题提交 contest_id 为 NULL，天然不落入该索引的有效前缀。

Revision ID: 0028
Revises: 0027
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_submissions_contest_created", "submissions", ["contest_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_submissions_contest_created", table_name="submissions")

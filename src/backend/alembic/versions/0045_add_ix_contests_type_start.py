"""contests 补 (contest_type, start_time) 索引：比赛中心落地列表按 contest_type='public' ORDER BY start_time

- 现有索引 (status,start_time) 不匹配前导 contest_type 列，走全表扫描+排序
- 新增 ix_contests_type_start 覆盖比赛中心列表与站点首页比赛列表

Revision ID: 0045
Revises: 0044
"""
from __future__ import annotations

from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_contests_type_start",
        "contests",
        ["contest_type", "start_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_contests_type_start", table_name="contests")

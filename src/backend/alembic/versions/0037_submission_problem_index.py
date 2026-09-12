"""性能优化：submissions 按题目维度查询索引

题目全员提交列表（WHERE problem_id = X ORDER BY created_at DESC）与 admin
按题目过滤此前无前导 problem_id 索引可用，提交量增长后退化为顺序扫描 +
排序；补 (problem_id, created_at) 复合索引。

Revision ID: 0037
Revises: 0036
"""
from __future__ import annotations

from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_submissions_problem_created", "submissions", ["problem_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_submissions_problem_created", table_name="submissions")

"""题目难度分 + 通过率计数表

problems 新增 difficulty（手动填写的难度分，NULL=未评分，仅约束非负）；
新增 problem_counters 1:1 计数表（终态提交数 / AC 提交数），判题完成时原子累加，
避免 problems 热行频繁 UPDATE。存量数据按统计口径回填：
排除 verify（验题非真实作答）与 pending / judging / system_error（非终态或平台故障）。

Revision ID: 0016
Revises: 0015
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

_BACKFILL_SQL = """
INSERT INTO problem_counters (problem_id, submission_count, accepted_count, updated_at)
SELECT s.problem_id, COUNT(*), COUNT(*) FILTER (WHERE s.status = 'accepted'), now()
FROM submissions s
WHERE s.submit_type <> 'verify'
  AND s.status NOT IN ('pending', 'judging', 'system_error')
GROUP BY s.problem_id
ON CONFLICT (problem_id) DO NOTHING
"""


def upgrade() -> None:
    op.add_column(
        "problems",
        sa.Column("difficulty", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_problems_difficulty_nonneg",
        "problems",
        "difficulty IS NULL OR difficulty >= 0",
    )
    now = sa.text("now()")
    op.create_table(
        "problem_counters",
        sa.Column("problem_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("problems.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("submission_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.execute(_BACKFILL_SQL)


def downgrade() -> None:
    op.drop_table("problem_counters")
    op.drop_constraint("ck_problems_difficulty_nonneg", "problems", type_="check")
    op.drop_column("problems", "difficulty")

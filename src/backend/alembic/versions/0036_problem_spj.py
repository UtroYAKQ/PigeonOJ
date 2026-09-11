"""SPJ 特判判题：problems 双字段 + 逐测试点 message

- problems.spj_oss_id / pending_spj_oss_id：生效 / 暂存特判程序源码对象 key
  （MinIO problems/{problem_id}/spj/{uuid}/code，C++17；NULL = 非 SPJ 题；
  暂存空串 '' = 暂存移除，docs/contracts/problems.md「SPJ 特判程序」节）
- submission_test_case_results.message：SPJ 判定信息（特判程序 stdout ≤2KB，
  docs/contracts/judge.md「SPJ 特判」节）

Revision ID: 0036
Revises: 0035
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("problems", sa.Column("spj_oss_id", sa.String(512), nullable=True))
    op.add_column("problems", sa.Column("pending_spj_oss_id", sa.String(512), nullable=True))
    op.add_column("submission_test_case_results", sa.Column("message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("submission_test_case_results", "message")
    op.drop_column("problems", "pending_spj_oss_id")
    op.drop_column("problems", "spj_oss_id")

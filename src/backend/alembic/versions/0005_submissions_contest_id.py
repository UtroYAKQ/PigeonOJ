"""submissions 补 contest_id 列；submission_test_case_results.test_case_id 放宽为可空（与契约/模型对齐）

Revision ID: 0005
Revises: 0004
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # models.judge.Submission.contest_id：contests 模块上线前先占列（无 FK，随 contests 迁移补齐）
    op.add_column("submissions", sa.Column("contest_id", postgresql.UUID(as_uuid=True), nullable=True))
    # contracts/judge.md：submission_test_case_results.test_case_id 为 NULL（编译失败等场景无对应测试点）
    op.alter_column("submission_test_case_results", "test_case_id",
                    existing_type=postgresql.UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    op.alter_column("submission_test_case_results", "test_case_id",
                    existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_column("submissions", "contest_id")

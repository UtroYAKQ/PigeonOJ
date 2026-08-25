"""submission_test_case_results.test_case_id 外键补 ON DELETE SET NULL

判题历史结果须独立于测试点生命周期保留：题目全量替换测试点时
（DELETE FROM test_cases WHERE problem_id=...），仍被结果表引用的旧测试点
触发外键违规（NO ACTION）。列本身在 0005 已放宽为可空（编译失败等场景无对应
测试点），本迁移把删除语义补齐为「引用置空、结果行保留」。

Revision ID: 0010
Revises: 0009
"""
from __future__ import annotations

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_CONSTRAINT = "submission_test_case_results_test_case_id_fkey"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "submission_test_case_results", type_="foreignkey")
    op.create_foreign_key(
        _CONSTRAINT,
        "submission_test_case_results",
        "test_cases",
        ["test_case_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "submission_test_case_results", type_="foreignkey")
    op.create_foreign_key(
        _CONSTRAINT,
        "submission_test_case_results",
        "test_cases",
        ["test_case_id"],
        ["id"],
    )

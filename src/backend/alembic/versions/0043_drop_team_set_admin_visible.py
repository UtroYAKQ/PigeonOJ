"""移除团队题单 admin_visible 分支：团队题单恒 team_visible（全队成员可见）

- 存量团队题单 visibility 'admin_visible' 回填为 'team_visible'
- CHECK 约束重建：团队分支仅允许 'team_visible'
- 数据回填 + 约束收紧后，团队题单不可能再出现其他可见性值

Revision ID: 0043
Revises: 0042
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

_OLD_CHECK = (
    "("
    "(team_id IS NULL     AND visibility IN ('public','private')) OR"
    "(team_id IS NOT NULL AND visibility IN ('team_visible','admin_visible'))"
    ")"
)
_NEW_CHECK = (
    "("
    "(team_id IS NULL     AND visibility IN ('public','private')) OR"
    "(team_id IS NOT NULL AND visibility IN ('team_visible'))"
    ")"
)


def upgrade() -> None:
    op.drop_constraint("ck_problem_sets_owner_visibility", "problem_sets", type_="check")
    # 存量团队题单：'admin_visible' → 'team_visible'（团队题单全队可见，移除管理私密分支）
    op.execute(
        "UPDATE problem_sets SET visibility = 'team_visible' "
        "WHERE team_id IS NOT NULL AND visibility = 'admin_visible'"
    )
    op.create_check_constraint(
        "ck_problem_sets_owner_visibility", "problem_sets", _NEW_CHECK
    )


def downgrade() -> None:
    op.drop_constraint("ck_problem_sets_owner_visibility", "problem_sets", type_="check")
    op.create_check_constraint(
        "ck_problem_sets_owner_visibility", "problem_sets", _OLD_CHECK
    )
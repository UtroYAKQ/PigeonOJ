"""团队题单可见性双分支：problem_sets 团队分支 visibility 对齐团队题目

- 团队题单（team_id 非空）visibility 'team' 更名为 'team_visible'（全队成员可见）
- 新增 'admin_visible'（仅团队创建者 / 管理员可见，与团队题目 admin_visible 同语义）
- CHECK 约束重建：团队分支 IN ('team_visible','admin_visible')
- 存量团队题单一律回填 'team_visible'（原语义即全队可见）

Revision ID: 0032
Revises: 0031
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None

_OLD_CHECK = (
    "("
    "(team_id IS NULL     AND visibility IN ('public','private')) OR"
    "(team_id IS NOT NULL AND visibility = 'team')"
    ")"
)
_NEW_CHECK = (
    "("
    "(team_id IS NULL     AND visibility IN ('public','private')) OR"
    "(team_id IS NOT NULL AND visibility IN ('team_visible','admin_visible'))"
    ")"
)


def upgrade() -> None:
    op.drop_constraint("ck_problem_sets_owner_visibility", "problem_sets", type_="check")
    # 存量团队题单：'team' → 'team_visible'（原语义即全队可见）
    op.execute(
        "UPDATE problem_sets SET visibility = 'team_visible' "
        "WHERE team_id IS NOT NULL AND visibility = 'team'"
    )
    op.create_check_constraint(
        "ck_problem_sets_owner_visibility", "problem_sets", _NEW_CHECK
    )


def downgrade() -> None:
    op.drop_constraint("ck_problem_sets_owner_visibility", "problem_sets", type_="check")
    # 回滚：admin_visible 退回 team（原单值语义），team_visible 更名回 team
    op.execute(
        "UPDATE problem_sets SET visibility = 'team' WHERE team_id IS NOT NULL"
    )
    op.create_check_constraint(
        "ck_problem_sets_owner_visibility", "problem_sets", _OLD_CHECK
    )

"""组织题库：problems 补 org_id 外键，可见性 CHECK 扩展为三分支

- problems.org_id：归属组织（组织题库，docs/contracts/orgs.md）；与 team_id 互斥由 CHECK 兜底
- 可见性三分支：全站 private/public、组织 org_visible、团队 admin_visible/team_visible

Revision ID: 0040
Revises: 0039
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("problems", sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_problems_org", "problems", "organizations", ["org_id"], ["id"])
    op.create_index("ix_problems_org_status", "problems", ["org_id", "status"])
    op.drop_constraint("ck_problems_owner_visibility", "problems", type_="check")
    op.create_check_constraint(
        "ck_problems_owner_visibility",
        "problems",
        "("
        "(team_id IS NULL AND org_id IS NULL AND visibility IN ('private','public')) OR"
        "(org_id IS NOT NULL AND team_id IS NULL AND visibility = 'org_visible') OR"
        "(team_id IS NOT NULL AND visibility IN ('admin_visible','team_visible'))"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_problems_owner_visibility", "problems", type_="check")
    op.create_check_constraint(
        "ck_problems_owner_visibility",
        "problems",
        "("
        "(team_id IS NULL     AND visibility IN ('private','public')) OR"
        "(team_id IS NOT NULL AND visibility IN ('admin_visible','team_visible'))"
        ")",
    )
    op.drop_index("ix_problems_org_status", table_name="problems")
    op.drop_constraint("fk_problems_org", "problems", type_="foreignkey")
    op.drop_column("problems", "org_id")

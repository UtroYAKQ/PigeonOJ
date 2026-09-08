"""团队可见性：teams 增 visibility 字段（public / private，默认 private）

- public：团队中心列表可见，登录用户可直接提交加入申请
- private：不出现在团队中心，仅凭邀请链接申请加入（存量团队行为不变）

Revision ID: 0031
Revises: 0030
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column(
            "visibility",
            sa.String(length=16),
            nullable=False,
            server_default="private",
        ),
    )
    op.create_index("ix_teams_visibility_status", "teams", ["visibility", "status"])


def downgrade() -> None:
    op.drop_index("ix_teams_visibility_status", table_name="teams")
    op.drop_column("teams", "visibility")

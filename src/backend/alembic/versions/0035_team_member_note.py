"""团队成员备注：team_members 新增 note VARCHAR(64) NULL

- 本人可备注自己，团队创建者 / 管理员可备注任意成员；空串视为清除
- 展示于成员昵称之后（团队详情成员瓦片 / 管理端成员表）

Revision ID: 0035
Revises: 0034
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("team_members", sa.Column("note", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("team_members", "note")

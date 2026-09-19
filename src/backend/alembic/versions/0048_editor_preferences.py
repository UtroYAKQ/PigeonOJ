"""用户偏好：编辑器字号与字体（docs/contracts/users.md；前端 Monaco 消费）。

Revision ID: 0048
Revises: 0047
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("editor_font_size", sa.Integer(), nullable=False, server_default="14"),
    )
    op.add_column(
        "users",
        sa.Column(
            "editor_font_family", sa.String(32), nullable=False, server_default="jetbrains-mono"
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "editor_font_family")
    op.drop_column("users", "editor_font_size")

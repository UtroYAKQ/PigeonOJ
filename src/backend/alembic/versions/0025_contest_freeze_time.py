"""封榜配置改为绝对时刻：contests.freeze_offset_seconds → freeze_time（NULL = 不封榜）

业务口径改为直接设置封榜时间（与开始 / 结束时间同构的时间四元组之外的第 5 个时间点），
不再维护「结束前 N 秒」的偏移量；封榜窗口判定与滚榜数据边界均以 freeze_time 为准。
存量数据按 freeze_time = end_time - freeze_offset_seconds 换算迁移。

Revision ID: 0025
Revises: 0024
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contests", sa.Column("freeze_time", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE contests
        SET freeze_time = end_time - make_interval(secs => freeze_offset_seconds)
        WHERE freeze_offset_seconds > 0
        """
    )
    op.drop_column("contests", "freeze_offset_seconds")


def downgrade() -> None:
    op.add_column(
        "contests",
        sa.Column(
            "freeze_offset_seconds",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.execute(
        """
        UPDATE contests
        SET freeze_offset_seconds = GREATEST(
            0,
            EXTRACT(EPOCH FROM (end_time - freeze_time))::int
        )
        WHERE freeze_time IS NOT NULL
        """
    )
    op.drop_column("contests", "freeze_time")

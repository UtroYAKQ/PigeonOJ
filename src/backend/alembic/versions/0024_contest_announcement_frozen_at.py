"""比赛赛时工具与滚榜：contests 增加 announcement / announcement_updated_at / frozen_at

- announcement：比赛公告（Markdown，赛时可改，详情页主页 tab 公告条展示）
- announcement_updated_at：公告最近更新时间（前端展示「更新于」）
- frozen_at：进入封榜时刻（滚榜揭晓序列的数据源边界：封榜期提交 = created_at >= frozen_at）

延时 / 封榜交互逻辑后续迭代调整（frozen_at 先行落库，写入点随封榜周期任务补齐）。

Revision ID: 0024
Revises: 0023
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contests", sa.Column("announcement", sa.Text(), nullable=True))
    op.add_column(
        "contests", sa.Column("announcement_updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "contests", sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("contests", "frozen_at")
    op.drop_column("contests", "announcement_updated_at")
    op.drop_column("contests", "announcement")

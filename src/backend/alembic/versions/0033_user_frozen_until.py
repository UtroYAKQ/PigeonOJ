"""用户冻结语义改造：冻结 = 短时封禁（frozen_until 到期自动恢复）

- users 新增 frozen_until TIMESTAMPTZ NULL：非空 = 冻结到期时刻，到期后自动恢复 active
- 登录失败超次的临时锁定由 Redis login:lock:* 迁移为落库 frozen（frozen_until = now + 15 分钟）
- 存量 frozen 账号冻结语义不变（人工冻结 frozen_until 为空 = 无限期，仍需人工解冻）

Revision ID: 0033
Revises: 0032
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("frozen_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "frozen_until")

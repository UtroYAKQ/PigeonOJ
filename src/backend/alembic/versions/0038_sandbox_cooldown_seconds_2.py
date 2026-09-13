"""自测（运行样例）提交冷却默认 10s → 2s

开发体验调整：写代码时反复运行样例，10s 冷却过久；默认改为 2s。
仅更新系统配置行，不涉及表结构（docs/contracts/admin.md sandbox 配置项）。

Revision ID: 0038
Revises: 0037
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def _update_value(value: int) -> None:
    op.execute(
        sa.text(
            "UPDATE system_configs SET config_value = to_jsonb(:value) "
            "WHERE category = 'sandbox' AND config_key = 'sandbox.cooldown_seconds'"
        ).bindparams(value=value)
    )


def upgrade() -> None:
    _update_value(2)


def downgrade() -> None:
    _update_value(10)
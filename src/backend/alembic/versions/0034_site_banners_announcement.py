"""新增首页展示配置项：site.banners（轮播海报 JSON 数组）与 site.announcement（系统公告）。

- banners：JSONB 数组 [{image, title?, link?}]，管理员后台经 JSON 编辑维护，
  图片走 /files/upload/image 上传；经 GET /site-config 白名单下发（未登录可读）
- announcement：纯文本系统公告，空串 = 不展示

Revision ID: 0034
Revises: 0033
"""
from __future__ import annotations

import json

from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

_BANNERS_DEFAULT = json.dumps([])
_ANNOUNCEMENT_DEFAULT = json.dumps("")


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO system_configs (id, category, config_key, config_value, description)
        VALUES (gen_random_uuid(), 'site', 'site.banners', '{_BANNERS_DEFAULT}'::jsonb,
                '首页轮播海报')
        ON CONFLICT (category, config_key) DO NOTHING
        """
    )
    op.execute(
        f"""
        INSERT INTO system_configs (id, category, config_key, config_value, description)
        VALUES (gen_random_uuid(), 'site', 'site.announcement', '{_ANNOUNCEMENT_DEFAULT}'::jsonb,
                '首页系统公告')
        ON CONFLICT (category, config_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_configs WHERE category = 'site' AND config_key = 'site.banners'")
    op.execute(
        "DELETE FROM system_configs WHERE category = 'site' AND config_key = 'site.announcement'"
    )

"""新增系统配置项 log.record_get_logs（是否记录 GET 请求日志，默认 true）。

GET 日志量占全量请求的大头，管理侧可关闭以降噪；POST / PUT / DELETE 等写操作
始终记录（审计需要，不受此开关影响）。config_value 为 JSONB，布尔种子须显式
'true'::jsonb 转型，id 无数据库默认值须 gen_random_uuid() 生成。

Revision ID: 0027
Revises: 0026
"""
from __future__ import annotations

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO system_configs (id, category, config_key, config_value, description)
        VALUES (gen_random_uuid(), 'log', 'log.record_get_logs', 'true'::jsonb,
                '是否记录 GET 请求日志（关闭后仅记录写操作）')
        ON CONFLICT (category, config_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM system_configs WHERE category = 'log' AND config_key = 'log.record_get_logs'"
    )

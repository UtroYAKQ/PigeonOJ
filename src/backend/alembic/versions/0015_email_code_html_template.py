"""新增验证码邮件 HTML 模板配置（docs/contracts/admin.md auth_email.template）。

Revision ID: 0015
Revises: 0014
"""
from __future__ import annotations

import json
import uuid

import sqlalchemy as sa
from alembic import op

from app.services.system_config import EMAIL_CODE_HTML_TEMPLATE_DEFAULT

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

CONFIG_KEY = "email.template.code_html"
CONFIG_VALUE = EMAIL_CODE_HTML_TEMPLATE_DEFAULT
CONFIG_DESC = "验证码邮件 HTML 正文模板，占位符 {code} / {purpose}（留空用内置默认卡片）"


def upgrade() -> None:
    # 仅在行不存在时插入，避免与已手动写入的部署冲突（(category, config_key) 唯一约束）
    # config_value 为 JSONB：HTML 字符串需先 json.dumps 成 JSON 字符串字面量再 CAST
    stmt = sa.text(
        "INSERT INTO system_configs (id, category, config_key, config_value, description) "
        "SELECT CAST(:id AS uuid), 'auth_email', :key, CAST(:val AS jsonb), :desc "
        "WHERE NOT EXISTS ("
        "  SELECT 1 FROM system_configs WHERE category = 'auth_email' AND config_key = :key"
        ")"
    ).bindparams(
        id=str(uuid.uuid4()),
        key=CONFIG_KEY,
        val=json.dumps(CONFIG_VALUE),
        desc=CONFIG_DESC,
    )
    op.execute(stmt)


def downgrade() -> None:
    stmt = sa.text(
        "DELETE FROM system_configs WHERE category = 'auth_email' AND config_key = :key"
    ).bindparams(key=CONFIG_KEY)
    op.execute(stmt)

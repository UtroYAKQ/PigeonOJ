"""auth_email 域新增注册邮箱验证开关与 SMTP 发信配置（docs/contracts/admin.md）。

Revision ID: 0007
Revises: 0006
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.services.system_config import EMAIL_CODE_HTML_TEMPLATE_DEFAULT

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# 新增配置种子：验证开关默认开启（与既有行为一致），SMTP 默认未配置（host 空 = 验证码打印到日志）
CONFIG_SEEDS = [
    ("auth_email", "email.verify_enabled", True, "注册是否需要邮箱验证码"),
    ("auth_email", "email.smtp.host", "", "SMTP 服务器地址（留空则验证码打印到后端日志）"),
    ("auth_email", "email.smtp.port", 0, "SMTP 端口（0=按 smtp_mode 自动：ssl=465/starttls=587/plain=25）"),
    ("auth_email", "email.smtp.username", "", "SMTP 用户名"),
    ("auth_email", "email.smtp.password", "", "SMTP 密码 / 授权码（管理接口掩码返回）"),
    ("auth_email", "email.smtp.sender", "", "发件人地址（留空用 SMTP 用户名）"),
    ("auth_email", "email.smtp.smtp_mode", "ssl", "SMTP 加密模式（ssl / starttls / plain）"),
    ("auth_email", "email.smtp.use_ssl", True, "（已废弃）旧版是否使用 SSL 直连，存在 smtp_mode 时忽略"),
    ("auth_email", "email.template.code_html", EMAIL_CODE_HTML_TEMPLATE_DEFAULT, "验证码邮件 HTML 正文模板，占位符 {code} / {purpose}"),
]


def upgrade() -> None:
    op.bulk_insert(
        sa.table(
            "system_configs",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("category", sa.String()),
            sa.column("config_key", sa.String()),
            sa.column("config_value", postgresql.JSONB()),
            sa.column("description", sa.Text()),
        ),
        [
            {"id": uuid.uuid4(), "category": cat, "config_key": key, "config_value": value, "description": desc}
            for cat, key, value, desc in CONFIG_SEEDS
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM system_configs WHERE category = 'auth_email' AND config_key IN ("
            "'email.verify_enabled', 'email.smtp.host', 'email.smtp.port', 'email.smtp.username', "
            "'email.smtp.password', 'email.smtp.sender', 'email.smtp.smtp_mode', 'email.smtp.use_ssl', "
            "'email.template.code_html')"
        )
    )

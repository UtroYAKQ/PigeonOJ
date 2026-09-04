"""日志与会话增加地理位置列：request_logs / login_logs / user_sessions + location。

location 存后端离线解析（ip2region xdb）结果字符串（如「中国 浙江省 杭州市 阿里云」），
展示与导出直读该列，不做前端 IP 反查；NULL = 解析失败 / 内网历史数据。

Revision ID: 0026
Revises: 0025
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("request_logs", sa.Column("location", sa.String(128), nullable=True))
    op.add_column("login_logs", sa.Column("location", sa.String(128), nullable=True))
    op.add_column("user_sessions", sa.Column("location", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("user_sessions", "location")
    op.drop_column("login_logs", "location")
    op.drop_column("request_logs", "location")

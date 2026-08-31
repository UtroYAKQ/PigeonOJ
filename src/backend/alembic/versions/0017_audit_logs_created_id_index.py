"""审计日志深分页优化：延迟关联 + (created_at, id) 复合索引

LogRepository._page 改为延迟关联（子查询按覆盖索引仅取主键，OFFSET 丢弃成本
不回表），排序补 id 决胜列，同 created_at 行的页边界稳定（不重复 / 不漏行）。
原单列 ix_*_created 被复合索引最左前缀覆盖，替换以消除高频写入表的冗余索引。

Revision ID: 0017
Revises: 0016
"""
from __future__ import annotations

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

# (表名, 旧单列索引, 新复合索引)
_TABLES = [
    ("request_logs", "ix_request_logs_created", "ix_request_logs_created_id"),
    ("login_logs", "ix_login_logs_created", "ix_login_logs_created_id"),
    ("exception_logs", "ix_exception_logs_created", "ix_exception_logs_created_id"),
]


def upgrade() -> None:
    for table, old_index, new_index in _TABLES:
        op.create_index(new_index, table, ["created_at", "id"])
        op.drop_index(old_index, table_name=table)


def downgrade() -> None:
    for table, old_index, new_index in _TABLES:
        op.create_index(old_index, table, ["created_at"])
        op.drop_index(new_index, table_name=table)

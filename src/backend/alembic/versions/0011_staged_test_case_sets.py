"""测试点暂存/生效双集合：problems 引用列表 + 题级状态缓存

- problems 增加 active_case_ids / pending_case_ids / case_status / cases_revision
- test_cases 增加 origin_id（不可变版本化：改版新行指回原行，行永不物理删除）
- 存量回填：active 列表 = 该题现有全部测试点（按 sort_order），有点的题目 case_status='ok'
  （存量数据视为已生效集；发布门禁仍要求 is_verified + verified_at，行为不变）

Revision ID: 0011
Revises: 0010
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "problems",
        sa.Column("active_case_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column("problems", sa.Column("pending_case_ids", JSONB, nullable=True))
    op.add_column(
        "problems",
        sa.Column("case_status", sa.String(16), nullable=False, server_default="empty"),
    )
    op.add_column(
        "problems",
        sa.Column("cases_revision", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column("test_cases", sa.Column("origin_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_test_cases_origin_id", "test_cases", "test_cases", ["origin_id"], ["id"]
    )

    # 存量回填：生效集 = 现有全部测试点（按判题顺序）
    op.execute(
        """
        UPDATE problems p
        SET active_case_ids = sub.ids,
            case_status = 'ok'
        FROM (
            SELECT problem_id, jsonb_agg(id ORDER BY sort_order, created_at) AS ids
            FROM test_cases
            GROUP BY problem_id
        ) sub
        WHERE p.id = sub.problem_id
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_test_cases_origin_id", "test_cases", type_="foreignkey")
    op.drop_column("test_cases", "origin_id")
    op.drop_column("problems", "cases_revision")
    op.drop_column("problems", "case_status")
    op.drop_column("problems", "pending_case_ids")
    op.drop_column("problems", "active_case_ids")

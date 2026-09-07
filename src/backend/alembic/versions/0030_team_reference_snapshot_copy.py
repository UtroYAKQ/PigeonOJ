"""团队引用语义重构：引用 = 快照复制新题（原归属切换语义废弃）

原语义（0029）：引用即归属切换——原题 team_id 置为团队、referenced_at 记引用时间，
个人题库失去该题，且 problem_counters 计数随题带走（团队通过率混入个人提交）。

新语义：引用生成一道**新题**（快照复制），源题留在个人题库：
- 新题继承题面 / 样例 / 生效测试点（MinIO 对象复制）/ 标签 / 验题与发布状态
- source_problem_id 指向源题（追溯 + 防重：同团队同源题唯一）
- referenced_at = 引用时间（来源标记）
- 统计数据（problem_counters / submissions）从零开始 → 团队通过率为纯团队口径
- 存量归属切换产生的团队题目（referenced_at 非空、source_problem_id NULL）就地保留，
  视为已复制完成的快照（原引用时个人侧计数已随归属切换丢失，无法回补，保持现状）

Revision ID: 0030
Revises: 0029
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "problems",
        sa.Column("source_problem_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_problems_source_problem",
        "problems",
        "problems",
        ["source_problem_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # 同一团队对同一源题仅允许一份引用快照
    op.create_index(
        "uq_problems_team_source",
        "problems",
        ["team_id", "source_problem_id"],
        unique=True,
        postgresql_where=sa.text("source_problem_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_problems_team_source", table_name="problems")
    op.drop_constraint("fk_problems_source_problem", "problems", type_="foreignkey")
    op.drop_column("problems", "source_problem_id")

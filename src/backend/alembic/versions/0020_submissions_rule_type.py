"""提交记录原生携带赛制：submissions.rule_type 快照（ACM/IOI）

评测记录不再依赖比赛上下文 + 时间判断可见性：
- rule_type 在提交创建时从所属比赛快照（练习 / 验题为 NULL，按 IOI 部分计分）
- ACM：二值计分（全部测试点通过 = 单题满分，否则 0），分数本身无部分分可泄露，
  原「ACM 进行中限分（restricted）」机制随时间判断一并移除
- IOI：按通过测试点比例部分计分（原行为）

Revision ID: 0020
Revises: 0019
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "submissions",
        sa.Column("rule_type", sa.String(8), nullable=True),
    )
    op.create_check_constraint(
        "ck_submissions_rule_type",
        "submissions",
        "rule_type IS NULL OR rule_type IN ('ACM','IOI')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_submissions_rule_type", "submissions", type_="check")
    op.drop_column("submissions", "rule_type")

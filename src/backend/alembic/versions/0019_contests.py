"""比赛模块：contests / contest_problems / contest_registrations / contest_rankings

公开比赛全生命周期：建赛 → 报名 → 赛内提交计分（ACM 罚时 / IOI 取最高）→ 封榜 → 手动解冻重算
→ finished。团队比赛（team_id 非空）随 teams 模块开放：列与 CHECK 先落齐，teams 表建立后补 FK。

- contests：CHECK 报名截止 ≤ 结束时间、开赛 < 结束
- contest_problems：letter A/B/C…，UNIQUE(contest, problem)
- contest_registrations：UNIQUE(contest, user) 防重复报名
- contest_rankings：UNIQUE(contest, user, problem)；条件更新 WHERE is_frozen = false；
  解冻（admin/tutor 手动）时从 submissions 权威重算

Revision ID: 0019
Revises: 0018
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = sa.text("now()")
    op.create_table(
        "contests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo", sa.String(512), nullable=True),
        sa.Column("contest_type", sa.String(16), nullable=False, server_default="public"),
        # FK → teams.id 随 teams 模块迁移补齐
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rule_type", sa.String(8), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("register_start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("register_end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freeze_offset_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("board_frozen", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(16), nullable=False, server_default="scheduled"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.CheckConstraint("register_end_time <= end_time", name="ck_contests_register_end"),
        sa.CheckConstraint("start_time < end_time", name="ck_contests_time_range"),
        sa.CheckConstraint("contest_type IN ('public','team')", name="ck_contests_type"),
        sa.CheckConstraint("rule_type IN ('ACM','IOI')", name="ck_contests_rule"),
    )
    op.create_index("ix_contests_status_start", "contests", ["status", "start_time"])
    op.create_index("ix_contests_team_type", "contests", ["team_id", "contest_type"])

    op.create_table(
        "contest_problems",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contests.id"), nullable=False),
        sa.Column("problem_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("letter", sa.String(4), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint("contest_id", "problem_id", name="uq_contest_problems_contest_problem"),
    )
    op.create_index("ix_contest_problems_problem", "contest_problems", ["problem_id"])

    op.create_table(
        "contest_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contests.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="registered"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint("contest_id", "user_id", name="uq_contest_registrations_contest_user"),
    )
    op.create_index("ix_contest_registrations_user", "contest_registrations", ["user_id"])

    op.create_table(
        "contest_rankings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contests.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("problem_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("penalty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint("contest_id", "user_id", "problem_id", name="uq_contest_rankings_row"),
    )
    op.create_index("ix_contest_rankings_contest_frozen", "contest_rankings", ["contest_id", "is_frozen"])


def downgrade() -> None:
    op.drop_index("ix_contest_rankings_contest_frozen", table_name="contest_rankings")
    op.drop_table("contest_rankings")
    op.drop_index("ix_contest_registrations_user", table_name="contest_registrations")
    op.drop_table("contest_registrations")
    op.drop_index("ix_contest_problems_problem", table_name="contest_problems")
    op.drop_table("contest_problems")
    op.drop_index("ix_contests_team_type", table_name="contests")
    op.drop_index("ix_contests_status_start", table_name="contests")
    op.drop_table("contests")

"""题库完整 schema：problems 补列与约束、标签、验题、代码草稿、submissions.verification_id

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = sa.text("now()")
    uuid = postgresql.UUID(as_uuid=True)

    # ---- problems 补列（docs/contracts/problems.md） ----
    op.add_column("problems", sa.Column("input_description", sa.Text(), nullable=True))
    op.add_column("problems", sa.Column("output_description", sa.Text(), nullable=True))
    op.add_column("problems", sa.Column("solution", sa.Text(), nullable=True))
    op.add_column("problems", sa.Column("difficulty", sa.String(16), nullable=False, server_default="easy"))
    op.add_column("problems", sa.Column("visibility", sa.String(16), nullable=False, server_default="public"))
    op.add_column("problems", sa.Column("verified_by", uuid, sa.ForeignKey("users.id"), nullable=True))
    op.add_column("problems", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("problems", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("problems", sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True))
    # team_id 随 teams 模块迁移补齐；当前先约束全站题目可见性取值
    op.create_check_constraint("ck_problems_site_visibility", "problems", "visibility IN ('private','public')")
    op.create_check_constraint("ck_problems_published_verified", "problems", "(status <> 'published' OR is_verified)")
    op.create_index("ix_problems_owner", "problems", ["owner_id"])
    op.create_index("ix_problems_visibility_status", "problems", ["visibility", "status"])

    # ---- 标签 ----
    op.create_table(
        "problem_tags",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("color", sa.String(16)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_table(
        "problem_tag_relations",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("problem_id", uuid, sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("tag_id", uuid, sa.ForeignKey("problem_tags.id"), nullable=False),
        sa.UniqueConstraint("problem_id", "tag_id", name="uq_problem_tag"),
    )
    op.create_index("ix_problem_tag_tag", "problem_tag_relations", ["tag_id"])

    # ---- 验题 ----
    op.create_table(
        "problem_verification_invites",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("problem_id", uuid, sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("invited_by", uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_table(
        "problem_verifications",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("problem_id", uuid, sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("verifier_id", uuid, sa.ForeignKey("users.id")),
        sa.Column("invite_id", uuid, sa.ForeignKey("problem_verification_invites.id")),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("language", sa.String(32)),
        sa.Column("code", sa.Text()),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_problem_verifications_problem_status", "problem_verifications", ["problem_id", "status"])

    # ---- 用户代码草稿 ----
    op.create_table(
        "user_code_drafts",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("problem_id", uuid, sa.ForeignKey("problems.id")),
        sa.Column("contest_id", uuid),
        sa.Column("language", sa.String(32), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index(
        "uq_user_code_drafts_user_problem_language",
        "user_code_drafts",
        ["user_id", "problem_id", "language"],
        unique=True,
        postgresql_where=sa.text("contest_id IS NULL"),
    )

    # ---- submissions 关联验题记录 ----
    op.add_column("submissions", sa.Column("verification_id", uuid, sa.ForeignKey("problem_verifications.id")))
    op.add_column("submissions", sa.Column("is_after_contest", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_index("ix_submissions_verification", "submissions", ["verification_id"])
    op.create_check_constraint(
        "ck_submissions_verify_has_verification",
        "submissions",
        "(submit_type <> 'verify' OR verification_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_submissions_verify_has_verification", "submissions", type_="check")
    op.drop_index("ix_submissions_verification", table_name="submissions")
    op.drop_column("submissions", "is_after_contest")
    op.drop_column("submissions", "verification_id")
    op.drop_index("uq_user_code_drafts_user_problem_language", table_name="user_code_drafts")
    op.drop_table("user_code_drafts")
    op.drop_index("ix_problem_verifications_problem_status", table_name="problem_verifications")
    op.drop_table("problem_verifications")
    op.drop_table("problem_verification_invites")
    op.drop_index("ix_problem_tag_tag", table_name="problem_tag_relations")
    op.drop_table("problem_tag_relations")
    op.drop_table("problem_tags")
    op.drop_index("ix_problems_visibility_status", table_name="problems")
    op.drop_index("ix_problems_owner", table_name="problems")
    op.drop_constraint("ck_problems_published_verified", "problems", type_="check")
    op.drop_constraint("ck_problems_site_visibility", "problems", type_="check")
    for column in ("promoted_at", "published_at", "verified_at", "verified_by", "visibility", "difficulty", "solution", "output_description", "input_description"):
        op.drop_column("problems", column)

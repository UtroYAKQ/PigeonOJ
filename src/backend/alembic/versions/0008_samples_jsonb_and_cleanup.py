"""样例拆分至 problems.samples；删除验题邀请链接表与用户代码草稿表

docs/decisions/2026-08-24-samples-jsonb-and-invite-cleanup.md：
- problems 新增 samples JSONB 与 samples_updated_at；test_cases 删除
  is_sample / sample_input / sample_output 三列（存量样例行迁入 JSONB 后删除）
- 验题邀请链接改存 Redis（verify_invite:{token}），drop problem_verification_invites
  表与 problem_verifications.invite_id 列
- drop user_code_drafts 表（无消费方）

Revision ID: 0008
Revises: 0007
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "problems",
        sa.Column("samples", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "problems",
        sa.Column("samples_updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    # 存量样例行按 sort_order 迁入 problems.samples
    op.execute(
        """
        UPDATE problems p
        SET samples = COALESCE((
            SELECT jsonb_agg(jsonb_build_object('input', tc.sample_input, 'output', tc.sample_output)
                             ORDER BY tc.sort_order, tc.created_at)
            FROM test_cases tc
            WHERE tc.problem_id = p.id AND tc.is_sample
        ), '[]'::jsonb),
            samples_updated_at = now()
        """
    )
    op.execute("DELETE FROM test_cases WHERE is_sample")
    op.drop_column("test_cases", "is_sample")
    op.drop_column("test_cases", "sample_input")
    op.drop_column("test_cases", "sample_output")

    # 验题邀请链接改存 Redis：先删引用列再删表
    op.drop_constraint(
        op.f("problem_verifications_invite_id_fkey"),
        "problem_verifications",
        type_="foreignkey",
    )
    op.drop_column("problem_verifications", "invite_id")
    op.drop_table("problem_verification_invites")

    # 用户代码草稿表移除
    op.drop_index("uq_user_code_drafts_user_problem_language", table_name="user_code_drafts")
    op.drop_table("user_code_drafts")


def downgrade() -> None:
    # ---- 恢复 user_code_drafts 表 ----
    op.create_table(
        "user_code_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("problem_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("problems.id")),
        sa.Column("contest_id", postgresql.UUID(as_uuid=True)),
        sa.Column("language", sa.String(32), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "uq_user_code_drafts_user_problem_language",
        "user_code_drafts",
        ["user_id", "problem_id", "language"],
        unique=True,
        postgresql_where=sa.text("contest_id IS NULL"),
    )

    # ---- 恢复验题邀请链接表 ----
    op.create_table(
        "problem_verification_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("problem_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column(
        "problem_verifications",
        sa.Column("invite_id", postgresql.UUID(as_uuid=True)),
    )
    op.create_foreign_key(
        op.f("problem_verifications_invite_id_fkey"),
        "problem_verifications",
        "problem_verification_invites",
        ["invite_id"],
        ["id"],
    )

    # ---- 恢复 test_cases 样例三列并从 problems.samples 还原样例行 ----
    op.add_column("test_cases", sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("test_cases", sa.Column("sample_input", sa.Text()))
    op.add_column("test_cases", sa.Column("sample_output", sa.Text()))
    op.execute(
        """
        INSERT INTO test_cases (id, problem_id, name, is_sample, sample_input, sample_output,
                                input_oss_id, expected_output_oss_id, sort_order, created_at, updated_at)
        SELECT gen_random_uuid(),
               p.id,
               'sample' || ordinality,
               true,
               NULLIF(elem->>'input', ''),
               NULLIF(elem->>'output', ''),
               NULL,
               NULL,
               ordinality,
               now(),
               now()
        FROM problems p
        CROSS JOIN LATERAL jsonb_array_elements(p.samples) WITH ORDINALITY AS t(elem, ordinality)
        WHERE jsonb_typeof(p.samples) = 'array'
        """
    )
    op.drop_column("problems", "samples_updated_at")
    op.drop_column("problems", "samples")

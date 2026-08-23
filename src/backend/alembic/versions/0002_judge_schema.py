"""judge schema: problems / test_cases / submissions / submission_test_case_results

Revision ID: 0002
Revises: 0001
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = sa.text("now()")
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "problems",
        sa.Column("id", uuid, primary_key=True), sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False), sa.Column("time_limit_ms", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("memory_limit_mb", sa.Integer(), nullable=False, server_default="256"), sa.Column("spj", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("spj_code", sa.String(512)),
        sa.Column("owner_id", uuid, sa.ForeignKey("users.id"), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_table(
        "test_cases",
        sa.Column("id", uuid, primary_key=True), sa.Column("problem_id", uuid, sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("name", sa.String(64)), sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sample_input", sa.Text()), sa.Column("sample_output", sa.Text()), sa.Column("input_oss_id", sa.String(512)),
        sa.Column("expected_output_oss_id", sa.String(512)), sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_test_cases_problem_order", "test_cases", ["problem_id", "sort_order"])
    op.create_table(
        "submissions",
        sa.Column("id", uuid, primary_key=True), sa.Column("user_id", uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("problem_id", uuid, sa.ForeignKey("problems.id"), nullable=False), sa.Column("language", sa.String(32), nullable=False),
        sa.Column("code", sa.Text(), nullable=False), sa.Column("submit_type", sa.String(16), nullable=False, server_default="practice"),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"), sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("time_used_ms", sa.Integer()), sa.Column("memory_used_kb", sa.Integer()), sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_submissions_user_problem_created", "submissions", ["user_id", "problem_id", "created_at"])
    op.create_index("ix_submissions_status", "submissions", ["status"])
    op.create_table(
        "submission_test_case_results",
        sa.Column("id", uuid, primary_key=True), sa.Column("submission_id", uuid, sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("test_case_id", uuid, sa.ForeignKey("test_cases.id"), nullable=False), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("time_used_ms", sa.Integer()), sa.Column("memory_used_kb", sa.Integer()), sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint("submission_id", "test_case_id", name="uq_submission_case"),
    )
    op.create_index("ix_results_test_case", "submission_test_case_results", ["test_case_id"])


def downgrade() -> None:
    op.drop_index("ix_results_test_case", table_name="submission_test_case_results")
    op.drop_table("submission_test_case_results")
    op.drop_index("ix_submissions_status", table_name="submissions")
    op.drop_index("ix_submissions_user_problem_created", table_name="submissions")
    op.drop_table("submissions")
    op.drop_index("ix_test_cases_problem_order", table_name="test_cases")
    op.drop_table("test_cases")
    op.drop_table("problems")

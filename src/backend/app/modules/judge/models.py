"""题目、测试点与提交判题模型。表结构对应 docs/contracts/problems.md / judge.md。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infra.database import Base


class SandboxConfig(Base):
    """沙箱语言级配置（docs/contracts/judge.md sandbox_configs）。

    题目限制为 C++ 基准；其他语言按本表比例换算有效限制（2026-08-15-language-limit-ratio）。
    """

    __tablename__ = "sandbox_configs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    language: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    cpu_limit: Mapped[int | None] = mapped_column(Integer)
    time_ratio: Mapped[float] = mapped_column(nullable=False, server_default="1.0")
    memory_ratio: Mapped[float] = mapped_column(nullable=False, server_default="1.0")
    memory_min_mb: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    process_limit: Mapped[int | None] = mapped_column(Integer)
    filesystem_readonly: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    output_limit_kb: Mapped[int | None] = mapped_column(Integer)
    disk_quota_mb: Mapped[int | None] = mapped_column(Integer)
    cpu_cores: Mapped[int | None] = mapped_column(Integer)
    network_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Problem(Base):
    """题目（docs/contracts/problems.md；team_id 随 teams 模块迁移补齐）。"""

    __tablename__ = "problems"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    input_description: Mapped[str | None] = mapped_column(Text)
    output_description: Mapped[str | None] = mapped_column(Text)
    solution: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False, server_default="easy")
    time_limit_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1000")
    memory_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False, server_default="256")
    spj: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    spj_code: Mapped[str | None] = mapped_column(String(512))
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # 全站题目：private / public（团队题目 admin_visible / team_visible / public 随 teams 模块扩展）
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, server_default="public")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_problems_owner", "owner_id"),
        Index("ix_problems_visibility_status", "visibility", "status"),
        CheckConstraint(
            "visibility IN ('private','public')", name="ck_problems_site_visibility"
        ),
        CheckConstraint("(status <> 'published' OR is_verified)", name="ck_problems_published_verified"),
    )


class ProblemTag(Base):
    """标签定义（docs/contracts/problems.md problem_tags）。"""

    __tablename__ = "problem_tags"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProblemTagRelation(Base):
    """题目-标签关联（docs/contracts/problems.md problem_tag_relations）。"""

    __tablename__ = "problem_tag_relations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("problems.id"), nullable=False)
    tag_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("problem_tags.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("problem_id", "tag_id", name="uq_problem_tag"),
        Index("ix_problem_tag_tag", "tag_id"),
    )


class ProblemVerification(Base):
    """验题记录（docs/contracts/problems.md problem_verifications）。"""

    __tablename__ = "problem_verifications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("problems.id"), nullable=False)
    verifier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    invite_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("problem_verification_invites.id"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    language: Mapped[str | None] = mapped_column(String(32))
    code: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_problem_verifications_problem_status", "problem_id", "status"),)


class ProblemVerificationInvite(Base):
    """验题邀请链接（docs/contracts/problems.md problem_verification_invites）。"""

    __tablename__ = "problem_verification_invites"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("problems.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    invited_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class UserCodeDraft(Base):
    """用户代码草稿（docs/contracts/problems.md user_code_drafts；API 随编辑器自动保存接入）。"""

    __tablename__ = "user_code_drafts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    problem_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("problems.id"))
    contest_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # contests 模块上线后补 FK
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=lambda: datetime.now()
    )

    __table_args__ = (
        Index(
            "uq_user_code_drafts_user_problem_language",
            "user_id", "problem_id", "language",
            unique=True,
            postgresql_where=text("contest_id IS NULL"),
        ),
    )


class TestCase(Base):
    __tablename__ = "test_cases"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("problems.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(64))
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sample_input: Mapped[str | None] = mapped_column(Text)
    sample_output: Mapped[str | None] = mapped_column(Text)
    input_oss_id: Mapped[str | None] = mapped_column(String(512))
    expected_output_oss_id: Mapped[str | None] = mapped_column(String(512))
    score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (Index("ix_test_cases_problem_order", "problem_id", "sort_order"),)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    problem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("problems.id"), nullable=False)
    contest_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # contests 模块上线后补 FK
    verification_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("problem_verifications.id"))
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    submit_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="practice")
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="pending")
    score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    time_used_ms: Mapped[int | None] = mapped_column(Integer)
    memory_used_kb: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    is_after_contest: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        Index("ix_submissions_user_problem_created", "user_id", "problem_id", "created_at"),
        Index("ix_submissions_status", "status"),
        Index("ix_submissions_verification", "verification_id"),
        CheckConstraint(
            "(submit_type <> 'verify' OR verification_id IS NOT NULL)",
            name="ck_submissions_verify_has_verification",
        ),
    )


class SubmissionTestCaseResult(Base):
    __tablename__ = "submission_test_case_results"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=False)
    test_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("test_cases.id"))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    time_used_ms: Mapped[int | None] = mapped_column(Integer)
    memory_used_kb: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("submission_id", "test_case_id", name="uq_submission_case"), Index("ix_results_test_case", "test_case_id"))

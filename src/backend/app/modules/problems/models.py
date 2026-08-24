"""题库模型：题目、标签、验题、测试点、代码草稿。表结构对应 docs/contracts/problems.md。

原位于 judge/models.py；按「每张表只有一个归属模块」原则迁入题库模块
（docs/decisions/2026-08-24-backend-module-packaging.md）。
提交 / 判题结果模型在 judge 模块。
"""
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
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # 全站题目：private / public（团队题目 admin_visible / team_visible / public 随 teams 模块扩展）
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, server_default="public")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
    """测试点（docs/contracts/problems.md test_cases）；样例仅存库展示，不参与正式判题。"""

    __tablename__ = "test_cases"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("problems.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(64))
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sample_input: Mapped[str | None] = mapped_column(Text)
    sample_output: Mapped[str | None] = mapped_column(Text)
    input_oss_id: Mapped[str | None] = mapped_column(String(512))
    expected_output_oss_id: Mapped[str | None] = mapped_column(String(512))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (Index("ix_test_cases_problem_order", "problem_id", "sort_order"),)

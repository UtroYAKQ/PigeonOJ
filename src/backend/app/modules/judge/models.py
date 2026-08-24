"""判题模块模型：沙箱配置、提交与逐测试点结果。

表结构对应 docs/contracts/judge.md；题目 / 测试点表在 problems 模块
（docs/decisions/2026-08-24-backend-module-packaging.md）。
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


class Submission(Base):
    """提交（练习 / 验题；比赛上下文随 contests 模块扩展）。"""

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
    """逐测试点判题结果（期望输出与运行输出不返回前端）。"""

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

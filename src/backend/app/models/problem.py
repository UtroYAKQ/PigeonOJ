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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.enums import CaseStatus, ProblemStatus, ProblemVisibility, TagStatus, VerificationStatus


class Problem(Base):
    """题目（docs/contracts/problems.md；team_id 随 teams 模块迁移补齐）。"""

    __tablename__ = "problems"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    input_description: Mapped[str | None] = mapped_column(Text)
    output_description: Mapped[str | None] = mapped_column(Text)
    solution: Mapped[str | None] = mapped_column(Text)
    # 展示样例数组 [{"input", "output"}]，仅展示与自测，不参与判题（≤10 组，单项各 ≤64KB）
    samples: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    samples_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # 测试点集合：生效集（判题唯一来源）/ 暂存集（NULL=无暂存改动）
    active_case_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    pending_case_ids: Mapped[list | None] = mapped_column(JSONB)
    case_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=CaseStatus.EMPTY)
    cases_revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # 暂存集已通过验题、待显式应用（验题与晋升解耦，见决策记录修订）
    pending_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    time_limit_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1000")
    memory_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False, server_default="256")
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # 全站题目：private / public（团队题目 admin_visible / team_visible / public 随 teams 模块扩展）
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, server_default=ProblemVisibility.PUBLIC)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=ProblemStatus.DRAFT)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    # 验题通过时间即「已验题」事实载体（is_verified 列已移除，≡ verified_at 非空）
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
        CheckConstraint("(status <> 'published' OR verified_at IS NOT NULL)", name="ck_problems_published_verified"),
    )

    @property
    def is_verified(self) -> bool:
        """已验题通过 ≡ verified_at 非空（列移除后的派生兼容字段，API 输出不变）。"""
        return self.verified_at is not None


class ProblemTag(Base):
    """标签定义（docs/contracts/problems.md problem_tags；admin 维护，归档不删除）。

    分类体系替代原 difficulty 三档枚举（docs/decisions/2026-08-24-remove-difficulty-use-tags.md）。
    """

    __tablename__ = "problem_tags"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=TagStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


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
    # 指定验题人；链接邀请模式为空，验题通过时回写实际提交人
    verifier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=VerificationStatus.PENDING)
    language: Mapped[str | None] = mapped_column(String(32))
    code: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_problem_verifications_problem_status", "problem_id", "status"),)


class TestCase(Base):
    """判题测试点（docs/contracts/problems.md test_cases）；行不可变版本化，
    集合成员资格由 problems.active_case_ids / pending_case_ids 定义；
    样例存 problems.samples，不落本表。"""

    __tablename__ = "test_cases"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("problems.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(64))
    input_oss_id: Mapped[str] = mapped_column(String(512), nullable=False)
    expected_output_oss_id: Mapped[str] = mapped_column(String(512), nullable=False)
    origin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("test_cases.id"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (Index("ix_test_cases_problem_order", "problem_id", "sort_order"),)

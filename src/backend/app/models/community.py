"""社区模块数据模型：题解、评论。表结构对应 docs/contracts/community.md。

举报模型在 admin 模块（models/admin.py）；通知 / 私信 / 讨论区为规划项（契约留档未建表）。
官方题解为 problems.solution（题库模块），不在本模块建表。
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
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.enums import CodeShareStatus, CommentTargetType, SolutionStatus


class Solution(Base):
    """用户题解（docs/contracts/community.md solutions）。

    可见性继承题目：读写先过题目访问检查（services/community.py 复用 ProblemService 门控）。
    """

    __tablename__ = "solutions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("problems.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=SolutionStatus.PUBLISHED)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_solutions_problem_status", "problem_id", "status"),
        Index("ix_solutions_user_status", "user_id", "status"),
        CheckConstraint(
            "status IN ('draft','published','removed')",
            name="ck_solutions_status",
        ),
    )


class CodeShare(Base):
    """代码广场分享（docs/contracts/community.md code_shares）。

    无草稿态：创建即 published；removed 仅作者与 admin 可读；关联题目可选。
    """

    __tablename__ = "code_shares"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=CodeShareStatus.PUBLISHED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_code_shares_status_created", "status", "created_at"),
        Index("ix_code_shares_user_status", "user_id", "status"),
        CheckConstraint(
            "status IN ('published','removed')",
            name="ck_code_shares_status",
        ),
        CheckConstraint(
            "language IN ('cpp17','python3.12','java21')",
            name="ck_code_shares_language",
        ),
    )


class Comment(Base):
    """评论（docs/contracts/community.md comments）：多态 target + 两级回复 + 软删除。

    parent_id 仅允许挂一级评论（父评论的 parent_id 必须为 NULL），校验在服务层。
    """

    __tablename__ = "comments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comments.id")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_comments_target", "target_type", "target_id", "created_at"),
        Index("ix_comments_parent", "parent_id"),
        CheckConstraint(
            "target_type IN ('solution','code_share','problem','post','submission')",
            name="ck_comments_target_type",
        ),
    )

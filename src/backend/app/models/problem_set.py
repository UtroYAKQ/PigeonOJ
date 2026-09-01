"""题单模型：problem_sets / problem_set_items。表结构对应 docs/contracts/problem-sets.md。

团队题单（team_id 非空）随 teams 模块开放：列与 CHECK 约束先按契约落齐，
teams 表建立后由其迁移补 FK 约束，当前应用层拒绝创建团队题单。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
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

from app.core.database import Base
from app.enums import ProblemSetStatus, ProblemSetVisibility


class ProblemSet(Base):
    """题单（docs/contracts/problem-sets.md）。"""

    __tablename__ = "problem_sets"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # 归属团队；NULL=全站题单。FK → teams.id 随 teams 模块迁移补齐
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=ProblemSetVisibility.PUBLIC
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=ProblemSetStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        # 归属与可见性匹配：全站题单 public/private，团队题单 team（契约 CHECK 原文）
        CheckConstraint(
            "("
            "(team_id IS NULL     AND visibility IN ('public','private')) OR"
            "(team_id IS NOT NULL AND visibility = 'team')"
            ")",
            name="ck_problem_sets_owner_visibility",
        ),
        Index("ix_problem_sets_owner_status", "owner_id", "status"),
        Index("ix_problem_sets_team_visibility", "team_id", "visibility"),
    )


class ProblemSetItem(Base):
    """题单题目关联（按 sort_order 编排；题单内 UNIQUE 防重复加入）。"""

    __tablename__ = "problem_set_items"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("problem_sets.id"), nullable=False
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("problems.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    added_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("problem_set_id", "problem_id", name="uq_problem_set_items_set_problem"),
        Index("ix_problem_set_items_problem", "problem_id"),
    )

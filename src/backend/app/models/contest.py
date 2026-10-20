"""比赛模型：contests / contest_problems / contest_registrations / contest_rankings。

表结构对应 docs/contracts/contests.md。团队比赛（team_id 非空）随 teams 模块开放：
列与 CHECK 约束先按契约落齐，teams 表建立后由其迁移补 FK 约束。
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.enums import ContestStatus, ContestType, RegistrationStatus


class Contest(Base):
    """比赛（公开 / 团队；计分按 rule_type 区分 ACM / IOI）。"""

    __tablename__ = "contests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # 比赛头像（Markdown 图片 URL 语义，经 /files/upload/image 上传；前端卡片 / 详情横幅展示）
    logo: Mapped[str | None] = mapped_column(String(512))
    contest_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=ContestType.PUBLIC
    )
    # 团队比赛所属团队；FK → teams.id 随 teams 模块迁移补齐
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(8), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    register_start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    register_end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # 封榜时间（绝对时刻；NULL = 不封榜；须晚于 start_time 且不晚于 end_time）
    freeze_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    board_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # 周期任务进入封榜的实际执行时刻；统计边界使用 freeze_time，兼容旧数据时回退本列。
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 比赛公告（Markdown，赛时可改；详情页主页 tab 公告条展示）
    announcement: Mapped[str | None] = mapped_column(Text)
    announcement_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=ContestStatus.SCHEDULED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("register_end_time <= end_time", name="ck_contests_register_end"),
        CheckConstraint("start_time < end_time", name="ck_contests_time_range"),
        CheckConstraint(
            "freeze_time IS NULL OR (freeze_time > start_time AND freeze_time <= end_time)",
            name="ck_contests_freeze_time",
        ),
        CheckConstraint("contest_type IN ('public','team')", name="ck_contests_type"),
        CheckConstraint("rule_type IN ('ACM','IOI')", name="ck_contests_rule"),
        Index("ix_contests_status_start", "status", "start_time"),
        Index("ix_contests_team_type", "team_id", "contest_type"),
    )


class ContestProblem(Base):
    """比赛题目关联（letter 自动分配 A/B/C…；score 为 IOI 单题分值）。"""

    __tablename__ = "contest_problems"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contests.id"), nullable=False
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("problems.id"), nullable=False)
    letter: Mapped[str | None] = mapped_column(String(4))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("contest_id", "problem_id", name="uq_contest_problems_contest_problem"),
        Index("ix_contest_problems_problem", "problem_id"),
    )


class ContestRegistration(Base):
    """比赛报名（唯一约束防重复；cancelled 保留记录）。"""

    __tablename__ = "contest_registrations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contests.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=RegistrationStatus.REGISTERED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("contest_id", "user_id", name="uq_contest_registrations_contest_user"),
        Index("ix_contest_registrations_user", "user_id"),
    )


class ContestRanking(Base):
    """比赛榜单记录行：(contest, user, problem) 唯一；is_frozen 为封榜快照标记。

    回调在比赛行锁下从正式 submissions 重算对应题格；封榜前的晚到结果仍可补入。
    本表为兼容的物化投影，展示与解冻使用同一提交聚合规则。
    """

    __tablename__ = "contest_rankings"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contests.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    problem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("problems.id"), nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    penalty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("contest_id", "user_id", "problem_id", name="uq_contest_rankings_row"),
        Index("ix_contest_rankings_contest_frozen", "contest_id", "is_frozen"),
    )


class ScoreboardSession(Base):
    """One immutable resolver snapshot and a shared playback clock per contest."""

    __tablename__ = "scoreboard_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contests.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cursor: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    playing: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    speed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    anchor_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_command_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        CheckConstraint("revision >= 0 AND cursor >= 0", name="ck_scoreboard_session_progress"),
        CheckConstraint("speed IN (1,2,4)", name="ck_scoreboard_session_speed"),
    )

"""团队模块数据模型：teams / team_members / team_member_applications。

表结构与 docs/contracts/teams.md 对齐；团队角色经 user_roles（scope='team'、
object_id=team_id）授权，本模块不含独立角色表。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.enums import TeamApplicationStatus, TeamMemberStatus, TeamStatus


class Team(Base):
    """团队（docs/contracts/teams.md）。解散为软解散，成员资源默认归档不物理删除。"""

    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TeamStatus.ACTIVE, server_default=TeamStatus.ACTIVE
    )
    disbanded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=lambda: datetime.now(),
    )

    __table_args__ = (
        Index("ix_teams_creator", "creator_id"),
        Index("ix_teams_status", "status"),
    )


class TeamMember(Base):
    """团队成员（仅记录成员身份与入 / 退队状态；角色在 user_roles 中按 scope='team' 查询）。"""

    __tablename__ = "team_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TeamMemberStatus.ACTIVE,
        server_default=TeamMemberStatus.ACTIVE,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_team_members_active",
            "team_id",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_team_members_user", "user_id"),
    )


class TeamMemberApplication(Base):
    """团队加入申请（pending 唯一约束防止同一人重复申请同一团队）。"""

    __tablename__ = "team_member_applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # 使用的邀请链接令牌（数据存 Redis，仅记录使用来源）
    invite_token: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TeamApplicationStatus.PENDING,
        server_default=TeamApplicationStatus.PENDING,
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_team_applications_pending",
            "team_id",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_team_applications_user_status", "user_id", "status"),
    )

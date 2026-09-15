"""组织模块数据模型：organizations / org_members。

表结构与 docs/contracts/orgs.md 对齐；组织角色（org_admin / org_member）经
user_roles（scope='org'、object_id=org_id）授权，本模块不含独立角色表。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.enums import OrgMemberStatus, OrgStatus


class Organization(Base):
    """组织（docs/contracts/orgs.md）。解散为软解散，题库题目默认归档。"""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=OrgStatus.ACTIVE, server_default=OrgStatus.ACTIVE
    )
    # 创建操作人（站点 admin），仅审计署名、无权限语义
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    disbanded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=lambda: datetime.now(),
    )

    __table_args__ = (Index("ix_organizations_status", "status"),)


class OrgMember(Base):
    """组织成员（组织 = 导师组；角色在 user_roles 中按 scope='org' 查询）。"""

    __tablename__ = "org_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=OrgMemberStatus.ACTIVE,
        server_default=OrgMemberStatus.ACTIVE,
    )
    # 拉人操作人（org_admin / 站点 admin）
    added_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 成员备注：本人可备注自己，org_admin 可备注任意成员；展示于昵称之后
    note: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index(
            "uq_org_members_active",
            "org_id",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_org_members_user", "user_id"),
    )

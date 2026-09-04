"""平台级审计日志表：login_logs / request_logs / exception_logs（docs/contracts/admin.md）。

三类日志由中间件与各业务流程写入（登录、请求、异常），属横切基础设施；
admin 路由仅提供查询端点。写入助手与查询仓储见 app.repositories.audit。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.enums import LogLevel, LoginAction


class RequestLog(Base):
    """请求日志（docs/contracts/admin.md request_logs；沙箱执行子记录写入 extra）。"""

    __tablename__ = "request_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    # 离线解析（ip2region xdb）：「中国 浙江省 杭州市 阿里云」；内网记「内网IP」；NULL=解析失败
    location: Mapped[str | None] = mapped_column(String(128))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_request_logs_user_created", "user_id", "created_at"),
        Index("ix_request_logs_path_created", "path", "created_at"),
        # (created_at, id)：深分页延迟关联的覆盖索引（id 决胜列，页边界稳定）；
        # 0017 起替换原单列 ix_request_logs_created
        Index("ix_request_logs_created_id", "created_at", "id"),
    )


class LoginLog(Base):
    """登录 / 认证日志（docs/contracts/admin.md login_logs）。"""

    __tablename__ = "login_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    email: Mapped[str | None] = mapped_column(String(255))
    # login / logout / register / reset_password / change_email
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    # 离线解析（ip2region xdb）：「中国 北京 北京市 移动」；内网记「内网IP」；NULL=解析失败
    location: Mapped[str | None] = mapped_column(String(128))
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_login_logs_user_created", "user_id", "created_at"),
        Index("ix_login_logs_created_id", "created_at", "id"),
    )


class ExceptionLog(Base):
    """异常日志（docs/contracts/admin.md exception_logs）。"""

    __tablename__ = "exception_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # error / warning / fatal
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    traceback: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_exception_logs_created_id", "created_at", "id"),
        Index("ix_exception_logs_level_created", "level", "created_at"),
    )

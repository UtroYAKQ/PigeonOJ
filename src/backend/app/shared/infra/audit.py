"""平台级审计日志：login_logs / request_logs / exception_logs 模型 + 写入助手
（docs/contracts/admin.md）。

归属说明（docs/decisions/2026-08-24-backend-module-packaging.md）：
三类日志由中间件与各业务流程写入（登录、请求、异常），属横切基础设施，
模型下沉到 shared/infra；admin 模块仅提供查询端点。

- 登录日志：认证流程（login/logout/register/reset_password/change_email）
- 请求日志：main.py 中间件全量记录（含 request_id 追踪）
- 异常日志：main.py 中间件捕获未处理异常时记录
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func, select
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infra.database import Base


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
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_request_logs_user_created", "user_id", "created_at"),
        Index("ix_request_logs_path_created", "path", "created_at"),
        Index("ix_request_logs_created", "created_at"),
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
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_login_logs_user_created", "user_id", "created_at"),
        Index("ix_login_logs_created", "created_at"),
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
        Index("ix_exception_logs_created", "created_at"),
        Index("ix_exception_logs_level_created", "level", "created_at"),
    )


async def write_login_log(
    db: AsyncSession,
    action: str,
    success: bool,
    user_id: uuid.UUID | None = None,
    email: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    reason: str | None = None,
) -> None:
    """写入登录日志（在请求级会话中使用 flush，依赖外层 commit）。"""
    db.add(
        LoginLog(
            user_id=user_id,
            email=email,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            reason=reason,
        )
    )
    await db.flush()


async def write_request_log(
    db: AsyncSession,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    user_id: uuid.UUID | None,
    ip_address: str | None,
    user_agent: str | None,
    duration_ms: int,
) -> None:
    """写入请求日志（在独立会话中使用 commit，确保异常时也能持久化）。"""
    db.add(
        RequestLog(
            request_id=request_id,
            method=method,
            path=path,
            status_code=status_code,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            duration_ms=duration_ms,
        )
    )
    await db.commit()


async def write_exception_log(
    db: AsyncSession,
    level: str,
    message: str,
    traceback: str | None,
    request_id: str | None,
    user_id: uuid.UUID | None,
) -> None:
    """写入异常日志（在独立会话中使用 commit，确保异常时也能持久化）。"""
    db.add(
        ExceptionLog(
            level=level,
            message=message,
            traceback=traceback,
            request_id=request_id,
            user_id=user_id,
        )
    )
    await db.commit()


class LogRepository:
    """审计日志分页查询（admin 管理端点使用）。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _range_filter(column, start: str | None, end: str | None):
        conditions = []
        if start:
            conditions.append(column >= datetime.fromisoformat(start))
        if end:
            conditions.append(column <= datetime.fromisoformat(end))
        return conditions

    async def list_request_logs(
        self, page: int, page_size: int, keyword: str | None, start: str | None, end: str | None
    ) -> tuple[list[RequestLog], int]:
        conditions = self._range_filter(RequestLog.created_at, start, end)
        if keyword:
            kw = f"%{keyword}%"
            conditions.append(RequestLog.request_id.ilike(kw) | RequestLog.path.ilike(kw))
        return await self._page(RequestLog, RequestLog.created_at, page, page_size, conditions)

    async def list_login_logs(
        self, page: int, page_size: int, keyword: str | None, start: str | None, end: str | None
    ) -> tuple[list[LoginLog], int]:
        conditions = self._range_filter(LoginLog.created_at, start, end)
        if keyword:
            kw = f"%{keyword}%"
            conditions.append(LoginLog.email.ilike(kw) | LoginLog.action.ilike(kw))
        return await self._page(LoginLog, LoginLog.created_at, page, page_size, conditions)

    async def list_exception_logs(
        self, page: int, page_size: int, keyword: str | None, start: str | None, end: str | None
    ) -> tuple[list[ExceptionLog], int]:
        conditions = self._range_filter(ExceptionLog.created_at, start, end)
        if keyword:
            kw = f"%{keyword}%"
            conditions.append(ExceptionLog.message.ilike(kw) | ExceptionLog.traceback.ilike(kw))
        return await self._page(ExceptionLog, ExceptionLog.created_at, page, page_size, conditions)

    async def _page(self, model, order_col, page: int, page_size: int, conditions: list) -> tuple[list, int]:
        count_stmt = select(func.count()).select_from(model).where(*conditions) if conditions else select(func.count()).select_from(model)
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = select(model)
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = stmt.order_by(order_col.desc()).offset((page - 1) * page_size).limit(page_size)
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, int(total)

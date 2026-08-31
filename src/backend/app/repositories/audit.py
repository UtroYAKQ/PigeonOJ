"""审计日志仓储（docs/contracts/admin.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import ExceptionLog, LoginLog, RequestLog


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
        # 深分页延迟关联（late row lookup）：子查询按 (created_at, id) 覆盖索引仅取主键，
        # OFFSET 丢弃的行不回表，代价只随索引深度增长；外层仅对页内行回表取整行。
        # id 为决胜列：同 created_at 行的全序固定，页边界稳定（不重复 / 不漏行）。
        page_ids = (
            select(model.id)
            .where(*conditions)
            .order_by(order_col.desc(), model.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .subquery()
        )
        stmt = (
            select(model)
            .join(page_ids, model.id == page_ids.c.id)
            .order_by(order_col.desc(), model.id.desc())
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, int(total)

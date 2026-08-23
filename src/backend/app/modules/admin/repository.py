"""管理 / 运维模块数据访问（Repository 层）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import (
    ExceptionLog,
    LoginLog,
    Report,
    RequestLog,
    SystemConfig,
)


class ConfigRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, category: str, key: str) -> SystemConfig | None:
        stmt = select(SystemConfig).where(
            SystemConfig.category == category, SystemConfig.config_key == key
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, config_id: uuid.UUID) -> SystemConfig | None:
        return await self.db.get(SystemConfig, config_id)

    async def list_by_category(self, category: str | None) -> list[SystemConfig]:
        stmt = select(SystemConfig)
        if category:
            stmt = stmt.where(SystemConfig.category == category)
        stmt = stmt.order_by(SystemConfig.category, SystemConfig.config_key)
        return list((await self.db.execute(stmt)).scalars().all())


class LogRepository:
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


class ReportRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_page(self, page: int, page_size: int, status: str | None) -> tuple[list[Report], int]:
        conditions = []
        if status:
            conditions.append(Report.status == status)
        count_stmt = select(func.count()).select_from(Report)
        stmt = select(Report)
        if conditions:
            count_stmt = count_stmt.where(*conditions)
            stmt = stmt.where(*conditions)
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(Report.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, int(total)

    async def get_by_id(self, report_id: uuid.UUID) -> Report | None:
        return await self.db.get(Report, report_id)

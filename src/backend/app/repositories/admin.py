"""管理域仓储：Report 数据访问。"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Report


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

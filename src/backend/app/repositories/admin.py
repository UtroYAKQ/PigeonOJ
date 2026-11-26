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

    async def get_pending_duplicate(
        self, reporter_id: uuid.UUID, target_type: str, target_id: uuid.UUID
    ) -> Report | None:
        """同举报人同目标的 pending 举报（重复举报防重，community.md 3003）。"""
        stmt = select(Report).where(
            Report.reporter_id == reporter_id,
            Report.target_type == target_type,
            Report.target_id == target_id,
            Report.status == "pending",
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create(self, report: Report) -> Report:
        self.db.add(report)
        await self.db.flush()
        return report

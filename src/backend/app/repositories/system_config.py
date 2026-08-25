"""系统配置仓储。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_config import SystemConfig


class ConfigRepository:
    """system_configs 数据访问；admin 管理端点与业务读取共用。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, category: str, key: str) -> SystemConfig | None:
        stmt = select(SystemConfig).where(
            SystemConfig.category == category, SystemConfig.config_key == key
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, config_id: Any) -> SystemConfig | None:
        return await self.db.get(SystemConfig, config_id)

    async def list_by_category(self, category: str | None) -> list[SystemConfig]:
        stmt = select(SystemConfig)
        if category:
            stmt = stmt.where(SystemConfig.category == category)
        stmt = stmt.order_by(SystemConfig.category, SystemConfig.config_key)
        return list((await self.db.execute(stmt)).scalars().all())

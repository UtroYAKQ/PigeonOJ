"""系统基础端点：健康检查（根路径）与公开站点配置（/api/v1）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_site_public_configs
from app.core.database import get_db
from app.schemas.common import HealthStatus
from app.utils.response import ok

router = APIRouter(tags=["system"])
"""根级端点（无前缀）：健康检查。"""

v1_router = APIRouter(prefix="/api/v1", tags=["system"])
"""v1 级端点：公开站点配置。"""


@router.get("/health")
async def health() -> dict:
    """健康检查：返回统一信封 {code: 0, message: "ok", data: {...}}。"""
    return ok(HealthStatus(status="ok").model_dump(mode="json"))


@v1_router.get("/site-config")
async def site_config(db: AsyncSession = Depends(get_db)) -> dict:
    """公开站点配置（未登录可读）：站点名 / Logo / ICP / 默认主题 / 注册开关。"""
    return ok(await get_site_public_configs(db))

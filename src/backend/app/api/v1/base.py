"""系统基础端点：健康检查（根路径）与公开站点配置（/api/v1）。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import SiteConfigsDep
from app.schemas.admin import SitePublicConfig
from app.schemas.common import HealthStatus
from app.utils.response import ApiResponse, ok

router = APIRouter(tags=["system"])
"""根级端点（无前缀）：健康检查。"""

v1_router = APIRouter(prefix="/api/v1", tags=["system"])
"""v1 级端点：公开站点配置。"""


@router.get("/health", response_model=ApiResponse[HealthStatus])
async def health() -> ApiResponse[HealthStatus]:
    """健康检查：返回统一信封 {code: 0, message: "ok", data: {...}}。"""
    return ok(HealthStatus(status="ok"))


@v1_router.get("/site-config", response_model=ApiResponse[SitePublicConfig])
async def site_config(configs: SiteConfigsDep) -> ApiResponse[SitePublicConfig]:
    """公开站点配置（未登录可读）：站点名 / Logo / ICP / 默认主题 / 注册开关。"""
    return ok(configs)

"""系统配置服务：统一配置读取接口，解除 auth → admin 的反向依赖。

使用方式：
    from app.shared.config import ConfigService, get_config_service

    # 在 Service 中使用
    config = ConfigService(db)
    policy = await config.get_email_code_policy()

    # 或通过依赖注入
    @router.get("/endpoint")
    async def endpoint(config: ConfigService = Depends(get_config_service)):
        ...
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import SystemConfig
from app.modules.admin.repository import ConfigRepository

# 邮箱验证码安全策略默认值（docs/contracts/admin.md auth_email 域；可经系统配置覆盖）
EMAIL_CODE_DEFAULT = {
    "expire_seconds": 600,
    "resend_seconds": 60,
    "max_attempts": 5,
}


class ConfigService:
    """系统配置服务：读取 system_configs 表中的 KV 配置。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ConfigRepository(db)

    async def get_value(self, category: str, key: str, default: Any) -> Any:
        """读取系统配置（KV），缺失时返回默认值。"""
        row = await self.repo.get(category, key)
        if row is None:
            return default
        return row.config_value

    async def get_email_code_policy(self) -> dict:
        """获取邮箱验证码安全策略（过期时间、重发间隔、最大尝试次数）。"""
        category = "auth_email"
        return {
            "expire_seconds": int(
                await self.get_value(
                    category, "email.code.expire_seconds", EMAIL_CODE_DEFAULT["expire_seconds"]
                )
            ),
            "resend_seconds": int(
                await self.get_value(
                    category, "email.code.resend_seconds", EMAIL_CODE_DEFAULT["resend_seconds"]
                )
            ),
            "max_attempts": int(
                await self.get_value(
                    category, "email.code.max_attempts", EMAIL_CODE_DEFAULT["max_attempts"]
                )
            ),
        }


async def get_config_service(db: AsyncSession) -> ConfigService:
    """FastAPI 依赖注入：获取 ConfigService 实例。"""
    return ConfigService(db)

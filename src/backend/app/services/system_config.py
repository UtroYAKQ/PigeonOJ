"""系统配置读写服务：业务模块统一经本服务读取 KV 配置。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_config import SystemConfig
from app.repositories.system_config import ConfigRepository
from app.schemas.admin import EmailCodePolicy, SMTPConfig, SitePublicConfig


# 邮箱验证码安全策略默认值（docs/contracts/admin.md auth_email 域；可经系统配置覆盖）
EMAIL_CODE_DEFAULT = {
    "expire_seconds": 600,
    "resend_seconds": 60,
    "max_attempts": 5,
}

# SMTP 发信配置默认值（host 为空 = 未接入邮件服务，验证码打印到后端日志）
EMAIL_SMTP_DEFAULT = {
    "host": "",
    "port": 465,
    "username": "",
    "password": "",
    "sender": "",
    "use_ssl": True,
}


class ConfigService:
    """系统配置读取服务：业务模块统一经本类读取 KV 配置。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ConfigRepository(db)

    async def get_value(self, category: str, key: str, default: Any) -> Any:
        """读取系统配置（KV），缺失时返回默认值。"""
        row = await self.repo.get(category, key)
        if row is None:
            return default
        return row.config_value

    async def get_email_code_policy(self) -> EmailCodePolicy:
        """获取邮箱验证码安全策略（过期时间、重发间隔、最大尝试次数）。"""
        category = "auth_email"
        return EmailCodePolicy(
            expire_seconds=int(
                await self.get_value(
                    category, "email.code.expire_seconds", EMAIL_CODE_DEFAULT["expire_seconds"]
                )
            ),
            resend_seconds=int(
                await self.get_value(
                    category, "email.code.resend_seconds", EMAIL_CODE_DEFAULT["resend_seconds"]
                )
            ),
            max_attempts=int(
                await self.get_value(
                    category, "email.code.max_attempts", EMAIL_CODE_DEFAULT["max_attempts"]
                )
            ),
        )

    async def get_email_verify_enabled(self) -> bool:
        """注册是否需要邮箱验证码（email.verify_enabled，默认开启）。"""
        return bool(await self.get_value("auth_email", "email.verify_enabled", True))

    async def get_email_smtp_config(self) -> SMTPConfig:
        """SMTP 发信配置；host 为空表示未配置邮件服务。"""
        cfg = {}
        for key, default in EMAIL_SMTP_DEFAULT.items():
            value = await self.get_value("auth_email", f"email.smtp.{key}", default)
            if isinstance(default, int) and not isinstance(value, bool):
                value = int(value)
            elif isinstance(default, bool):
                value = bool(value)
            cfg[key] = value
        return SMTPConfig(**cfg)


async def get_category_configs(db: AsyncSession, category: str) -> dict[str, Any]:
    """读取整个分域的 KV 配置为 {config_key: config_value}；缺失域返回空 dict。"""
    rows = (await db.execute(select(SystemConfig).where(SystemConfig.category == category))).scalars().all()
    return {row.config_key: row.config_value for row in rows}


# 公开站点配置默认值：未配置时返回，保证前端首屏有合理兜底
SITE_PUBLIC_DEFAULTS: dict[str, Any] = {
    "name": "PigeonOJ",
    "logo": "",
    "icp": "",
    "default_theme": "light",
    "register_enabled": True,
    "email_verify_enabled": True,
}

# 配置键 → 公开字段名（site 域 + auth_email 域的注册验证开关）；仅暴露白名单，不透传整表
_SITE_PUBLIC_KEYS = {
    ("site", "site.name"): "name",
    ("site", "site.logo"): "logo",
    ("site", "site.icp"): "icp",
    ("site", "site.default_theme"): "default_theme",
    ("site", "site.register_enabled"): "register_enabled",
    ("auth_email", "email.verify_enabled"): "email_verify_enabled",
}


async def get_site_public_configs(db: AsyncSession) -> SitePublicConfig:
    """公开站点配置（GET /site-config，未登录可读）：
    站点名 / Logo / ICP / 默认主题 / 注册开关 / 注册邮箱验证开关。"""
    rows = (
        await db.execute(
            select(SystemConfig).where(SystemConfig.category.in_(["site", "auth_email"]))
        )
    ).scalars().all()
    kv = {(row.category, row.config_key): row.config_value for row in rows}
    return SitePublicConfig(
        name=kv.get(("site", "site.name"), SITE_PUBLIC_DEFAULTS["name"]),
        logo=kv.get(("site", "site.logo"), SITE_PUBLIC_DEFAULTS["logo"]),
        icp=kv.get(("site", "site.icp"), SITE_PUBLIC_DEFAULTS["icp"]),
        default_theme=kv.get(("site", "site.default_theme"), SITE_PUBLIC_DEFAULTS["default_theme"]),
        register_enabled=kv.get(("site", "site.register_enabled"), SITE_PUBLIC_DEFAULTS["register_enabled"]),
        email_verify_enabled=kv.get(("auth_email", "email.verify_enabled"), SITE_PUBLIC_DEFAULTS["email_verify_enabled"]),
    )

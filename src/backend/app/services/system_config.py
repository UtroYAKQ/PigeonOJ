"""系统配置读写服务：业务模块统一经本服务读取 KV 配置。"""
from __future__ import annotations

import time
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_config import SystemConfig
from app.repositories.system_config import ConfigRepository
from app.schemas.admin import EmailCodePolicy, SMTPConfig, SiteBanner, SitePublicConfig

# 进程内 TTL 缓存：系统配置读多写少（判题回写 / 邮件 / 站点配置等热点路径每次请求
# 都打 DB 不必要）。仅缓存标量（str/int/float/bool/None 与缺失哨兵），dict/list 直接
# 回源，避免调用方原地修改污染缓存。admin 更新配置时按 (category, key) 主动失效；
# 多 worker 部署下其他进程依赖 TTL 到期收敛（与 core/middlewares 的进程内缓存同款取舍）。
_CONFIG_CACHE_TTL_SECONDS = 30.0
_MISSING = object()  # 配置行不存在的哨兵：缓存「缺失」状态，命中时返回调用方 default

_config_cache: dict[tuple[str, str], tuple[float, Any]] = {}
_site_public_cache: tuple[float, SitePublicConfig] | None = None


def invalidate_config_cache(category: str | None = None, key: str | None = None) -> None:
    """失效进程内配置缓存（admin 更新配置 / 站点配置变更后调用）。

    不带参数清空全部；带 category（可再带 key）精确失效。未失效的进程最迟
    _CONFIG_CACHE_TTL_SECONDS 后读到新值。
    """
    global _site_public_cache
    if category is None:
        _config_cache.clear()
        _site_public_cache = None
        return
    if key is None:
        for cache_key in [k for k in _config_cache if k[0] == category]:
            _config_cache.pop(cache_key, None)
    else:
        _config_cache.pop((category, key), None)
    _site_public_cache = None


# 邮箱验证码安全策略默认值（docs/contracts/admin.md auth_email 域；可经系统配置覆盖）
EMAIL_CODE_DEFAULT = {
    "expire_seconds": 600,
    "resend_seconds": 60,
    "max_attempts": 5,
}

# SMTP 发信配置默认值（host 为空 = 未接入邮件服务，验证码打印到后端日志）
# SMTP 发信配置默认值（docs/contracts/admin.md auth_email.smtp 域；可经系统配置覆盖）
# 旧部署可能仅写入 email.smtp.use_ssl（bool），get_email_smtp_config 会向下兼容推导 smtp_mode。
EMAIL_SMTP_DEFAULT = {
    "host": "",
    "port": 0,  # 0 = 按 smtp_mode 自动推导端口；>0 为显式覆盖
    "username": "",
    "password": "",
    "sender": "",
    "smtp_mode": "ssl",
}

# smtp_mode → 默认端口（仅在 email.smtp.port 未显式配置即 0 时生效）
SMTP_MODE_DEFAULT_PORTS: dict[str, int] = {
    "ssl": 465,
    "starttls": 587,
    "plain": 25,
}

# 验证码邮件 HTML 正文默认模板。占位符：{code} 验证码、{purpose} 用途文案。
# 仅由管理员在系统配置中编辑，收件人侧不会被注入（code 为纯数字、purpose 取自固定枚举）。
EMAIL_CODE_HTML_TEMPLATE_DEFAULT = """\
<!doctype html>
<html lang="zh-CN">
  <body style="margin:0;background:#f4f6fb;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <div style="max-width:480px;margin:24px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.08);">
      <div style="background:linear-gradient(135deg,#4f7cff,#6a5cff);padding:24px 28px;color:#fff;">
        <h1 style="margin:0;font-size:20px;">PigeonOJ</h1>
        <p style="margin:6px 0 0;opacity:.9;font-size:13px;">邮箱验证码</p>
      </div>
      <div style="padding:28px;">
        <p style="margin:0 0 16px;color:#333;font-size:15px;">你好，你的{purpose}验证码如下，请勿泄露给他人：</p>
        <div style="font-size:32px;font-weight:700;letter-spacing:6px;color:#4f7cff;text-align:center;padding:16px;background:#f4f7ff;border-radius:8px;">{code}</div>
        <p style="margin:16px 0 0;color:#888;font-size:12px;">若非本人操作，请忽略本邮件。验证码有效期较短，请及时使用。</p>
      </div>
      <div style="padding:14px 28px;background:#fafbff;color:#aaa;font-size:12px;text-align:center;">© PigeonOJ</div>
    </div>
  </body>
</html>
"""


class ConfigService:
    """系统配置读取服务：业务模块统一经本类读取 KV 配置。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ConfigRepository(db)

    async def get_value(self, category: str, key: str, default: Any) -> Any:
        """读取系统配置（KV），缺失时返回默认值；标量值走进程内 TTL 缓存。"""
        cache_key = (category, key)
        now = time.monotonic()
        cached = _config_cache.get(cache_key)
        if cached is not None and cached[0] > now:
            value = cached[1]
            return default if value is _MISSING else value
        row = await self.repo.get(category, key)
        value = row.config_value if row is not None else _MISSING
        if not isinstance(value, (dict, list)):
            _config_cache[cache_key] = (now + _CONFIG_CACHE_TTL_SECONDS, value)
        return default if value is _MISSING else value

    async def should_record_get_logs(self) -> bool:
        """是否记录 GET 请求日志（log.record_get_logs，默认记录；写操作不受影响）。"""
        return bool(await self.get_value("log", "log.record_get_logs", True))

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

    async def get_email_code_html_template(self) -> str | None:
        """验证码邮件 HTML 正文模板；为空（默认内置模板也未覆盖）时回退纯文本。

        占位符：{code} 验证码、{purpose} 用途文案。模板由管理员编辑，受信任。
        """
        value = await self.get_value(
            "auth_email", "email.template.code_html", EMAIL_CODE_HTML_TEMPLATE_DEFAULT
        )
        return value if value else None

    async def get_email_smtp_config(self) -> SMTPConfig:
        """SMTP 发信配置；host 为空表示未配置邮件服务。

        一次取回 auth_email 全域配置（替代逐键 6-7 条单键查询）。
        兼容旧部署：若未写入 email.smtp.smtp_mode，则按 legacy 的 email.smtp.use_ssl 推导
        （True → "ssl"，False → "starttls"）。
        """
        kv = await get_category_configs(self.db, "auth_email")
        host = kv.get("email.smtp.host", EMAIL_SMTP_DEFAULT["host"])
        raw_port = kv.get("email.smtp.port", EMAIL_SMTP_DEFAULT["port"])
        username = kv.get("email.smtp.username", EMAIL_SMTP_DEFAULT["username"])
        password = kv.get("email.smtp.password", EMAIL_SMTP_DEFAULT["password"])
        sender = kv.get("email.smtp.sender", EMAIL_SMTP_DEFAULT["sender"])
        mode = kv.get("email.smtp.smtp_mode")
        if mode not in ("ssl", "starttls", "plain"):
            use_ssl = bool(kv.get("email.smtp.use_ssl", True))
            mode = "ssl" if use_ssl else "starttls"
        # 端口未显式配置（0/空）时按 smtp_mode 推导；>0 视为显式覆盖
        port = int(raw_port) if raw_port else 0
        if not port:
            port = SMTP_MODE_DEFAULT_PORTS[mode]
        return SMTPConfig(
            host=host,
            port=port,
            username=username,
            password=password,
            sender=sender,
            smtp_mode=mode,
        )


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
    "banners": [],
    "announcement": "",
}

# 配置键 → 公开字段名（site 域 + auth_email 域的注册验证开关）；仅暴露白名单，不透传整表
_SITE_PUBLIC_KEYS = {
    ("site", "site.name"): "name",
    ("site", "site.logo"): "logo",
    ("site", "site.icp"): "icp",
    ("site", "site.default_theme"): "default_theme",
    ("site", "site.register_enabled"): "register_enabled",
    ("site", "site.banners"): "banners",
    ("site", "site.announcement"): "announcement",
    ("auth_email", "email.verify_enabled"): "email_verify_enabled",
}

# 首页轮播海报上限：防误配超大列表拖慢首屏（管理端为 JSON 文本编辑，无结构硬约束）
_SITE_BANNERS_MAX = 10


def _parse_banners(raw: Any) -> list[SiteBanner]:
    """解析 site.banners（JSONB 数组 [{image, title?, link?}]）：
    非 dict / 缺 image 的条目跳过，截断至上限。"""
    if not isinstance(raw, list):
        return []
    banners: list[SiteBanner] = []
    for item in raw[:_SITE_BANNERS_MAX]:
        try:
            banners.append(SiteBanner.model_validate(item))
        except ValidationError:
            continue
    return banners


async def get_site_public_configs(db: AsyncSession) -> SitePublicConfig:
    """公开站点配置（GET /site-config，未登录可读）：
    站点名 / Logo / ICP / 默认主题 / 注册开关 / 注册邮箱验证开关 / 首页轮播海报 / 系统公告。

    每个前端首屏都会请求且几乎不变，走进程内 TTL 缓存（admin 更新配置时失效）。
    """
    global _site_public_cache
    now = time.monotonic()
    if _site_public_cache is not None and _site_public_cache[0] > now:
        return _site_public_cache[1]
    rows = (
        await db.execute(
            select(SystemConfig).where(SystemConfig.category.in_(["site", "auth_email"]))
        )
    ).scalars().all()
    kv = {(row.category, row.config_key): row.config_value for row in rows}
    announcement = kv.get(("site", "site.announcement"), SITE_PUBLIC_DEFAULTS["announcement"])
    config = SitePublicConfig(
        name=kv.get(("site", "site.name"), SITE_PUBLIC_DEFAULTS["name"]),
        logo=kv.get(("site", "site.logo"), SITE_PUBLIC_DEFAULTS["logo"]),
        icp=kv.get(("site", "site.icp"), SITE_PUBLIC_DEFAULTS["icp"]),
        default_theme=kv.get(("site", "site.default_theme"), SITE_PUBLIC_DEFAULTS["default_theme"]),
        register_enabled=kv.get(("site", "site.register_enabled"), SITE_PUBLIC_DEFAULTS["register_enabled"]),
        banners=_parse_banners(kv.get(("site", "site.banners"), SITE_PUBLIC_DEFAULTS["banners"])),
        announcement=announcement if isinstance(announcement, str) else "",
        email_verify_enabled=kv.get(("auth_email", "email.verify_enabled"), SITE_PUBLIC_DEFAULTS["email_verify_enabled"]),
    )
    _site_public_cache = (now + _CONFIG_CACHE_TTL_SECONDS, config)
    return config

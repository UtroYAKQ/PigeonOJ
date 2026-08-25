"""管理/运维域服务：系统配置/日志/沙箱状态/举报处理。"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ReportStatus
from app.models.user import User
from app.repositories.admin import ReportRepository
from app.repositories.user import UserRepository
from app.repositories.audit import LogRepository
from app.repositories.system_config import ConfigRepository
from app.schemas.admin import (
    ConfigItemOut,
    ExceptionLogOut,
    LoginLogOut,
    ReportOut,
    RequestLogOut,
    SandboxNodeOut,
)
from app.schemas.common import PaginatedData
from app.core.exceptions import (
    PARAM_FORMAT_INVALID,
    RESOURCE_NOT_FOUND,
    RESOURCE_STATE_CONFLICT,
    APIError,
)
from app.core.redis import SANDBOX_NODE_KEY_PREFIX, get_redis

logger = logging.getLogger(__name__)

# 敏感配置键后缀：列表返回时掩码，更新时该值表示「保持原值」
_PASSWORD_KEY_SUFFIX = ".password"
_PASSWORD_MASK = "******"


def _is_secret_key(config_key: str) -> bool:
    return config_key.endswith(_PASSWORD_KEY_SUFFIX)


class AdminConfigService:
    """管理后台专用的配置服务：在平台配置读取之上扩展列表查询与更新。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ConfigRepository(db)

    async def list_configs(self, category: str | None) -> list[ConfigItemOut]:
        rows = await self.repo.list_by_category(category)
        # 修改人：关联 users 取昵称（updated_by 为 UUID）
        updater_ids = {r.updated_by for r in rows if r.updated_by}
        updater_names = await UserRepository(self.db).get_nicknames(list(updater_ids))
        return [
            ConfigItemOut(
                id=str(r.id),
                category=r.category,
                config_key=r.config_key,
                config_value=_PASSWORD_MASK
                if _is_secret_key(r.config_key) and r.config_value
                else r.config_value,
                description=r.description,
                updated_by=updater_names.get(r.updated_by) if r.updated_by else None,
                updated_at=r.updated_at.isoformat(),
            )
            for r in rows
        ]

    async def update_configs(self, admin: User, items: list[dict]) -> list[ConfigItemOut]:
        for item in items:
            config_id = item.get("id")
            if not config_id:
                raise APIError(PARAM_FORMAT_INVALID, "配置项缺少 id", 400)
            row = await self.repo.get_by_id(uuid.UUID(str(config_id)))
            if row is None:
                raise APIError(RESOURCE_NOT_FOUND, f"配置不存在：{config_id}", 404)
            value = item["config_value"]
            # 敏感键：提交掩码值视为「未修改」，避免把密文回写覆盖真实值
            if _is_secret_key(row.config_key) and value == _PASSWORD_MASK:
                continue
            row.config_value = value
            row.updated_by = admin.id
        await self.db.flush()
        return await self.list_configs(None)


class LogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = LogRepository(db)

    async def list(self, log_type: str, page: int, page_size: int, keyword: str | None, start: str | None, end: str | None) -> PaginatedData:
        if log_type == "request":
            rows, total = await self.repo.list_request_logs(page, page_size, keyword, start, end)
            items = [
                RequestLogOut(
                    id=str(r.id), request_id=r.request_id,
                    user_id=str(r.user_id) if r.user_id else None,
                    method=r.method, path=r.path, status_code=r.status_code,
                    ip_address=r.ip_address, duration_ms=r.duration_ms,
                    created_at=r.created_at.isoformat(),
                )
                for r in rows
            ]
        elif log_type == "login":
            rows, total = await self.repo.list_login_logs(page, page_size, keyword, start, end)
            items = [
                LoginLogOut(
                    id=str(r.id), user_id=str(r.user_id) if r.user_id else None,
                    email=r.email, action=r.action, ip_address=r.ip_address,
                    success=r.success, reason=r.reason, created_at=r.created_at.isoformat(),
                )
                for r in rows
            ]
        elif log_type == "exception":
            rows, total = await self.repo.list_exception_logs(page, page_size, keyword, start, end)
            items = [
                ExceptionLogOut(
                    id=str(r.id), level=r.level, message=r.message,
                    traceback=r.traceback, request_id=r.request_id,
                    user_id=str(r.user_id) if r.user_id else None,
                    created_at=r.created_at.isoformat(),
                )
                for r in rows
            ]
        else:
            raise APIError(RESOURCE_NOT_FOUND, "日志类型不存在", 404)
        return PaginatedData(items=[i.model_dump(mode="json") for i in items], total=total, page=page, page_size=page_size)


class SandboxService:
    """沙箱节点状态：读 Redis 热数据（sandbox:node:<id>），无节点时返回空列表。"""

    async def status(self) -> list[SandboxNodeOut]:
        r = get_redis()
        nodes: list[SandboxNodeOut] = []
        async for key in r.scan_iter(f"{SANDBOX_NODE_KEY_PREFIX}*", count=100):
            raw = await r.get(key)
            if not raw:
                continue
            try:
                data = json.loads(raw)
                nodes.append(SandboxNodeOut(**data))
            except (json.JSONDecodeError, Exception):
                logger.warning("sandbox node key %s 解析失败", key)
        return nodes


class ReportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ReportRepository(db)

    async def list(self, page: int, page_size: int, status: str | None) -> PaginatedData:
        rows, total = await self.repo.list_page(page, page_size, status)
        reporter_ids = {r.reporter_id for r in rows}
        nicknames = await UserRepository(self.db).get_nicknames(list(reporter_ids))
        items = [
            ReportOut(
                id=str(r.id),
                target_type=r.target_type,
                target_id=str(r.target_id),
                target_summary=None,  # 内容表（题解/帖子/评论）实现后回填摘要
                reporter_nickname=nicknames.get(r.reporter_id, "未知用户"),
                reason=r.reason,
                status=r.status,
                handled_by=str(r.handled_by) if r.handled_by else None,
                handled_at=r.handled_at.isoformat() if r.handled_at else None,
                created_at=r.created_at.isoformat(),
            )
            for r in rows
        ]
        return PaginatedData(items=[i.model_dump(mode="json") for i in items], total=total, page=page, page_size=page_size)

    async def handle(self, report_id: uuid.UUID, admin: User, action: str) -> None:
        """处理举报：handled（通过）/ ignored（驳回），见 docs/contracts/community.md。"""
        report = await self.repo.get_by_id(report_id)
        if report is None:
            raise APIError(RESOURCE_NOT_FOUND, "举报不存在", 404)
        if report.status != ReportStatus.PENDING:
            raise APIError(RESOURCE_STATE_CONFLICT, "该举报已处理", 409)
        report.status = action
        report.handled_by = admin.id
        report.handled_at = datetime.now()
        await self.db.flush()

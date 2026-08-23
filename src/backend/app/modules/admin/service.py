"""管理 / 运维模块业务逻辑（Service 层）。

系统配置 / 日志 / 沙箱状态 / 举报处理；用户管理逻辑在 users.service（admin.routes 调用）。
（模型配置服务随 AI 模块暂缓实现）

"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import Report
from app.modules.admin.repository import ConfigRepository, LogRepository, ReportRepository
from app.modules.users.models import User
from app.shared.common.config import ConfigService
from app.shared.common.errors import (
    PARAM_FORMAT_INVALID,
    RESOURCE_NOT_FOUND,
    RESOURCE_STATE_CONFLICT,
    APIError,
)
from app.shared.infra.redis import get_redis

logger = logging.getLogger(__name__)


class AdminConfigService(ConfigService):
    """管理后台专用的配置服务，扩展了配置列表查询和更新功能。"""

    async def list_configs(self, category: str | None) -> list[dict]:
        rows = await self.repo.list_by_category(category)
        # 修改人：关联 users 取昵称（updated_by 为 UUID）
        updater_ids = {r.updated_by for r in rows if r.updated_by}
        updater_names: dict[uuid.UUID, str] = {}
        if updater_ids:
            stmt = select(User.id, User.nickname).where(User.id.in_(updater_ids))
            for uid, nickname in (await self.db.execute(stmt)).all():
                updater_names[uid] = nickname
        return [
            {
                "id": str(r.id),
                "category": r.category,
                "config_key": r.config_key,
                "config_value": r.config_value,
                "description": r.description,
                "updated_by": updater_names.get(r.updated_by) if r.updated_by else None,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rows
        ]

    async def update_configs(self, admin: User, items: list[dict]) -> list[dict]:
        for item in items:
            config_id = item.get("id")
            if not config_id:
                raise APIError(PARAM_FORMAT_INVALID, "配置项缺少 id", 400)
            row = await self.repo.get_by_id(uuid.UUID(str(config_id)))
            if row is None:
                raise APIError(RESOURCE_NOT_FOUND, f"配置不存在：{config_id}", 404)
            row.config_value = item["config_value"]
            row.updated_by = admin.id
        await self.db.flush()
        return await self.list_configs(None)


class LogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = LogRepository(db)

    async def list(self, log_type: str, page: int, page_size: int, keyword: str | None, start: str | None, end: str | None) -> dict:
        if log_type == "request":
            rows, total = await self.repo.list_request_logs(page, page_size, keyword, start, end)
            items = [
                {
                    "id": str(r.id), "request_id": r.request_id,
                    "user_id": str(r.user_id) if r.user_id else None,
                    "method": r.method, "path": r.path, "status_code": r.status_code,
                    "ip_address": r.ip_address, "duration_ms": r.duration_ms,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        elif log_type == "login":
            rows, total = await self.repo.list_login_logs(page, page_size, keyword, start, end)
            items = [
                {
                    "id": str(r.id), "user_id": str(r.user_id) if r.user_id else None,
                    "email": r.email, "action": r.action, "ip_address": r.ip_address,
                    "success": r.success, "reason": r.reason, "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        elif log_type == "exception":
            rows, total = await self.repo.list_exception_logs(page, page_size, keyword, start, end)
            items = [
                {
                    "id": str(r.id), "level": r.level, "message": r.message,
                    "traceback": r.traceback, "request_id": r.request_id,
                    "user_id": str(r.user_id) if r.user_id else None,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        else:
            raise APIError(RESOURCE_NOT_FOUND, "日志类型不存在", 404)
        return {"items": items, "total": total, "page": page, "page_size": page_size}


class SandboxService:
    """沙箱节点状态：读 Redis 热数据（sandbox:node:<id>），无节点时返回空列表。"""

    async def status(self) -> list[dict]:
        r = get_redis()
        nodes: list[dict] = []
        async for key in r.scan_iter("sandbox:node:*", count=100):
            raw = await r.get(key)
            if not raw:
                continue
            try:
                nodes.append(json.loads(raw))
            except json.JSONDecodeError:
                logger.warning("sandbox node key %s 解析失败", key)
        return nodes


class ReportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ReportRepository(db)

    async def list(self, page: int, page_size: int, status: str | None) -> dict:
        rows, total = await self.repo.list_page(page, page_size, status)
        reporter_ids = {r.reporter_id for r in rows}
        nicknames: dict[uuid.UUID, str] = {}
        if reporter_ids:
            stmt = select(User.id, User.nickname).where(User.id.in_(reporter_ids))
            for uid, nickname in (await self.db.execute(stmt)).all():
                nicknames[uid] = nickname
        items = [
            {
                "id": str(r.id),
                "target_type": r.target_type,
                "target_id": str(r.target_id),
                "target_summary": None,  # 内容表（题解/帖子/评论）实现后回填摘要
                "reporter_nickname": nicknames.get(r.reporter_id, "未知用户"),
                "reason": r.reason,
                "status": r.status,
                "handled_by": str(r.handled_by) if r.handled_by else None,
                "handled_at": r.handled_at.isoformat() if r.handled_at else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def handle(self, report_id: uuid.UUID, admin: User, action: str) -> None:
        """处理举报：handled（通过）/ ignored（驳回），见 docs/contracts/community.md。"""
        report = await self.repo.get_by_id(report_id)
        if report is None:
            raise APIError(RESOURCE_NOT_FOUND, "举报不存在", 404)
        if report.status != "pending":
            raise APIError(RESOURCE_STATE_CONFLICT, "该举报已处理", 409)
        report.status = action
        report.handled_by = admin.id
        report.handled_at = datetime.now()
        await self.db.flush()

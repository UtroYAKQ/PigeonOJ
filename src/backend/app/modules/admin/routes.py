"""管理 / 运维路由（docs/contracts/admin.md /admin* 端点，统一前缀 /api/v1，全部 admin 权限）。

用户管理端点（用户列表 / 角色 / 封禁 / 冻结）复用 users.service 的业务逻辑。
（模型配置 / Token 用量端点随 AI 模块暂缓实现）
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.schemas import (
    ConfigUpdateRequest,
    ReportHandleRequest,
    RoleUpdateRequest,
    StatusReasonRequest,
)
from app.modules.admin.service import AdminConfigService, LogService, ReportService, SandboxService
from app.modules.users.api import User, UserService, get_current_admin
from app.shared.common.response import ok
from app.shared.infra.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])

_admin = Depends(get_current_admin)


@router.get("/users")
async def list_users(
    admin: User = _admin,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    status: str | None = None,
):
    return ok(await UserService(db).admin_list_users(page, page_size, keyword, status))


@router.put("/users/{user_id}/roles")
async def set_roles(
    user_id: uuid.UUID,
    body: RoleUpdateRequest,
    admin: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    await UserService(db).admin_set_roles(user_id, body.role_ids)
    return ok(None)


@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: uuid.UUID,
    body: StatusReasonRequest | None = None,
    admin: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    await UserService(db).admin_ban(user_id, body.reason if body else None)
    return ok(None)


@router.post("/users/{user_id}/unban")
async def unban_user(
    user_id: uuid.UUID,
    admin: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    await UserService(db).admin_unban(user_id)
    return ok(None)


@router.post("/users/{user_id}/freeze")
async def freeze_user(
    user_id: uuid.UUID,
    body: StatusReasonRequest | None = None,
    admin: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    await UserService(db).admin_freeze(user_id, body.reason if body else None)
    return ok(None)


@router.post("/users/{user_id}/unfreeze")
async def unfreeze_user(
    user_id: uuid.UUID,
    admin: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    await UserService(db).admin_unfreeze(user_id)
    return ok(None)


@router.get("/configs")
async def list_configs(
    admin: User = _admin,
    db: AsyncSession = Depends(get_db),
    category: str | None = None,
):
    return ok(await AdminConfigService(db).list_configs(category))


@router.put("/configs")
async def update_configs(
    body: ConfigUpdateRequest,
    admin: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminConfigService(db).update_configs(admin, [i.model_dump() for i in body.items]))


@router.get("/logs/{log_type}")
async def list_logs(
    log_type: str,
    admin: User = _admin,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    start: str | None = None,
    end: str | None = None,
):
    return ok(await LogService(db).list(log_type, page, page_size, keyword, start, end))


@router.get("/sandbox/status")
async def sandbox_status(
    admin: User = _admin,
):
    return ok(await SandboxService().status())


@router.get("/reports")
async def list_reports(
    admin: User = _admin,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
):
    return ok(await ReportService(db).list(page, page_size, status))


@router.post("/reports/{report_id}/handle")
async def handle_report(
    report_id: uuid.UUID,
    body: ReportHandleRequest,
    admin: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    await ReportService(db).handle(report_id, admin, body.action)
    return ok(None)

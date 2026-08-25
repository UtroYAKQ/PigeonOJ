"""管理 / 运维路由（docs/contracts/admin.md /admin* 端点，统一前缀 /api/v1，全部 admin 权限）。

用户管理端点（用户列表 / 角色 / 封禁 / 冻结）复用 users.service 的业务逻辑。
（模型配置 / Token 用量端点随 AI 模块暂缓实现）
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.admin import (
    ConfigUpdateRequest,
    ReportHandleRequest,
    RoleUpdateRequest,
    StatusReasonRequest,
)
from app.schemas.problem import TagCreate, TagOut, TagUpdate
from app.services.admin import AdminConfigService, LogService, ReportService, SandboxService
from app.services.tag import TagService
from app.models.user import User
from app.core.dependency import get_current_admin
from app.services.user import UserService
from app.utils.response import ok
from app.core.database import get_db

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
    result = await LogService(db).list(log_type, page, page_size, keyword, start, end)
    return ok(result.model_dump(mode="json"))


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
    result = await ReportService(db).list(page, page_size, status)
    return ok(result.model_dump(mode="json"))


@router.post("/reports/{report_id}/handle")
async def handle_report(
    report_id: uuid.UUID,
    body: ReportHandleRequest,
    admin: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    await ReportService(db).handle(report_id, admin, body.action)
    return ok(None)


# ---- 标签管理（docs/contracts/problems.md 端点表 /admin/tags*） ----


def tag_out(tag) -> dict:
    return TagOut.model_validate(tag).model_dump(mode="json")


@router.get("/tags")
async def list_tags(admin: User = _admin, db: AsyncSession = Depends(get_db)):
    """标签管理全量列表（含已归档；激活在前）。"""
    rows = await TagService(db).list_all()
    return ok([tag_out(row) for row in rows])


@router.post("/tags")
async def create_tag(body: TagCreate, admin: User = _admin, db: AsyncSession = Depends(get_db)):
    tag = await TagService(db).create(body)
    await db.commit()
    return ok(tag_out(tag))


@router.put("/tags/{tag_id}")
async def update_tag(
    tag_id: uuid.UUID,
    body: TagUpdate,
    admin: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    tag = await TagService(db).update(tag_id, body)
    await db.commit()
    return ok(tag_out(tag))


@router.post("/tags/{tag_id}/archive")
async def archive_tag(tag_id: uuid.UUID, admin: User = _admin, db: AsyncSession = Depends(get_db)):
    tag = await TagService(db).archive(tag_id)
    await db.commit()
    return ok(tag_out(tag))



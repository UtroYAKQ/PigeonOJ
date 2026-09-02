"""管理 / 运维路由（docs/contracts/admin.md /admin* 端点，统一前缀 /api/v1，全部 admin 权限）。

用户管理端点（用户列表 / 角色 / 封禁 / 冻结）复用 users.service 的业务逻辑。
（模型配置 / Token 用量端点随 AI 模块暂缓实现）
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    AdminConfigServiceDep,
    LogServiceDep,
    ProblemSetServiceDep,
    ReportServiceDep,
    SandboxServiceDep,
    SessionDep,
    TagServiceDep,
    UserServiceDep,
)
from app.models.user import User
from app.schemas.admin import (
    ConfigItemOut,
    ConfigUpdateRequest,
    ExceptionLogOut,
    LoginLogOut,
    ReportHandleRequest,
    ReportOut,
    RequestLogOut,
    RoleUpdateRequest,
    SandboxNodeOut,
    StatusReasonRequest,
)
from app.schemas.problem import TagCreate, TagOut, TagUpdate
from app.schemas.problem_set import ProblemSetSummary
from app.schemas.user import UserPublic
from app.core.dependency import get_current_admin, get_current_user
from app.enums import ProblemSetStatus
from app.utils.pagination import PaginatedResponse
from app.utils.response import ApiResponse, ok

router = APIRouter(prefix="/admin", tags=["admin"])

_admin = Depends(get_current_admin)

LogPage = PaginatedResponse[RequestLogOut] | PaginatedResponse[LoginLogOut] | PaginatedResponse[ExceptionLogOut]


@router.get("/users", response_model=ApiResponse[PaginatedResponse[UserPublic]])
async def list_users(
    service: UserServiceDep,
    admin: User = _admin,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    status: str | None = None,
) -> ApiResponse[PaginatedResponse[UserPublic]]:
    return ok(await service.admin_list_users(page, page_size, keyword, status))


@router.put("/users/{user_id}/roles", response_model=ApiResponse[None])
async def set_roles(
    user_id: uuid.UUID,
    body: RoleUpdateRequest,
    service: UserServiceDep,
    admin: User = _admin,
) -> ApiResponse[None]:
    await service.admin_set_roles(user_id, body.role_ids)
    return ok(None)


@router.post("/users/{user_id}/ban", response_model=ApiResponse[None])
async def ban_user(
    user_id: uuid.UUID,
    service: UserServiceDep,
    body: StatusReasonRequest | None = None,
    admin: User = _admin,
) -> ApiResponse[None]:
    await service.admin_ban(user_id, body.reason if body else None)
    return ok(None)


@router.post("/users/{user_id}/unban", response_model=ApiResponse[None])
async def unban_user(
    user_id: uuid.UUID,
    service: UserServiceDep,
    admin: User = _admin,
) -> ApiResponse[None]:
    await service.admin_unban(user_id)
    return ok(None)


@router.post("/users/{user_id}/freeze", response_model=ApiResponse[None])
async def freeze_user(
    user_id: uuid.UUID,
    service: UserServiceDep,
    body: StatusReasonRequest | None = None,
    admin: User = _admin,
) -> ApiResponse[None]:
    await service.admin_freeze(user_id, body.reason if body else None)
    return ok(None)


@router.post("/users/{user_id}/unfreeze", response_model=ApiResponse[None])
async def unfreeze_user(
    user_id: uuid.UUID,
    service: UserServiceDep,
    admin: User = _admin,
) -> ApiResponse[None]:
    await service.admin_unfreeze(user_id)
    return ok(None)


@router.get("/configs", response_model=ApiResponse[list[ConfigItemOut]])
async def list_configs(
    service: AdminConfigServiceDep,
    admin: User = _admin,
    category: str | None = None,
) -> ApiResponse[list[ConfigItemOut]]:
    return ok(await service.list_configs(category))


@router.put("/configs", response_model=ApiResponse[list[ConfigItemOut]])
async def update_configs(
    body: ConfigUpdateRequest,
    service: AdminConfigServiceDep,
    admin: User = _admin,
) -> ApiResponse[list[ConfigItemOut]]:
    return ok(await service.update_configs(admin, body.items))


@router.get("/logs/{log_type}", response_model=ApiResponse[LogPage])
async def list_logs(
    log_type: str,
    service: LogServiceDep,
    admin: User = _admin,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> ApiResponse[LogPage]:
    return ok(await service.list(log_type, page, page_size, keyword, start, end))


@router.get("/sandbox/status", response_model=ApiResponse[list[SandboxNodeOut]])
async def sandbox_status(
    service: SandboxServiceDep,
    admin: User = _admin,
) -> ApiResponse[list[SandboxNodeOut]]:
    return ok(await service.status())


@router.get("/reports", response_model=ApiResponse[PaginatedResponse[ReportOut]])
async def list_reports(
    service: ReportServiceDep,
    admin: User = _admin,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
) -> ApiResponse[PaginatedResponse[ReportOut]]:
    return ok(await service.list(page, page_size, status))


@router.post("/reports/{report_id}/handle", response_model=ApiResponse[None])
async def handle_report(
    report_id: uuid.UUID,
    body: ReportHandleRequest,
    service: ReportServiceDep,
    admin: User = _admin,
) -> ApiResponse[None]:
    await service.handle(report_id, admin, body.action)
    return ok(None)


# ---- 标签管理（docs/contracts/problems.md 端点表 /admin/tags*） ----
@router.get("/tags", response_model=ApiResponse[list[TagOut]])
async def list_tags(
    service: TagServiceDep,
    admin: User = _admin,
) -> ApiResponse[list[TagOut]]:
    """标签管理全量列表（含已归档；激活在前）。"""
    rows = await service.list_all()
    return ok([TagOut.model_validate(row) for row in rows])


@router.post("/tags", response_model=ApiResponse[TagOut])
async def create_tag(
    body: TagCreate,
    service: TagServiceDep,
    db: SessionDep,
    admin: User = _admin,
) -> ApiResponse[TagOut]:
    tag = await service.create(body)
    await db.commit()
    return ok(TagOut.model_validate(tag))


@router.put("/tags/{tag_id}", response_model=ApiResponse[TagOut])
async def update_tag(
    tag_id: uuid.UUID,
    body: TagUpdate,
    service: TagServiceDep,
    db: SessionDep,
    admin: User = _admin,
) -> ApiResponse[TagOut]:
    tag = await service.update(tag_id, body)
    await db.commit()
    return ok(TagOut.model_validate(tag))


@router.post("/tags/{tag_id}/archive", response_model=ApiResponse[TagOut])
async def archive_tag(
    tag_id: uuid.UUID,
    service: TagServiceDep,
    db: SessionDep,
    admin: User = _admin,
) -> ApiResponse[TagOut]:
    tag = await service.archive(tag_id)
    await db.commit()
    return ok(TagOut.model_validate(tag))


# ---- 题单管理（docs/contracts/problem-sets.md；管理角色 admin/tutor，非 admin 专属） ----


@router.get("/problem-sets", response_model=ApiResponse[PaginatedResponse[ProblemSetSummary]])
async def admin_list_problem_sets(
    service: ProblemSetServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    status: ProblemSetStatus | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[ProblemSetSummary]]:
    """题单管理视图：全量题单（含私有与已下线），供管理后台编排维护。"""
    await service.require_manager(user)
    rows, total = await service.list_manage(
        page=page, page_size=page_size, keyword=keyword, status=status
    )
    return ok(PaginatedResponse(items=rows, total=total, page=page, page_size=page_size))

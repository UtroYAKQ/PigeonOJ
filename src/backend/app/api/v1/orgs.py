"""组织路由（docs/contracts/orgs.md /orgs* 端点，统一前缀 /api/v1）。

组织角色经 user_roles（scope='org'）应用层判定；路由仅做 HTTP 装配，
权限 / 状态校验收敛在 OrgService。组织管理端点在 /admin 前缀（admin.py），
组织题库端点复用题库统一端点（见 problems.md），本路由不含题目管理动作。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import OrgServiceDep, ProblemServiceDep, SessionDep
from app.core.dependency import get_current_admin, get_current_user
from app.models.user import User
from app.schemas.org import (
    OrgAdminFlag,
    OrgCreate,
    OrgDetail,
    OrgMemberAdd,
    OrgMemberNote,
    OrgMemberOut,
    OrgSummary,
    OrgUpdate,
)
from app.schemas.problem import ProblemCreate, TeamProblemSummary
from app.schemas.team import TeamCreate, TeamSummary
from app.utils.pagination import PaginatedResponse
from app.utils.response import ApiResponse, ok

router = APIRouter(prefix="/orgs", tags=["orgs"])


@router.post("", response_model=ApiResponse[OrgDetail])
async def create_org(
    body: OrgCreate,
    service: OrgServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_admin),
) -> ApiResponse[OrgDetail]:
    """创建组织（站点 admin）：可同时任命初始组织管理员。"""
    detail = await service.create(user, body)
    await db.commit()
    return ok(detail)


@router.get("/mine", response_model=ApiResponse[PaginatedResponse[OrgSummary]])
async def list_my_orgs(
    service: OrgServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=64),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[OrgSummary]]:
    """我的组织列表（在册成员，创建时间倒序；keyword 模糊匹配组织名称）。"""
    items, total = await service.list_mine(user, page, page_size, keyword)
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


@router.get("/{org_id}", response_model=ApiResponse[OrgDetail])
async def get_org(
    org_id: uuid.UUID,
    service: OrgServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[OrgDetail]:
    """组织详情（组织成员可见，非成员 2003）。"""
    return ok(await service.get_detail(user, org_id))


@router.put("/{org_id}", response_model=ApiResponse[OrgDetail])
async def update_org(
    org_id: uuid.UUID,
    body: OrgUpdate,
    service: OrgServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[OrgDetail]:
    """编辑组织信息（org_admin；缺省不动）。"""
    detail = await service.update(user, org_id, body)
    await db.commit()
    return ok(detail)


@router.delete("/{org_id}")
async def disband_org(
    org_id: uuid.UUID,
    service: OrgServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_admin),
) -> ApiResponse[None]:
    """解散组织（软解散，仅站点 admin）：清理 org 授权与成员状态，题库题目归档。"""
    await service.disband(user, org_id)
    await db.commit()
    return ok(None)


@router.get("/{org_id}/members", response_model=ApiResponse[PaginatedResponse[OrgMemberOut]])
async def list_members(
    org_id: uuid.UUID,
    service: OrgServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[OrgMemberOut]]:
    """组织成员列表（组织任意角色可查；keyword 模糊匹配昵称）。"""
    items, total = await service.list_members(user, org_id, status, page, page_size, keyword)
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


@router.post("/{org_id}/members")
async def add_members(
    org_id: uuid.UUID,
    body: OrgMemberAdd,
    service: OrgServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """直接添加成员（org_admin 拉人，可批量；已在册跳过）。"""
    await service.add_members(user, org_id, body)
    await db.commit()
    return ok(None)


@router.delete("/{org_id}/members/{user_id}")
async def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    service: OrgServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """移出成员（org_admin；最后一名 org_admin 3004）。"""
    await service.remove_member(user, org_id, user_id)
    await db.commit()
    return ok(None)


@router.put("/{org_id}/members/{user_id}/admin")
async def set_admin(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    body: OrgAdminFlag,
    service: OrgServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """授予 / 撤销组织管理员（org_admin 或站点 admin；最后一名 3004）。"""
    await service.set_admin(user, org_id, user_id, body)
    await db.commit()
    return ok(None)


@router.put("/{org_id}/members/{user_id}/note")
async def set_member_note(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    body: OrgMemberNote,
    service: OrgServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """设置成员备注（本人可备注自己；org_admin 可备注任意成员；空串 = 清除）。"""
    await service.set_member_note(user, org_id, user_id, body)
    await db.commit()
    return ok(None)


@router.post("/{org_id}/teams", response_model=ApiResponse[TeamSummary])
async def create_team(
    org_id: uuid.UUID,
    body: TeamCreate,
    service: OrgServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[TeamSummary]:
    """在组织内创建团队（org_admin）：团队 org_id 落本组织，创建者自动 team_creator。"""
    summary = await service.create_team(user, org_id, body)
    await db.commit()
    return ok(summary)


@router.get("/{org_id}/teams", response_model=ApiResponse[PaginatedResponse[TeamSummary]])
async def list_teams(
    org_id: uuid.UUID,
    service: OrgServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[TeamSummary]]:
    """组织名下团队列表（组织成员可见；带成员数与我的团队角色）。"""
    items, total = await service.list_teams(user, org_id, page, page_size, keyword, status)
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


# ---- 组织题库（docs/contracts/orgs.md；管理动作复用 /problems/{id}/... 统一端点） ----


@router.get(
    "/{org_id}/problems", response_model=ApiResponse[PaginatedResponse[TeamProblemSummary]]
)
async def list_org_problems(
    org_id: uuid.UUID,
    service: OrgServiceDep,
    problems: ProblemServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[TeamProblemSummary]]:
    """组织题库列表：缺省仅 published；status='draft' 草稿视图（全组织草稿均可见，
    无个人私稿）；归档任何视图不返回；管理视图回填 needs_reverification。"""
    await service.require_roles(user, org_id, level="member")
    rows, total = await problems.list_org_problems(
        org_id, keyword=keyword, status=status, page=page, page_size=page_size
    )
    items = [TeamProblemSummary.model_validate(row) for row in rows]
    flags = await problems.verification_flags([row.id for row in rows])
    for item in items:
        item.needs_reverification = flags.get(item.id, False)
    await problems.attach_counters(items)
    await problems.attach_tags(items)
    await problems.attach_solve_status(items, user)
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


@router.post("/{org_id}/problems", response_model=ApiResponse[TeamProblemSummary])
async def create_org_problem(
    org_id: uuid.UUID,
    body: ProblemCreate,
    service: OrgServiceDep,
    problems: ProblemServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[TeamProblemSummary]:
    """组织题库直建题目（org_member）：visibility 恒 org_visible，owner_id 为创建人署名。"""
    await service.require_roles(user, org_id, level="member")
    problem = await problems.create(user, body, org_id=org_id)
    await db.commit()
    item = TeamProblemSummary.model_validate(problem)
    await problems.attach_counters([item])
    await problems.attach_tags([item])
    return ok(item)


@router.get("/{org_id}/problems/{problem_id}", response_model=ApiResponse[TeamProblemSummary])
async def get_org_problem(
    org_id: uuid.UUID,
    problem_id: uuid.UUID,
    service: OrgServiceDep,
    problems: ProblemServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[TeamProblemSummary]:
    """组织题目详情（组织上下文统一入口）：归属校验后复用题库详情装配。"""
    await service.require_roles(user, org_id, level="member")
    detail = await problems.get_org_problem_detail(org_id, problem_id, user)
    return ok(TeamProblemSummary.model_validate(detail))

"""团队路由（docs/contracts/teams.md /teams* 端点，统一前缀 /api/v1）。

团队角色经 user_roles（scope='team'）应用层判定；路由仅做 HTTP 装配，
权限 / 状态校验收敛在 TeamService。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, TeamServiceDep
from app.core.dependency import get_current_user
from app.models.user import User
from app.schemas.team import (
    TeamAdminFlag,
    TeamApplicationOut,
    TeamApplicationReview,
    TeamApplicationSubmit,
    TeamCreate,
    TeamDetail,
    TeamInviteCreated,
    TeamInviteResolved,
    TeamMemberOut,
    TeamSummary,
    TeamUpdate,
)
from app.utils.pagination import PaginatedResponse
from app.utils.response import ApiResponse, ok

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", response_model=ApiResponse[TeamSummary])
async def create_team(
    body: TeamCreate,
    service: TeamServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[TeamSummary]:
    """创建团队（admin/tutor）：自动写创建者成员记录 + team_creator 授权。"""
    summary = await service.create(user, body)
    await db.commit()  # 显式提交：确保团队 / 成员 / 授权持久化
    return ok(summary)


@router.get("/invites/{token}", response_model=ApiResponse[TeamInviteResolved])
async def resolve_invite(token: str, service: TeamServiceDep) -> ApiResponse[TeamInviteResolved]:
    """解析邀请链接（public）：返回团队与有效期（落地页展示用）。"""
    return ok(await service.resolve_invite(token))


@router.get("/mine", response_model=ApiResponse[PaginatedResponse[TeamSummary]])
async def list_my_teams(
    service: TeamServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=64),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[TeamSummary]]:
    """我的团队列表（在册成员，创建时间倒序；keyword 模糊匹配团队名称）。"""
    items, total = await service.list_my_teams(user, page, page_size, keyword)
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


@router.get("/{team_id}", response_model=ApiResponse[TeamDetail])
async def get_team(
    team_id: uuid.UUID,
    service: TeamServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[TeamDetail]:
    """团队详情（成员可见）。"""
    return ok(await service.get_detail(user, team_id))


@router.put("/{team_id}", response_model=ApiResponse[TeamDetail])
async def update_team(
    team_id: uuid.UUID,
    body: TeamUpdate,
    service: TeamServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[TeamDetail]:
    """编辑团队信息（team_creator / team_admin；缺省不动）。"""
    detail = await service.update(user, team_id, body)
    await db.commit()
    return ok(detail)


@router.get("/{team_id}/members", response_model=ApiResponse[PaginatedResponse[TeamMemberOut]])
async def list_members(
    team_id: uuid.UUID,
    service: TeamServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[TeamMemberOut]]:
    """成员列表（team 角色可查；带创建者 / 管理员标记）。"""
    items, total = await service.list_members(user, team_id, status, page, page_size)
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


@router.post("/{team_id}/invites", response_model=ApiResponse[TeamInviteCreated])
async def create_invite(
    team_id: uuid.UUID,
    service: TeamServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[TeamInviteCreated]:
    """生成邀请链接（team_creator / team_admin；写 Redis，TTL 取配置）。"""
    return ok(await service.create_invite(user, team_id))


@router.post("/{team_id}/applications", response_model=ApiResponse[None])
async def submit_application(
    team_id: uuid.UUID,
    body: TeamApplicationSubmit,
    service: TeamServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """提交加入申请（已入队或已有 pending 申请返回 3003；邀请链接经校验记录来源）。"""
    await service.submit_application(user, team_id, body)
    await db.commit()
    return ok(None)


@router.get(
    "/{team_id}/applications", response_model=ApiResponse[PaginatedResponse[TeamApplicationOut]]
)
async def list_applications(
    team_id: uuid.UUID,
    service: TeamServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[TeamApplicationOut]]:
    """申请列表（team_creator / team_admin；status 缺省 = pending）。"""
    items, total = await service.list_applications(user, team_id, status, page, page_size)
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


@router.post("/{team_id}/applications/{application_id}/review", response_model=ApiResponse[None])
async def review_application(
    team_id: uuid.UUID,
    application_id: uuid.UUID,
    body: TeamApplicationReview,
    service: TeamServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """审批加入申请（通过写在册成员 + team_member 授权；拒绝仅记录状态）。"""
    await service.review_application(user, team_id, application_id, body)
    await db.commit()
    return ok(None)


@router.post("/{team_id}/members/{user_id}/admin", response_model=ApiResponse[None])
async def set_member_admin(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    body: TeamAdminFlag,
    service: TeamServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """分配 / 取消团队管理员（仅创建者；分配即写授权，取消即删除）。"""
    await service.set_admin(user, team_id, user_id, body)
    await db.commit()
    return ok(None)


@router.delete("/{team_id}/members/{user_id}", response_model=ApiResponse[None])
async def kick_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    service: TeamServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """踢出成员（team_creator / team_admin；清理成员状态与团队授权）。"""
    await service.kick(user, team_id, user_id)
    await db.commit()
    return ok(None)


@router.post("/{team_id}/exit", response_model=ApiResponse[None])
async def exit_team(
    team_id: uuid.UUID,
    service: TeamServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """主动退出（成员本人；创建者不可退出，只能解散）。"""
    await service.exit(user, team_id)
    await db.commit()
    return ok(None)


@router.delete("/{team_id}", response_model=ApiResponse[None])
async def disband_team(
    team_id: uuid.UUID,
    service: TeamServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """解散团队（软解散，仅创建者；清理全部团队授权与成员状态）。"""
    await service.disband(user, team_id)
    await db.commit()
    return ok(None)

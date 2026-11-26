"""社区路由（docs/contracts/community.md 端点，统一前缀 /api/v1）。

官方题解 / 用户题解 / 评论 / 举报；管理端点（/admin/solutions*、/admin/comments*）
注册在 admin 路由（与举报处理同层）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    CommunityServiceDep,
    SessionDep,
    get_current_user,
    get_optional_user,
)
from app.models.user import User
from app.schemas.community import (
    CodeShareCreate,
    CodeShareDetail,
    CodeShareSummary,
    CommentCreate,
    CommentOut,
    EditorialOut,
    ReportCreate,
    SolutionCreate,
    SolutionDetail,
    SolutionSummary,
    SolutionUpdate,
)
from app.utils.pagination import PaginatedResponse
from app.utils.response import ApiResponse, ok

router = APIRouter(tags=["community"])


# ---- 官方题解 ----


@router.get(
    "/problems/{problem_id}/editorial", response_model=ApiResponse[EditorialOut]
)
async def get_editorial(
    problem_id: uuid.UUID,
    service: CommunityServiceDep,
    user: User | None = Depends(get_optional_user),
) -> ApiResponse[EditorialOut]:
    """官方题解（problems.solution 浏览视图；比赛进行中 3002，community.md）。"""
    return ok(await service.get_editorial(problem_id, user))


# ---- 用户题解 ----


@router.get(
    "/problems/{problem_id}/solutions",
    response_model=ApiResponse[PaginatedResponse[SolutionSummary]],
)
async def list_solutions(
    problem_id: uuid.UUID,
    service: CommunityServiceDep,
    user: User | None = Depends(get_optional_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    mine: bool = Query(default=False),
) -> ApiResponse[PaginatedResponse[SolutionSummary]]:
    """分享题解分页（published；mine=true 返回本人全部状态，需登录）。"""
    return ok(
        await service.list_solutions(problem_id, user, page, page_size, keyword, mine)
    )


@router.post(
    "/problems/{problem_id}/solutions",
    response_model=ApiResponse[SolutionDetail],
)
async def create_solution(
    problem_id: uuid.UUID,
    body: SolutionCreate,
    service: CommunityServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SolutionDetail]:
    detail = await service.create_solution(problem_id, user, body)
    await db.commit()  # 显式提交：确保数据持久化后再返回
    return ok(detail)


@router.get("/solutions/{solution_id}", response_model=ApiResponse[SolutionDetail])
async def get_solution(
    solution_id: uuid.UUID,
    service: CommunityServiceDep,
    user: User | None = Depends(get_optional_user),
) -> ApiResponse[SolutionDetail]:
    return ok(await service.get_solution(solution_id, user))


@router.put("/solutions/{solution_id}", response_model=ApiResponse[SolutionDetail])
async def update_solution(
    solution_id: uuid.UUID,
    body: SolutionUpdate,
    service: CommunityServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SolutionDetail]:
    detail = await service.update_solution(solution_id, user, body)
    await db.commit()
    return ok(detail)


@router.delete("/solutions/{solution_id}", response_model=ApiResponse[None])
async def remove_solution(
    solution_id: uuid.UUID,
    service: CommunityServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    await service.remove_solution(solution_id, user)
    await db.commit()
    return ok(None)


# ---- 评论 ----


@router.get(
    "/comments", response_model=ApiResponse[PaginatedResponse[CommentOut]]
)
async def list_comments(
    service: CommunityServiceDep,
    user: User | None = Depends(get_optional_user),
    target_type: str = Query(...),
    target_id: uuid.UUID = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    parent_id: uuid.UUID | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> ApiResponse[PaginatedResponse[CommentOut]]:
    """评论分页：一级评论（含回复预览）或 parent_id 指定回复页；include_deleted 仅 admin。"""
    return ok(
        await service.list_comments(
            target_type, target_id, user, page, page_size, parent_id, include_deleted
        )
    )


@router.post("/comments", response_model=ApiResponse[CommentOut])
async def create_comment(
    body: CommentCreate,
    service: CommunityServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[CommentOut]:
    comment = await service.create_comment(user, body)
    await db.commit()
    return ok(comment)


@router.delete("/comments/{comment_id}", response_model=ApiResponse[None])
async def delete_comment(
    comment_id: uuid.UUID,
    service: CommunityServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    await service.delete_comment(comment_id, user)
    await db.commit()
    return ok(None)


# ---- 代码广场 ----


@router.get("/codes", response_model=ApiResponse[PaginatedResponse[CodeShareSummary]])
async def list_code_shares(
    service: CommunityServiceDep,
    user: User | None = Depends(get_optional_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    language: str | None = Query(default=None, max_length=32),
    mine: bool = Query(default=False),
) -> ApiResponse[PaginatedResponse[CodeShareSummary]]:
    """代码广场分享分页（published；mine=true 返回本人全部状态，需登录）。"""
    return ok(
        await service.list_code_shares(user, page, page_size, keyword, language, mine)
    )


@router.post("/codes", response_model=ApiResponse[CodeShareDetail])
async def create_code_share(
    body: CodeShareCreate,
    service: CommunityServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[CodeShareDetail]:
    detail = await service.create_code_share(user, body)
    await db.commit()
    return ok(detail)


@router.get("/codes/{share_id}", response_model=ApiResponse[CodeShareDetail])
async def get_code_share(
    share_id: uuid.UUID,
    service: CommunityServiceDep,
    user: User | None = Depends(get_optional_user),
) -> ApiResponse[CodeShareDetail]:
    return ok(await service.get_code_share(share_id, user))


@router.delete("/codes/{share_id}", response_model=ApiResponse[None])
async def remove_code_share(
    share_id: uuid.UUID,
    service: CommunityServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    await service.remove_code_share(share_id, user)
    await db.commit()
    return ok(None)


# ---- 举报 ----


@router.post("/reports", response_model=ApiResponse[None])
async def create_report(
    body: ReportCreate,
    service: CommunityServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    await service.create_report(user, body)
    await db.commit()
    return ok(None)

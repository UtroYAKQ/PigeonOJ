"""题单路由（docs/contracts/problem-sets.md /problem-sets* 端点，统一前缀 /api/v1）。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import ProblemSetServiceDep, SessionDep, SubmissionServiceDep
from app.core.dependency import get_current_user, get_optional_user
from app.models.user import User
from app.rpc.judge_gateway import dispatch_submission
from app.schemas.judge import SubmissionCreate, SubmissionCreatedResponse
from app.schemas.problem import ProblemDetail
from app.schemas.problem_set import (
    ProblemSetCreate,
    ProblemSetDetail,
    ProblemSetItemsUpdate,
    ProblemSetSubmissionCreate,
    ProblemSetSummary,
    ProblemSetUpdate,
)
from app.utils.pagination import PaginatedResponse
from app.utils.response import ApiResponse, ok

router = APIRouter(prefix="/problem-sets", tags=["problem-sets"])


@router.get("", response_model=ApiResponse[PaginatedResponse[ProblemSetSummary]])
async def list_problem_sets(
    service: ProblemSetServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    mine: bool = Query(default=False),
    viewer: User | None = Depends(get_optional_user),
) -> ApiResponse[PaginatedResponse[ProblemSetSummary]]:
    """题单中心：公开且未下线的全站题单；mine=true 仅本人未下线题单（含私有，须登录）。"""
    rows, total = await service.list_center(
        page=page, page_size=page_size, keyword=keyword, viewer=viewer, mine=mine
    )
    return ok(PaginatedResponse(items=rows, total=total, page=page, page_size=page_size))


@router.post("", response_model=ApiResponse[ProblemSetSummary])
async def create_problem_set(
    body: ProblemSetCreate,
    service: ProblemSetServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemSetSummary]:
    """创建题单（admin/tutor；团队题单随 teams 模块开放）。"""
    summary = await service.create(user, body)
    await db.commit()  # 显式提交：确保数据持久化后再返回
    return ok(summary)


@router.get("/{set_id}", response_model=ApiResponse[ProblemSetDetail])
async def get_problem_set(
    set_id: uuid.UUID,
    service: ProblemSetServiceDep,
    user: User | None = Depends(get_optional_user),
) -> ApiResponse[ProblemSetDetail]:
    """题单详情（含题目编排；私有 / 已下线题单仅创建者与管理角色可见）。"""
    return ok(await service.get_detail(set_id, user))


@router.put("/{set_id}", response_model=ApiResponse[ProblemSetSummary])
async def update_problem_set(
    set_id: uuid.UUID,
    body: ProblemSetUpdate,
    service: ProblemSetServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemSetSummary]:
    """编辑题单元信息（admin/tutor）。"""
    summary = await service.update(set_id, user, body)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(summary)


@router.put("/{set_id}/items", response_model=ApiResponse[None])
async def replace_problem_set_items(
    set_id: uuid.UUID,
    body: ProblemSetItemsUpdate,
    service: ProblemSetServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """编排题目：全量替换题单内列表（题目须已发布公开；同题单内不得重复）。"""
    await service.replace_items(set_id, user, body)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(None)


@router.post("/{set_id}/archive", response_model=ApiResponse[ProblemSetSummary])
async def archive_problem_set(
    set_id: uuid.UUID,
    service: ProblemSetServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemSetSummary]:
    """下线题单（status='archived'，不做物理删除）。"""
    summary = await service.archive(set_id, user)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(summary)


@router.get(
    "/{set_id}/problems/{problem_id}", response_model=ApiResponse[ProblemDetail]
)
async def get_problem_set_problem(
    set_id: uuid.UUID,
    problem_id: uuid.UUID,
    service: ProblemSetServiceDep,
    user: User | None = Depends(get_optional_user),
) -> ApiResponse[ProblemDetail]:
    """题单内题目详情（统一入口）：题单可见 + 题目属于该题单校验后，
    返回与 GET /problems/{id} 完全一致的详情装配（docs/contracts/problem-sets.md）。"""
    return ok(await service.get_problem_detail(set_id, problem_id, user))


@router.post(
    "/{set_id}/problems/{problem_id}/submissions",
    response_model=ApiResponse[SubmissionCreatedResponse],
)
async def create_problem_set_submission(
    set_id: uuid.UUID,
    problem_id: uuid.UUID,
    body: ProblemSetSubmissionCreate,
    service: ProblemSetServiceDep,
    submission_service: SubmissionServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SubmissionCreatedResponse]:
    """题单内交题：题单可见 + 题目属于该题单校验通过后，走统一判题提交链路
    （docs/contracts/problem-sets.md 交题端点；落库 / 派发 / 计分与 POST /submissions 完全一致）。
    """
    await service.ensure_set_problem(set_id, problem_id, user)
    submission = await submission_service.create(
        user,
        SubmissionCreate(problem_id=problem_id, language=body.language, code=body.code),
    )
    await db.commit()  # 显式提交：确保 submission 已持久化，dispatch_submission 才能找到它
    await dispatch_submission(submission.id)
    return ok(SubmissionCreatedResponse(submission_id=str(submission.id), status=submission.status))

"""比赛路由（docs/contracts/contests.md /contests* 端点，统一前缀 /api/v1）。

比赛上下文统一入口：赛内题目详情与交题经本模块端点（归属 / 窗口校验），
不跨模块直调题库 / 判题端点（docs/frontend.md「路由上下文隔离」规则 4）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependency import get_current_user, get_optional_user
from app.models.user import User
from app.rpc.judge_gateway import dispatch_submission
from app.schemas.contest import (
    BoardOut,
    ContestCreate,
    ContestDetail,
    ContestSubmissionItem,
    ContestSummary,
    ContestUpdate,
    MyContestItem,
)
from app.schemas.judge import SubmissionCreatedResponse, SubmissionDetailOut
from app.schemas.problem import ProblemDetail
from app.schemas.problem_set import ProblemSetSubmissionCreate as ContestSubmissionBody
from app.services.contest import ContestService
from app.services.judge import SubmissionService
from app.utils.pagination import PaginatedResponse
from app.utils.response import ApiResponse, ok

router = APIRouter(prefix="/contests", tags=["contests"])


@router.get("", response_model=ApiResponse[PaginatedResponse[ContestSummary]])
async def list_contests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=128),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PaginatedResponse[ContestSummary]]:
    """比赛中心：公开比赛（可按状态过滤与名称关键字搜索）。"""
    rows, total = await ContestService(db).list_center(
        page=page, page_size=page_size, status=status, keyword=keyword
    )
    return ok(PaginatedResponse(items=rows, total=total, page=page, page_size=page_size))


@router.get("/me", response_model=ApiResponse[PaginatedResponse[MyContestItem]])
async def list_my_contests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PaginatedResponse[MyContestItem]]:
    """我的比赛（我报名的比赛 + 报名状态）。"""
    rows, total = await ContestService(db).list_my_contests(
        user, page=page, page_size=page_size, status=status
    )
    return ok(PaginatedResponse(items=rows, total=total, page=page, page_size=page_size))


@router.post("", response_model=ApiResponse[ContestSummary])
async def create_contest(
    body: ContestCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ApiResponse[ContestSummary]:
    """创建比赛（admin/tutor；团队赛随 teams 模块开放）。"""
    summary = await ContestService(db).create(user, body)
    await db.commit()  # 显式提交：确保数据持久化后再返回
    return ok(summary)


@router.get("/{contest_id}", response_model=ApiResponse[ContestDetail])
async def get_contest(
    contest_id: uuid.UUID,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ContestDetail]:
    """比赛详情（报名状态 / 时间窗口能力位；题目仅在看题窗口内携带）。"""
    return ok(await ContestService(db).get_detail(contest_id, user))


@router.get("/{contest_id}/submissions", response_model=ApiResponse[PaginatedResponse[ContestSubmissionItem]])
async def list_contest_submissions(
    contest_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PaginatedResponse[ContestSubmissionItem]]:
    """比赛提交记录（比赛期间对所有人隐藏，赛后仅已报名用户与管理角色可见）。"""
    items, total = await ContestService(db).list_submissions(
        user, contest_id, page=page, page_size=page_size
    )
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


@router.get(
    "/{contest_id}/submissions/{submission_id}",
    response_model=ApiResponse[SubmissionDetailOut],
)
async def get_contest_submission(
    contest_id: uuid.UUID,
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SubmissionDetailOut]:
    """比赛提交详情（统一入口）：窗口校验后复用判题详情装配（计分按提交行赛制快照）。"""
    submission = await ContestService(db).get_visible_submission(user, contest_id, submission_id)
    return ok(await SubmissionService(db).build_detail(submission))


@router.get(
    "/{contest_id}/board/{cell_user_id}/{problem_id}/accepted",
    response_model=ApiResponse[list[ContestSubmissionItem]],
)
async def list_board_cell_accepted(
    contest_id: uuid.UUID,
    cell_user_id: uuid.UUID,
    problem_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[ContestSubmissionItem]]:
    """榜单单格成功提交（赛后开放，随提交记录窗口）：该 (选手, 题目) 比赛内的 AC 提交列表。"""
    items = await ContestService(db).cell_submissions(user, contest_id, cell_user_id, problem_id)
    return ok(items)


@router.put("/{contest_id}", response_model=ApiResponse[ContestSummary])
async def update_contest(
    contest_id: uuid.UUID, body: ContestUpdate,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> ApiResponse[ContestSummary]:
    """编辑比赛（admin/tutor）。"""
    summary = await ContestService(db).update(contest_id, user, body)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(summary)


@router.post("/{contest_id}/register", response_model=ApiResponse[None])
async def register_contest(
    contest_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ApiResponse[None]:
    """报名（公开比赛；重复 3003，截止 3002）。"""
    await ContestService(db).register(user, contest_id)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(None)


@router.get("/{contest_id}/problems", response_model=ApiResponse[list])
async def list_contest_problems(
    contest_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ApiResponse[list]:
    """比赛题目列表（已报名 + 开赛后；letter / 分值随行）。"""
    items = await ContestService(db).list_problems(user, contest_id)
    return ok(items)


@router.get("/{contest_id}/problems/search", response_model=ApiResponse[PaginatedResponse])
async def search_contest_problems(
    contest_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PaginatedResponse]:
    """编排页题目搜索（统一入口）：已发布且（全站公开 或 本人私有），标题模糊。

    仅比赛管理角色可调（require_manage），供编排步骤从题库挑选题目。
    """
    rows, total = await ContestService(db).search_arrangeable_problems(
        user,
        contest_id=contest_id,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ok(PaginatedResponse(items=rows, total=total, page=page, page_size=page_size))


@router.get("/{contest_id}/problems/{problem_id}", response_model=ApiResponse[ProblemDetail])
async def get_contest_problem(
    contest_id: uuid.UUID,
    problem_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProblemDetail]:
    """比赛内题目详情（统一入口）：窗口校验后与题库详情装配一致。"""
    return ok(await ContestService(db).get_problem_detail(user, contest_id, problem_id))


@router.post(
    "/{contest_id}/problems/{problem_id}/submissions",
    response_model=ApiResponse[SubmissionCreatedResponse],
)
async def create_contest_submission(
    contest_id: uuid.UUID,
    problem_id: uuid.UUID,
    body: ContestSubmissionBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SubmissionCreatedResponse]:
    """比赛交题（统一入口）：窗口校验后落 contest 提交并派发判题。

    赛后（end_time 之后）自动标记 is_after_contest 补题，不计榜单。
    """
    submission, _after = await ContestService(db).submit_problem(
        user,
        contest_id,
        problem_id,
        language=body.language,
        code=body.code,
        create_submission=SubmissionService(db).create_contest_submission,
    )
    await db.commit()  # 显式提交：确保 submission 已持久化，dispatch_submission 才能找到它
    await dispatch_submission(submission.id)
    return ok(SubmissionCreatedResponse(submission_id=str(submission.id), status=submission.status))


@router.get("/{contest_id}/board", response_model=ApiResponse[BoardOut])
async def get_contest_board(
    contest_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[BoardOut]:
    """榜单（封榜时按冻结快照展示；解冻由 admin/tutor 手动触发）。"""
    return ok(await ContestService(db).board(contest_id))


@router.post("/{contest_id}/unfreeze", response_model=ApiResponse[ContestSummary])
async def unfreeze_contest_board(
    contest_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ApiResponse[ContestSummary]:
    """手动解冻榜单（admin/tutor）：从 submissions 权威重算并回填封榜期间结果。"""
    summary = await ContestService(db).unfreeze(user, contest_id)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(summary)

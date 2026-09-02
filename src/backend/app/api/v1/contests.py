"""比赛路由（docs/contracts/contests.md /contests* 端点，统一前缀 /api/v1）。

比赛上下文统一入口：赛内题目详情与交题经本模块端点（归属 / 窗口校验），
不跨模块直调题库 / 判题端点（docs/frontend.md「路由上下文隔离」规则 4）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import ContestServiceDep, SessionDep, SubmissionServiceDep
from app.core.dependency import get_current_user, get_optional_user
from app.core.exceptions import APIError, PARAM_FORMAT_INVALID
from app.enums import SubmissionStatus
from app.models.user import User
from app.rpc.judge_gateway import dispatch_submission
from app.schemas.contest import (
    AnnouncementUpdate,
    BoardOut,
    ContestCreate,
    ContestDetail,
    ContestSubmissionItem,
    ContestSummary,
    ContestUpdate,
    MyContestItem,
    ScoreboardShowOut,
)
from app.schemas.judge import SubmissionCreatedResponse, SubmissionDetailOut
from app.schemas.problem import ProblemDetail
from app.schemas.problem_set import ProblemSetSubmissionCreate as ContestSubmissionBody
from app.utils.pagination import PaginatedResponse
from app.utils.response import ApiResponse, ok

router = APIRouter(prefix="/contests", tags=["contests"])


@router.get("", response_model=ApiResponse[PaginatedResponse[ContestSummary]])
async def list_contests(
    service: ContestServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=128),
) -> ApiResponse[PaginatedResponse[ContestSummary]]:
    """比赛中心：公开比赛（可按状态过滤与名称关键字搜索）。"""
    rows, total = await service.list_center(
        page=page, page_size=page_size, status=status, keyword=keyword
    )
    return ok(PaginatedResponse(items=rows, total=total, page=page, page_size=page_size))


@router.get("/me", response_model=ApiResponse[PaginatedResponse[MyContestItem]])
async def list_my_contests(
    service: ContestServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[MyContestItem]]:
    """我的比赛（我报名的比赛 + 报名状态）。"""
    rows, total = await service.list_my_contests(
        user, page=page, page_size=page_size, status=status
    )
    return ok(PaginatedResponse(items=rows, total=total, page=page, page_size=page_size))


@router.post("", response_model=ApiResponse[ContestSummary])
async def create_contest(
    body: ContestCreate,
    service: ContestServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ContestSummary]:
    """创建比赛（admin/tutor；团队赛随 teams 模块开放）。"""
    summary = await service.create(user, body)
    await db.commit()  # 显式提交：确保数据持久化后再返回
    return ok(summary)


@router.get("/{contest_id}", response_model=ApiResponse[ContestDetail])
async def get_contest(
    contest_id: uuid.UUID,
    service: ContestServiceDep,
    user: User | None = Depends(get_optional_user),
) -> ApiResponse[ContestDetail]:
    """比赛详情（报名状态 / 时间窗口能力位；题目仅在看题窗口内携带）。"""
    return ok(await service.get_detail(contest_id, user))


@router.get("/{contest_id}/submissions", response_model=ApiResponse[PaginatedResponse[ContestSubmissionItem]])
async def list_contest_submissions(
    contest_id: uuid.UUID,
    service: ContestServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=64),
    language: str | None = Query(default=None, max_length=32),
    status: str | None = Query(default=None),
    problem_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[ContestSubmissionItem]]:
    """比赛提交记录（管理角色随时可见，参赛者赛后开放）。

    keyword 模糊匹配提交人昵称；language / status / problem_id 精确过滤。
    """
    try:
        status_value = SubmissionStatus(status) if status else None
    except ValueError as exc:
        raise APIError(PARAM_FORMAT_INVALID, "查询参数不合法", 400) from exc
    items, total = await service.list_submissions(
        user, contest_id, page=page, page_size=page_size,
        keyword=keyword, language=language, status=status_value, problem_id=problem_id,
    )
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


@router.get(
    "/{contest_id}/submissions/{submission_id}",
    response_model=ApiResponse[SubmissionDetailOut],
)
async def get_contest_submission(
    contest_id: uuid.UUID,
    submission_id: uuid.UUID,
    service: ContestServiceDep,
    submission_service: SubmissionServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SubmissionDetailOut]:
    """比赛提交详情（统一入口）：窗口校验后复用判题详情装配（计分按提交行赛制快照）。"""
    submission = await service.get_visible_submission(user, contest_id, submission_id)
    return ok(await submission_service.build_detail(submission))


@router.get(
    "/{contest_id}/board/{cell_user_id}/{problem_id}/accepted",
    response_model=ApiResponse[list[ContestSubmissionItem]],
)
async def list_board_cell_accepted(
    contest_id: uuid.UUID,
    cell_user_id: uuid.UUID,
    problem_id: uuid.UUID,
    service: ContestServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[list[ContestSubmissionItem]]:
    """榜单单格成功提交（赛后开放，随提交记录窗口）：该 (选手, 题目) 比赛内的 AC 提交列表。"""
    items = await service.cell_submissions(user, contest_id, cell_user_id, problem_id)
    return ok(items)


@router.put("/{contest_id}", response_model=ApiResponse[ContestSummary])
async def update_contest(
    contest_id: uuid.UUID, body: ContestUpdate,
    service: ContestServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ContestSummary]:
    """编辑比赛（admin/tutor）。"""
    summary = await service.update(contest_id, user, body)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(summary)


@router.post("/{contest_id}/register", response_model=ApiResponse[None])
async def register_contest(
    contest_id: uuid.UUID,
    service: ContestServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """报名（公开比赛；重复 3003，截止 3002）。"""
    await service.register(user, contest_id)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(None)


@router.get("/{contest_id}/problems", response_model=ApiResponse[list])
async def list_contest_problems(
    contest_id: uuid.UUID,
    service: ContestServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[list]:
    """比赛题目列表（已报名 + 开赛后；letter / 分值随行）。"""
    items = await service.list_problems(user, contest_id)
    return ok(items)


@router.get("/{contest_id}/problems/search", response_model=ApiResponse[PaginatedResponse])
async def search_contest_problems(
    contest_id: uuid.UUID,
    service: ContestServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse]:
    """编排页题目搜索（统一入口）：已发布且（全站公开 或 本人私有），标题模糊。

    仅比赛管理角色可调（require_manage），供编排步骤从题库挑选题目。
    """
    rows, total = await service.search_arrangeable_problems(
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
    service: ContestServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemDetail]:
    """比赛内题目详情（统一入口）：窗口校验后与题库详情装配一致。"""
    return ok(await service.get_problem_detail(user, contest_id, problem_id))


@router.post(
    "/{contest_id}/problems/{problem_id}/submissions",
    response_model=ApiResponse[SubmissionCreatedResponse],
)
async def create_contest_submission(
    contest_id: uuid.UUID,
    problem_id: uuid.UUID,
    body: ContestSubmissionBody,
    service: ContestServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SubmissionCreatedResponse]:
    """比赛交题（统一入口）：窗口校验后落 contest 提交并派发判题。

    判题上下文端口（ContestSubmitter）由 deps.py 装配进 ContestService。
    赛后（end_time 之后）自动标记 is_after_contest 补题，不计榜单。
    """
    submission, _after = await service.submit_problem(
        user,
        contest_id,
        problem_id,
        language=body.language,
        code=body.code,
    )
    await db.commit()  # 显式提交：确保 submission 已持久化，dispatch_submission 才能找到它
    await dispatch_submission(submission.id)
    return ok(SubmissionCreatedResponse(submission_id=str(submission.id), status=submission.status))


@router.get("/{contest_id}/board", response_model=ApiResponse[BoardOut])
async def get_contest_board(
    contest_id: uuid.UUID,
    service: ContestServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[BoardOut]:
    """榜单（封榜时按冻结快照展示；解冻由 admin/tutor 手动触发）。"""
    return ok(await service.board(contest_id))


@router.post("/{contest_id}/unfreeze", response_model=ApiResponse[ContestSummary])
async def unfreeze_contest_board(
    contest_id: uuid.UUID,
    service: ContestServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ContestSummary]:
    """手动解冻榜单（admin/tutor）：从 submissions 权威重算并回填封榜期间结果（仅赛后）。"""
    summary = await service.unfreeze(user, contest_id)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(summary)


@router.put("/{contest_id}/announcement", response_model=ApiResponse[ContestSummary])
async def update_contest_announcement(
    contest_id: uuid.UUID,
    body: AnnouncementUpdate,
    service: ContestServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ContestSummary]:
    """更新比赛公告（管理角色；赛时允许，空字符串 = 清空）。"""
    summary = await service.update_announcement(user, contest_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(summary)


@router.get("/{contest_id}/scoreboard-show", response_model=ApiResponse[ScoreboardShowOut])
async def get_scoreboard_show(
    contest_id: uuid.UUID,
    service: ContestServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ScoreboardShowOut]:
    """滚榜数据（管理角色专用，只读不解冻）：快照榜 + 最终榜 + 封榜期揭晓序列。"""
    return ok(await service.scoreboard_show(user, contest_id))

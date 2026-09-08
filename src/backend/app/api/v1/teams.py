"""团队路由（docs/contracts/teams.md /teams* 端点，统一前缀 /api/v1）。

团队角色经 user_roles（scope='team'）应用层判定；路由仅做 HTTP 装配，
权限 / 状态校验收敛在 TeamService 与 TeamSpaceService（团队空间门面）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    SelfTestServiceDep,
    SessionDep,
    TeamServiceDep,
    TeamSpaceServiceDep,
)
from app.core.dependency import get_current_user, get_optional_user
from app.core.exceptions import PARAM_FORMAT_INVALID, APIError
from app.models.user import User
from app.rpc.judge_gateway import dispatch_submission, dispatch_run_code
from app.schemas.judge import (
    SelfTestRequest,
    SelfTestResultOut,
    SubmissionCreatedResponse,
)
from app.schemas.problem import ProblemDetail, ProblemUpdate
from app.schemas.problem_set import (
    ProblemSetDetail,
    ProblemSetItemsUpdate,
    ProblemSetSubmissionCreate,
)
from app.schemas.team import (
    TeamAdminFlag,
    TeamApplicationOut,
    TeamApplicationReview,
    TeamApplicationSubmit,
    TeamContestCreate,
    TeamCreate,
    TeamDetail,
    TeamInviteCreated,
    TeamInviteResolved,
    TeamMemberOut,
    TeamProblemReferenceCreate,
    TeamProblemSetCreate,
    TeamSummary,
    TeamUpdate,
)
from app.schemas.contest import ContestSummary
from app.schemas.problem import TeamProblemSummary
from app.schemas.problem_set import ProblemSetSummary
from app.rpc.judge_gateway import GatewayUnavailableError, GatewayBusyError, GatewayTimeoutError
from app.core.exceptions import RATE_LIMITED, RATE_SEND_TOO_FREQUENT, SYSTEM_UPSTREAM_FAILURE
from app.utils.pagination import PaginatedResponse
from app.utils.response import ApiResponse, ok

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=ApiResponse[PaginatedResponse[TeamSummary]])
async def list_teams(
    service: TeamServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=64),
    mine: bool = Query(default=False),
    user: User | None = Depends(get_optional_user),
) -> ApiResponse[PaginatedResponse[TeamSummary]]:
    """团队中心列表：默认仅公开在册团队（匿名可看）；mine=true 为「我的团队」
    勾选（须登录，匿名 401），返回本人在册的团队（公开 + 私有）。"""
    if mine and user is None:
        from app.core.exceptions import AUTH_NOT_LOGGED_IN

        raise APIError(AUTH_NOT_LOGGED_IN, "查看我的团队需要登录", 401)
    items, total = await service.list_public_teams(
        user, page, page_size, keyword, mine=mine
    )
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


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
    keyword: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[TeamMemberOut]]:
    """成员列表（team 角色可查；带创建者 / 管理员标记；keyword 模糊昵称）。"""
    items, total = await service.list_members(user, team_id, status, page, page_size, keyword)
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


# ==================== 团队空间（docs/contracts/teams.md 团队空间节） ====================
# 注意：/problems/references、/problems/arrangeable 等静态段路由必须先于
# /problems/{problem_id} 注册（FastAPI 按注册顺序匹配，UUID 路径参数会吞掉静态段）。


@router.get(
    "/{team_id}/problems", response_model=ApiResponse[PaginatedResponse[TeamProblemSummary]]
)
async def list_team_problems(
    team_id: uuid.UUID,
    service: TeamSpaceServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    status: str | None = Query(default=None),
    visibility: str | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[TeamProblemSummary]]:
    """团队题库列表：成员见 published + team_visible；创建者 / 管理员主列表仅见
    已发布（草稿经 status=draft 进入草稿箱视图，仍仅本人草稿；归档不在团队空间
    返回）；keyword / status / visibility 过滤。"""
    items, total = await service.list_problems(
        user, team_id, keyword=keyword, status=status, visibility=visibility,
        page=page, page_size=page_size,
    )
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


@router.post(
    "/{team_id}/problems/references", response_model=ApiResponse[TeamProblemSummary]
)
async def reference_team_problem(
    team_id: uuid.UUID,
    body: TeamProblemReferenceCreate,
    service: TeamSpaceServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[TeamProblemSummary]:
    """引用本人全站题目进入团队题库（team_creator / team_admin；单向，无移出通道）。"""
    item = await service.reference_problem(user, team_id, body)
    await db.commit()
    return ok(item)


@router.get(
    "/{team_id}/problems/arrangeable",
    response_model=ApiResponse[PaginatedResponse[TeamProblemSummary]],
)
async def search_team_arrangeable_problems(
    team_id: uuid.UUID,
    service: TeamSpaceServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[TeamProblemSummary]]:
    """团队编排候选搜索（team_creator / team_admin）：已发布且
    （本团队题目 ∪ 全站公开 ∪ 本人私有）；团队题单编排挑题用。"""
    rows, total = await service.list_arrangeable_problems(
        user, team_id, keyword=keyword, page=page, page_size=page_size
    )
    return ok(PaginatedResponse(items=rows, total=total, page=page, page_size=page_size))


@router.get(
    "/{team_id}/problems/referenceable",
    response_model=ApiResponse[PaginatedResponse[TeamProblemSummary]],
)
async def search_team_referenceable_problems(
    team_id: uuid.UUID,
    service: TeamSpaceServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[TeamProblemSummary]]:
    """团队题目引用候选搜索（team_creator / team_admin）：本人创建 + 已发布 +
    全站题 + 未被该团队引用过（同团队同源仅一份快照）；引用页列表用。"""
    rows, total = await service.list_referenceable_problems(
        user, team_id, keyword=keyword, page=page, page_size=page_size
    )
    return ok(PaginatedResponse(items=rows, total=total, page=page, page_size=page_size))


@router.put(
    "/{team_id}/problems/{problem_id}/statement",
    response_model=ApiResponse[TeamProblemSummary],
)
async def update_team_problem_statement(
    team_id: uuid.UUID,
    problem_id: uuid.UUID,
    body: ProblemUpdate,
    service: TeamSpaceServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[TeamProblemSummary]:
    """团队上下文编辑题面（编辑向导第一步）：成员门 + 归属校验后复用题库 update。"""
    item = await service.update_team_problem_statement(user, team_id, problem_id, body)
    await db.commit()
    return ok(item)


@router.get("/{team_id}/problems/{problem_id}", response_model=ApiResponse[ProblemDetail])
async def get_team_problem(
    team_id: uuid.UUID,
    problem_id: uuid.UUID,
    service: TeamSpaceServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemDetail]:
    """团队题库内题目详情（统一入口）：团队可见 + 归属校验后复用题库详情装配。"""
    return ok(await service.get_problem_detail(user, team_id, problem_id))


@router.post(
    "/{team_id}/problems/{problem_id}/submissions",
    response_model=ApiResponse[SubmissionCreatedResponse],
)
async def create_team_problem_submission(
    team_id: uuid.UUID,
    problem_id: uuid.UUID,
    body: ProblemSetSubmissionCreate,
    service: TeamSpaceServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SubmissionCreatedResponse]:
    """团队题库内交题（统一入口）：团队门控通过后走统一判题链路（submit_type='practice'）。"""
    submission = await service.create_problem_submission(
        user, team_id, problem_id, language=body.language, code=body.code
    )
    await db.commit()  # 显式提交：确保 submission 已持久化，dispatch_submission 才能找到它
    await dispatch_submission(submission.id)
    return ok(SubmissionCreatedResponse(submission_id=str(submission.id), status=submission.status))


@router.post(
    "/{team_id}/problems/{problem_id}/run-code",
    response_model=ApiResponse[SelfTestResultOut],
)
async def run_team_problem_code(
    team_id: uuid.UUID,
    problem_id: uuid.UUID,
    body: SelfTestRequest,
    space: TeamSpaceServiceDep,
    service: SelfTestServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SelfTestResultOut]:
    """团队题库内用户自测：团队门控通过后豁免题库可见性，经网关派发一次性运行。"""
    await space.require_member(user, team_id)
    await space.get_problem_detail(user, team_id, problem_id)  # 复用详情门控（可见性 + 归属）
    order = await service.create_order(user, problem_id, body, bypass_visibility=True)
    if not await service.try_claim_cooldown(order, user.id):
        raise APIError(RATE_SEND_TOO_FREQUENT, "操作过于频繁，请稍后再试", 429)
    try:
        outcome = await dispatch_run_code(
            problem=order.problem,
            sandbox_config=order.sandbox_config,
            language=order.language,
            code=order.code,
            stdin_data=order.stdin_data,
            max_concurrent=order.max_concurrent,
        )
    except GatewayUnavailableError as exc:
        await service.release_cooldown(order, user.id)
        raise APIError(SYSTEM_UPSTREAM_FAILURE, "暂无在线判题节点，请稍后重试", 502) from exc
    except GatewayBusyError as exc:
        await service.release_cooldown(order, user.id)
        raise APIError(RATE_LIMITED, "全局判题并发已达上限，请稍后重试", 429) from exc
    except GatewayTimeoutError as exc:
        await service.release_cooldown(order, user.id)
        raise APIError(SYSTEM_UPSTREAM_FAILURE, "沙箱执行超时，请稍后重试", 502) from exc
    return ok(SelfTestResultOut(
        status=outcome.status,
        output=outcome.output.decode("utf-8", errors="replace"),
        error_message=outcome.error_message,
        time_used_ms=outcome.time_used_ms,
        memory_used_kb=outcome.memory_used_kb,
    ))


@router.get(
    "/{team_id}/problem-sets", response_model=ApiResponse[PaginatedResponse[ProblemSetSummary]]
)
async def list_team_problem_sets(
    team_id: uuid.UUID,
    service: TeamSpaceServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[ProblemSetSummary]]:
    """团队题单列表：默认仅未下线；status 显式传入时按值过滤（团队管理视图）。"""
    items, total = await service.list_problem_sets(
        user, team_id, keyword=keyword, status=status, page=page, page_size=page_size
    )
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


@router.post("/{team_id}/problem-sets", response_model=ApiResponse[ProblemSetSummary])
async def create_team_problem_set(
    team_id: uuid.UUID,
    body: TeamProblemSetCreate,
    service: TeamSpaceServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemSetSummary]:
    """创建团队题单（team_creator / team_admin；visibility='team'，仅团队空间可见）。

    copy_items_from 非空 = 复制本人全站题单条目（快照复制，源题单保留在全站）。
    """
    summary = await service.create_problem_set(user, team_id, body)
    await db.commit()
    return ok(summary)


@router.put("/{team_id}/problem-sets/{set_id}/items", response_model=ApiResponse[None])
async def replace_team_problem_set_items(
    team_id: uuid.UUID,
    set_id: uuid.UUID,
    body: ProblemSetItemsUpdate,
    service: TeamSpaceServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """编排团队题单（team_creator / team_admin）：候选 = 已发布且
    （本团队题目 ∪ 全站公开 ∪ 本人私有）；同一题单内不得重复。"""
    await service.replace_set_items(user, team_id, set_id, body.items)
    await db.commit()
    return ok(None)


@router.post("/{team_id}/problem-sets/{set_id}/archive", response_model=ApiResponse[ProblemSetSummary])
async def archive_team_problem_set(
    team_id: uuid.UUID,
    set_id: uuid.UUID,
    service: TeamSpaceServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemSetSummary]:
    """下线团队题单（team_creator / team_admin；不做物理删除）。"""
    summary = await service.archive_problem_set(user, team_id, set_id)
    await db.commit()
    return ok(summary)


# ---- 团队题单上下文（限界上下文：详情 / 题目 / 交题 / 自测走团队端点，不走题单统一入口） ----


@router.get(
    "/{team_id}/problem-sets/{set_id}", response_model=ApiResponse[ProblemSetDetail]
)
async def get_team_problem_set(
    team_id: uuid.UUID,
    set_id: uuid.UUID,
    service: TeamSpaceServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemSetDetail]:
    """团队题单详情（团队上下文统一入口）：成员门 + 归属校验后复用题单详情装配。"""
    return ok(await service.get_set_detail(user, team_id, set_id))


@router.get(
    "/{team_id}/problem-sets/{set_id}/problems/{problem_id}",
    response_model=ApiResponse[ProblemDetail],
)
async def get_team_set_problem(
    team_id: uuid.UUID,
    set_id: uuid.UUID,
    problem_id: uuid.UUID,
    service: TeamSpaceServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemDetail]:
    """团队题单内题目详情（团队上下文统一入口）：归属校验后复用题库详情装配。"""
    return ok(await service.get_set_problem_detail(user, team_id, set_id, problem_id))


@router.post(
    "/{team_id}/problem-sets/{set_id}/problems/{problem_id}/submissions",
    response_model=ApiResponse[SubmissionCreatedResponse],
)
async def create_team_set_submission(
    team_id: uuid.UUID,
    set_id: uuid.UUID,
    problem_id: uuid.UUID,
    body: ProblemSetSubmissionCreate,
    service: TeamSpaceServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SubmissionCreatedResponse]:
    """团队题单内交题（团队上下文统一入口）：门控通过后走统一判题链路。"""
    submission = await service.create_set_submission(
        user, team_id, set_id, problem_id, language=body.language, code=body.code
    )
    await db.commit()  # 显式提交：确保 submission 已持久化，dispatch_submission 才能找到它
    await dispatch_submission(submission.id)
    return ok(SubmissionCreatedResponse(submission_id=str(submission.id), status=submission.status))


@router.post(
    "/{team_id}/problem-sets/{set_id}/problems/{problem_id}/run-code",
    response_model=ApiResponse[SelfTestResultOut],
)
async def run_team_set_problem_code(
    team_id: uuid.UUID,
    set_id: uuid.UUID,
    problem_id: uuid.UUID,
    body: SelfTestRequest,
    space: TeamSpaceServiceDep,
    service: SelfTestServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SelfTestResultOut]:
    """团队题单内用户自测：门控复用题目详情端点，豁免题库可见性后经网关派发。"""
    await space.require_member(user, team_id)
    await space.get_set_problem_detail(user, team_id, set_id, problem_id)  # 复用详情门控
    order = await service.create_order(user, problem_id, body, bypass_visibility=True)
    if not await service.try_claim_cooldown(order, user.id):
        raise APIError(RATE_SEND_TOO_FREQUENT, "操作过于频繁，请稍后再试", 429)
    try:
        outcome = await dispatch_run_code(
            problem=order.problem,
            sandbox_config=order.sandbox_config,
            language=order.language,
            code=order.code,
            stdin_data=order.stdin_data,
            max_concurrent=order.max_concurrent,
        )
    except GatewayUnavailableError as exc:
        await service.release_cooldown(order, user.id)
        raise APIError(SYSTEM_UPSTREAM_FAILURE, "暂无在线判题节点，请稍后重试", 502) from exc
    except GatewayBusyError as exc:
        await service.release_cooldown(order, user.id)
        raise APIError(RATE_LIMITED, "全局判题并发已达上限，请稍后重试", 429) from exc
    except GatewayTimeoutError as exc:
        await service.release_cooldown(order, user.id)
        raise APIError(SYSTEM_UPSTREAM_FAILURE, "沙箱执行超时，请稍后重试", 502) from exc
    return ok(SelfTestResultOut(
        status=outcome.status,
        output=outcome.output.decode("utf-8", errors="replace"),
        error_message=outcome.error_message,
        time_used_ms=outcome.time_used_ms,
        memory_used_kb=outcome.memory_used_kb,
    ))


@router.get(
    "/{team_id}/contests", response_model=ApiResponse[PaginatedResponse[ContestSummary]]
)
async def list_team_contests(
    team_id: uuid.UUID,
    service: TeamSpaceServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[ContestSummary]]:
    """团队比赛列表：本团队全部状态比赛（成员可见）。"""
    items, total = await service.list_contests(
        user, team_id, keyword=keyword, status=status, page=page, page_size=page_size
    )
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


@router.post("/{team_id}/contests", response_model=ApiResponse[ContestSummary])
async def create_team_contest(
    team_id: uuid.UUID,
    body: TeamContestCreate,
    service: TeamSpaceServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ContestSummary]:
    """创建团队比赛（team_creator / team_admin；contest_type='team'）；
    编排候选在公开比赛规则之上放开本团队题目。"""
    summary = await service.create_contest(user, team_id, body)
    await db.commit()
    return ok(summary)

"""判题路由（docs/contracts/judge.md 端点，统一前缀 /api/v1）。

POST /problems/{id}/verify（验题提交）在本模块注册：该端点创建判题提交并派发，
属于判题链路；保持 judge → problems 单向依赖。
POST /problems/{id}/run-code（用户自测）：经网关派发到节点一次性运行，不落库不计分。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import ProblemServiceDep, SelfTestServiceDep, SessionDep, SubmissionServiceDep
from app.core.dependency import get_current_admin, get_current_user
from app.core.exceptions import (
    APIError,
    PARAM_FORMAT_INVALID,
    RATE_LIMITED,
    RATE_SEND_TOO_FREQUENT,
    SYSTEM_UPSTREAM_FAILURE,
)
from app.enums import SubmissionStatus, SubmitType
from app.models.user import User
from app.rpc.judge_gateway import (
    REGISTRY,
    GatewayBusyError,
    GatewayTimeoutError,
    GatewayUnavailableError,
    dispatch_run_code,
    dispatch_submission,
)
from app.schemas.judge import (
    ProblemSubmissionItem,
    SandboxHealthOut,
    SelfTestRequest,
    SelfTestResultOut,
    SubmissionCreate,
    SubmissionCreatedResponse,
    SubmissionDetailOut,
    SubmissionQuery,
    SubmissionSummary,
    VerifyRequest,
)
from app.schemas.problem import VerificationInitOut, VerificationInviteLink
from app.utils.pagination import PaginatedResponse
from app.utils.response import ApiResponse, ok

router = APIRouter(tags=["judge"])


# ---- 验题提交 ----


@router.post(
    "/problems/{problem_id}/verify",
    response_model=ApiResponse[SubmissionCreatedResponse | VerificationInitOut],
    response_model_exclude_none=True,  # 发起模式无邀请链接时不返回 invite: null
)
async def verify_problem(
    problem_id: uuid.UUID, body: VerifyRequest,
    service: SubmissionServiceDep,
    problem_service: ProblemServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SubmissionCreatedResponse | VerificationInitOut]:
    if body.code is not None:
        submission = await service.create_verify_submission(user, problem_id, body)
        await db.commit()  # 显式提交：确保 submission 已持久化，dispatch_submission 才能找到它
        await dispatch_submission(submission.id)
        return ok(SubmissionCreatedResponse(submission_id=str(submission.id), status=submission.status))
    result = await problem_service.init_verification(user, problem_id, body.invite_expires_hours)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(result)


@router.get(
    "/problems/{problem_id}/verify/invite",
    response_model=ApiResponse[VerificationInviteLink | None],
)
async def get_verification_invite(
    problem_id: uuid.UUID,
    service: ProblemServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[VerificationInviteLink | None]:
    """查询题目当前有效的验题邀请链接；无或已失效返回 null。"""
    return ok(await service.get_verification_invite(user, problem_id))


# ---- 提交 ----


@router.post("/submissions", response_model=ApiResponse[SubmissionCreatedResponse])
async def create_submission(
    body: SubmissionCreate,
    service: SubmissionServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SubmissionCreatedResponse]:
    submission = await service.create(user, body)
    await db.commit()  # 显式提交：确保 submission 已持久化，dispatch_submission 才能找到它
    await dispatch_submission(submission.id)
    return ok(SubmissionCreatedResponse(submission_id=str(submission.id), status=submission.status))


@router.get("/submissions", response_model=ApiResponse[PaginatedResponse[SubmissionSummary]])
async def list_submissions(
    service: SubmissionServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    problem_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[SubmissionSummary]]:
    try:
        query = SubmissionQuery(page=page, page_size=page_size, problem_id=problem_id, status=status)
    except Exception as exc:
        raise APIError(PARAM_FORMAT_INVALID, "查询参数不合法", 400) from exc
    items, total = await service.list_summaries(user, query)
    return ok(PaginatedResponse(items=items, total=total, page=query.page, page_size=query.page_size))


@router.get("/submissions/{submission_id}", response_model=ApiResponse[SubmissionDetailOut])
async def get_submission(
    submission_id: uuid.UUID,
    service: SubmissionServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SubmissionDetailOut]:
    return ok(await service.get_detail(user, submission_id))


@router.get(
    "/problems/{problem_id}/submissions",
    response_model=ApiResponse[PaginatedResponse[ProblemSubmissionItem]],
)
async def list_problem_submissions(
    problem_id: uuid.UUID,
    service: SubmissionServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=64),
    language: str | None = Query(default=None, max_length=32),
    submit_type: str | None = Query(default=None, max_length=32),
    user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[ProblemSubmissionItem]]:
    """题目全员提交（题目管理视角：创建者与管理角色可见，docs/contracts/judge.md）。

    keyword 模糊匹配提交人昵称；language / status / submit_type 精确过滤。
    """
    try:
        status_value = SubmissionStatus(status) if status else None
        submit_type_value = SubmitType(submit_type) if submit_type else None
    except ValueError as exc:
        raise APIError(PARAM_FORMAT_INVALID, "查询参数不合法", 400) from exc
    items, total = await service.list_problem_summaries(
        user, problem_id, status_value, keyword, language, submit_type_value, page, page_size
    )
    return ok(PaginatedResponse(items=items, total=total, page=page, page_size=page_size))


@router.get(
    "/problems/{problem_id}/submissions/{submission_id}",
    response_model=ApiResponse[SubmissionDetailOut],
)
async def get_problem_submission(
    problem_id: uuid.UUID,
    submission_id: uuid.UUID,
    service: SubmissionServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SubmissionDetailOut]:
    """题目管理视角的提交详情（统一入口）：管理权限 + 归属校验后复用判题详情装配。"""
    return ok(await service.get_problem_submission_detail(user, problem_id, submission_id))


# ---- 用户自测 ----


@router.post("/problems/{problem_id}/run-code", response_model=ApiResponse[SelfTestResultOut])
async def run_problem_code(
    problem_id: uuid.UUID,
    body: SelfTestRequest,
    service: SelfTestServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[SelfTestResultOut]:
    """用户自测：代码 + 自定义输入经判题节点一次性运行，仅回传 stdout（docs/contracts/judge.md）。"""
    order = await service.create_order(user, problem_id, body)
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


# ---- 沙箱 ----


@router.get("/sandbox/health", response_model=ApiResponse[SandboxHealthOut])
async def sandbox_health(admin: User = Depends(get_current_admin)) -> ApiResponse[SandboxHealthOut]:
    """沙箱节点健康（admin；docs/contracts/judge.md）：在线节点来自网关注册表。"""
    nodes = [conn.to_payload() for conn in REGISTRY.list_nodes()]
    return ok(SandboxHealthOut(nodes=nodes))

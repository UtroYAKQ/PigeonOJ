"""题库路由（docs/contracts/problems.md /problems* 端点，统一前缀 /api/v1）。

验题提交端点 POST /problems/{id}/verify 在 judge 模块路由中注册
（创建判题提交并派发）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import ProblemServiceDep, SessionDep, TagServiceDep
from app.models.user import User
from app.schemas.problem import (
    ProblemCreate,
    ProblemDetail,
    ProblemQuery,
    ProblemSummary,
    ProblemUpdate,
    SamplesUpdate,
    TagPublic,
    TestCaseListOut,
    TestCasesOut,
    TestCasesPatch,
    TestCasesUpdate,
    VerificationInviteOut,
)
from app.core.dependency import get_current_user, get_optional_user
from app.core.exceptions import AUTH_NOT_LOGGED_IN, PARAM_FORMAT_INVALID, APIError
from app.utils.pagination import PaginatedResponse
from app.utils.response import ApiResponse, ok

router = APIRouter(tags=["problems"])


@router.get("/problems", response_model=ApiResponse[PaginatedResponse[ProblemSummary]])
async def list_problems(
    service: ProblemServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    tag: str | None = Query(default=None, max_length=64),
    scope: str = Query(default="all"),
    status: str | None = Query(default=None),
    difficulty_min: int | None = Query(default=None, ge=0),
    difficulty_max: int | None = Query(default=None, ge=0),
    user: User | None = Depends(get_optional_user),
) -> ApiResponse[PaginatedResponse[ProblemSummary]]:
    try:
        query = ProblemQuery(
            page=page, page_size=page_size, keyword=keyword, tag=tag, scope=scope, status=status,
            difficulty_min=difficulty_min, difficulty_max=difficulty_max,
        )
    except Exception as exc:  # pydantic 校验失败转 1001 信封
        raise APIError(PARAM_FORMAT_INVALID, "查询参数不合法", 400) from exc
    if query.scope == "mine" and user is None:
        raise APIError(AUTH_NOT_LOGGED_IN, "查看我的题目需要登录", 401)
    rows, total = await service.list_published(query, viewer=user)
    flags = (
        await service.verification_flags([row.id for row in rows]) if query.scope == "mine" else {}
    )
    items: list[ProblemSummary] = []
    for row in rows:
        item = ProblemSummary.model_validate(row)
        item.needs_reverification = flags.get(row.id, False)
        items.append(item)
    await service.attach_counters(items)
    await service.attach_solve_status(items, user)
    return ok(PaginatedResponse(items=items, total=total, page=query.page, page_size=query.page_size))


@router.post("/problems", response_model=ApiResponse[ProblemSummary])
async def create_problem(
    body: ProblemCreate,
    service: ProblemServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemSummary]:
    problem = await service.create(user, body)
    await db.commit()  # 显式提交：确保数据持久化后再返回（get_db 会再次 commit，但无害）
    summary = ProblemSummary.model_validate(problem)
    await service.attach_counters([summary])
    return ok(summary)


@router.get("/problems/tags", response_model=ApiResponse[list[TagPublic]])
async def list_active_tags(service: TagServiceDep) -> ApiResponse[list[TagPublic]]:
    """激活标签列表（public：打标选择器与题库筛选；docs/contracts/problems.md 端点表）。

    注意必须先于 /problems/{problem_id} 注册，否则 tags 会被当作 uuid 解析。
    """
    rows = await service.list_active()
    return ok([TagPublic.model_validate(row) for row in rows])


@router.get("/problems/{problem_id}", response_model=ApiResponse[ProblemDetail])
async def get_problem(
    problem_id: uuid.UUID,
    service: ProblemServiceDep,
    user: User | None = Depends(get_optional_user),
) -> ApiResponse[ProblemDetail]:
    return ok(await service.get_detail_view(problem_id, user))


@router.put("/problems/{problem_id}", response_model=ApiResponse[ProblemSummary])
async def update_problem(
    problem_id: uuid.UUID, body: ProblemUpdate,
    service: ProblemServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemSummary]:
    problem = await service.update(user, problem_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    summary = ProblemSummary.model_validate(problem)
    await service.attach_counters([summary])
    return ok(summary)


@router.get("/problems/{problem_id}/test-cases", response_model=ApiResponse[TestCaseListOut])
async def get_test_cases(
    problem_id: uuid.UUID,
    service: ProblemServiceDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[TestCaseListOut]:
    """测试点列表（独立管理端点）：仅题目管理者（admin 或创建者）可读，普通用户 2003。

    详情响应一律不携带测试点；编辑器经本端点回读目标状态（暂存优先）。
    """
    return ok(await service.get_cases_managed(user, problem_id))


@router.put("/problems/{problem_id}/test-cases", response_model=ApiResponse[None])
async def update_test_cases(
    problem_id: uuid.UUID, body: TestCasesUpdate,
    service: ProblemServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """全量替换暂存集（生效集不动，验题通过后晋升；行不可变不物理删除）。"""
    await service.replace_cases(user, problem_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(None)


@router.patch("/problems/{problem_id}/test-cases", response_model=ApiResponse[TestCasesOut])
async def patch_test_cases(
    problem_id: uuid.UUID, body: TestCasesPatch,
    service: ProblemServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[TestCasesOut]:
    """增量更新暂存集：只提交变化的测试点（带 id=修改 / 无 id=新增 / delete_ids=目标状态移除）。"""
    await service.patch_cases(user, problem_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    problem = await service.problems.get_by_id(problem_id)
    cases = await service.list_cases_view(problem) if problem else []
    return ok(TestCasesOut(cases=cases))


@router.post("/problems/{problem_id}/test-cases/apply", response_model=ApiResponse[ProblemSummary])
async def apply_test_cases(
    problem_id: uuid.UUID,
    service: ProblemServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemSummary]:
    """显式生效：把已通过验题的暂存集晋升为生效集（验题与晋升解耦）。"""
    problem = await service.apply_pending_cases(user, problem_id)
    await db.commit()
    summary = ProblemSummary.model_validate(problem)
    await service.attach_counters([summary])
    return ok(summary)


@router.put("/problems/{problem_id}/samples", response_model=ApiResponse[None])
async def update_samples(
    problem_id: uuid.UUID, body: SamplesUpdate,
    service: ProblemServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    await service.replace_samples(user, problem_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(None)


@router.post("/problems/{problem_id}/publish", response_model=ApiResponse[ProblemSummary])
async def publish_problem(
    problem_id: uuid.UUID,
    service: ProblemServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemSummary]:
    problem = await service.publish(user, problem_id)
    await db.commit()  # 显式提交：确保数据持久化
    summary = ProblemSummary.model_validate(problem)
    await service.attach_counters([summary])
    return ok(summary)


@router.post("/problems/{problem_id}/archive", response_model=ApiResponse[ProblemSummary])
async def archive_problem(
    problem_id: uuid.UUID,
    service: ProblemServiceDep,
    db: SessionDep,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProblemSummary]:
    problem = await service.archive(user, problem_id)
    await db.commit()  # 显式提交：确保数据持久化
    summary = ProblemSummary.model_validate(problem)
    await service.attach_counters([summary])
    return ok(summary)


@router.get("/verify-invites/{token}", response_model=ApiResponse[VerificationInviteOut])
async def resolve_verify_invite(token: str, service: ProblemServiceDep) -> ApiResponse[VerificationInviteOut]:
    return ok(await service.resolve_invite(token))

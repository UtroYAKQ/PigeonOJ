"""题库路由（docs/contracts/problems.md /problems* 端点，统一前缀 /api/v1）。

验题提交端点 POST /problems/{id}/verify 在 judge 模块路由中注册
（创建判题提交并派发）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.problem import (
    ProblemCreate,
    ProblemDetail,
    ProblemQuery,
    ProblemSummary,
    ProblemUpdate,
    SamplesUpdate,
    TagPublic,
    TestCasesOut,
    TestCasesPatch,
    TestCasesUpdate,
    VerificationInviteOut,
)
from app.services.problem import ProblemDetailData, ProblemService
from app.services.tag import TagService
from app.models.user import User
from app.core.dependency import get_current_user, get_optional_user
from app.core.exceptions import AUTH_NOT_LOGGED_IN, PARAM_FORMAT_INVALID, APIError
from app.utils.pagination import PaginatedResponse
from app.utils.response import ApiResponse, ok
from app.core.database import get_db

router = APIRouter(tags=["problems"])


def _to_detail(detail: ProblemDetailData) -> ProblemDetail:
    """将题目详情装配结果转换为响应契约（测试点 / 题解仅管理角色可见）。"""
    problem = detail.problem
    return ProblemDetail(
        id=problem.id,
        title=problem.title,
        background=problem.background,
        description=problem.description,
        input_description=problem.input_description,
        output_description=problem.output_description,
        solution=problem.solution if detail.can_manage else None,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
        status=problem.status,
        visibility=problem.visibility,
        is_verified=problem.is_verified,
        verified_by=problem.verified_by,
        verified_at=problem.verified_at,
        owner_id=problem.owner_id,
        published_at=problem.published_at,
        created_at=problem.created_at,
        updated_at=problem.updated_at,
        difficulty=problem.difficulty,
        submission_count=detail.submission_count,
        accepted_count=detail.accepted_count,
        samples=detail.samples,
        tags=detail.tags,
        can_manage=detail.can_manage,
        needs_reverification=bool(detail.needs_reverification),
        case_status=problem.case_status,
        test_cases=detail.test_cases if detail.can_manage and detail.test_cases else None,
        cases_updated_at=detail.cases_updated_at,
        samples_updated_at=problem.samples_updated_at,
    )


@router.get("/problems", response_model=ApiResponse[PaginatedResponse[ProblemSummary]])
async def list_problems(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    tag: str | None = Query(default=None, max_length=64),
    scope: str = Query(default="all"),
    status: str | None = Query(default=None),
    difficulty_min: int | None = Query(default=None, ge=0),
    difficulty_max: int | None = Query(default=None, ge=0),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
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
    service = ProblemService(db)
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
    return ok(PaginatedResponse(items=items, total=total, page=query.page, page_size=query.page_size))


@router.post("/problems", response_model=ApiResponse[ProblemSummary])
async def create_problem(
    body: ProblemCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProblemSummary]:
    service = ProblemService(db)
    problem = await service.create(user, body)
    await db.commit()  # 显式提交：确保数据持久化后再返回（get_db 会再次 commit，但无害）
    summary = ProblemSummary.model_validate(problem)
    await service.attach_counters([summary])
    return ok(summary)


@router.get("/problems/tags", response_model=ApiResponse[list[TagPublic]])
async def list_active_tags(db: AsyncSession = Depends(get_db)) -> ApiResponse[list[TagPublic]]:
    """激活标签列表（public：打标选择器与题库筛选；docs/contracts/problems.md 端点表）。

    注意必须先于 /problems/{problem_id} 注册，否则 tags 会被当作 uuid 解析。
    """
    rows = await TagService(db).list_active()
    return ok([TagPublic.model_validate(row) for row in rows])


@router.get("/problems/{problem_id}", response_model=ApiResponse[ProblemDetail])
async def get_problem(
    problem_id: uuid.UUID,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProblemDetail]:
    detail = await ProblemService(db).get_detail(problem_id, user)
    return ok(_to_detail(detail))


@router.put("/problems/{problem_id}", response_model=ApiResponse[ProblemSummary])
async def update_problem(
    problem_id: uuid.UUID, body: ProblemUpdate,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProblemSummary]:
    service = ProblemService(db)
    problem = await service.update(user, problem_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    summary = ProblemSummary.model_validate(problem)
    await service.attach_counters([summary])
    return ok(summary)


@router.put("/problems/{problem_id}/test-cases", response_model=ApiResponse[None])
async def update_test_cases(
    problem_id: uuid.UUID, body: TestCasesUpdate,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    """全量替换暂存集（生效集不动，验题通过后晋升；行不可变不物理删除）。"""
    await ProblemService(db).replace_cases(user, problem_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(None)


@router.patch("/problems/{problem_id}/test-cases", response_model=ApiResponse[TestCasesOut])
async def patch_test_cases(
    problem_id: uuid.UUID, body: TestCasesPatch,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> ApiResponse[TestCasesOut]:
    """增量更新暂存集：只提交变化的测试点（带 id=修改 / 无 id=新增 / delete_ids=目标状态移除）。"""
    service = ProblemService(db)
    await service.patch_cases(user, problem_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    problem = await service.problems.get_by_id(problem_id)
    cases = await service.list_cases_view(problem) if problem else []
    return ok(TestCasesOut(cases=cases))


@router.post("/problems/{problem_id}/test-cases/apply", response_model=ApiResponse[ProblemSummary])
async def apply_test_cases(
    problem_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProblemSummary]:
    """显式生效：把已通过验题的暂存集晋升为生效集（验题与晋升解耦）。"""
    service = ProblemService(db)
    problem = await service.apply_pending_cases(user, problem_id)
    await db.commit()
    summary = ProblemSummary.model_validate(problem)
    await service.attach_counters([summary])
    return ok(summary)


@router.put("/problems/{problem_id}/samples", response_model=ApiResponse[None])
async def update_samples(
    problem_id: uuid.UUID, body: SamplesUpdate,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    await ProblemService(db).replace_samples(user, problem_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(None)


@router.post("/problems/{problem_id}/publish", response_model=ApiResponse[ProblemSummary])
async def publish_problem(
    problem_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProblemSummary]:
    service = ProblemService(db)
    problem = await service.publish(user, problem_id)
    await db.commit()  # 显式提交：确保数据持久化
    summary = ProblemSummary.model_validate(problem)
    await service.attach_counters([summary])
    return ok(summary)


@router.post("/problems/{problem_id}/archive", response_model=ApiResponse[ProblemSummary])
async def archive_problem(
    problem_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProblemSummary]:
    service = ProblemService(db)
    problem = await service.archive(user, problem_id)
    await db.commit()  # 显式提交：确保数据持久化
    summary = ProblemSummary.model_validate(problem)
    await service.attach_counters([summary])
    return ok(summary)


@router.get("/verify-invites/{token}", response_model=ApiResponse[VerificationInviteOut])
async def resolve_verify_invite(token: str, db: AsyncSession = Depends(get_db)) -> ApiResponse[VerificationInviteOut]:
    return ok(await ProblemService(db).resolve_invite(token))

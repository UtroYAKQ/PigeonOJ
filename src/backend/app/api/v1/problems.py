"""题库路由（docs/contracts/problems.md /problems* 端点，统一前缀 /api/v1）。

验题提交端点 POST /problems/{id}/verify 在 judge 模块路由中注册
（创建判题提交并派发；见 docs/decisions/2026-08-24-backend-module-packaging.md）。
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
    TestCasesPatch,
    TestCasesUpdate,
)
from app.services.problem import ProblemDetailData, ProblemService, schedule_object_cleanup
from app.services.tag import TagService
from app.models.user import User
from app.core.dependency import get_current_user, get_optional_user
from app.core.exceptions import AUTH_NOT_LOGGED_IN, PARAM_FORMAT_INVALID, APIError
from app.utils.pagination import PaginatedResponse
from app.utils.response import ok
from app.core.database import get_db

router = APIRouter(tags=["problems"])


def _summary(problem) -> dict:
    """将 Problem ORM 对象转换为摘要字典。"""
    return ProblemSummary.model_validate(problem).model_dump(mode="json")


def _detail(detail: ProblemDetailData) -> dict:
    """将题目详情装配结果转换为响应格式。"""
    problem = detail.problem
    test_cases = None
    if detail.can_manage and detail.test_cases:
        test_cases = [tc.model_dump(mode="json") for tc in detail.test_cases]
    return ProblemDetail(
        id=problem.id,
        title=problem.title,
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
        samples=[s.model_dump(mode="json") for s in detail.samples],
        tags=detail.tags,
        can_manage=detail.can_manage,
        needs_reverification=bool(detail.needs_reverification),
        test_cases=test_cases,
        cases_updated_at=detail.cases_updated_at,
        samples_updated_at=problem.samples_updated_at,
    ).model_dump(mode="json")


@router.get("/problems")
async def list_problems(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=128),
    tag: str | None = Query(default=None, max_length=64),
    scope: str = Query(default="all"),
    status: str | None = Query(default=None),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        query = ProblemQuery(page=page, page_size=page_size, keyword=keyword, tag=tag, scope=scope, status=status)
    except Exception as exc:  # pydantic 校验失败转 1001 信封
        raise APIError(PARAM_FORMAT_INVALID, "查询参数不合法", 400) from exc
    if query.scope == "mine" and user is None:
        raise APIError(AUTH_NOT_LOGGED_IN, "查看我的题目需要登录", 401)
    service = ProblemService(db)
    rows, total = await service.list_published(query, viewer=user)
    flags = (
        await service.verification_flags([row.id for row in rows]) if query.scope == "mine" else {}
    )
    items = []
    for row in rows:
        item = _summary(row)
        if row.id in flags:
            item["needs_reverification"] = flags[row.id]
        items.append(item)
    return ok(PaginatedResponse(items=items, total=total, page=query.page, page_size=query.page_size))


@router.post("/problems")
async def create_problem(body: ProblemCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    problem = await ProblemService(db).create(user, body)
    await db.commit()  # 显式提交：确保数据持久化后再返回（get_db 会再次 commit，但无害）
    return ok(_summary(problem))


@router.get("/problems/tags")
async def list_active_tags(db: AsyncSession = Depends(get_db)):
    """激活标签列表（public：打标选择器与题库筛选；docs/contracts/problems.md 端点表）。

    注意必须先于 /problems/{problem_id} 注册，否则 tags 会被当作 uuid 解析。
    """
    rows = await TagService(db).list_active()
    return ok([
        {"id": str(row.id), "name": row.name, "color": row.color}
        for row in rows
    ])


@router.get("/problems/{problem_id}")
async def get_problem(
    problem_id: uuid.UUID,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(_detail(await ProblemService(db).get_detail(problem_id, user)))


@router.put("/problems/{problem_id}")
async def update_problem(problem_id: uuid.UUID, body: ProblemUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    problem = await ProblemService(db).update(user, problem_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(_summary(problem))


@router.put("/problems/{problem_id}/test-cases")
async def update_test_cases(problem_id: uuid.UUID, body: TestCasesUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stale_keys = await ProblemService(db).replace_cases(user, problem_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    schedule_object_cleanup(stale_keys)  # 事务提交后异步清理旧对象（docs/contracts/problems.md）
    return ok(None)


@router.patch("/problems/{problem_id}/test-cases")
async def patch_test_cases(problem_id: uuid.UUID, body: TestCasesPatch, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """增量更新：只提交变化的测试点（带 id=修改 / 无 id=新增 / delete_ids=删除）。"""
    service = ProblemService(db)
    stale_keys = await service.patch_cases(user, problem_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    schedule_object_cleanup(stale_keys)
    cases = await service.list_cases_with_contents(problem_id)
    return ok({"cases": [tc.model_dump(mode="json") for tc in cases]})


@router.put("/problems/{problem_id}/samples")
async def update_samples(problem_id: uuid.UUID, body: SamplesUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await ProblemService(db).replace_samples(user, problem_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(None)


@router.post("/problems/{problem_id}/publish")
async def publish_problem(problem_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    problem = await ProblemService(db).publish(user, problem_id)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(_summary(problem))


@router.post("/problems/{problem_id}/archive")
async def archive_problem(problem_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    problem = await ProblemService(db).archive(user, problem_id)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(_summary(problem))


@router.get("/verify-invites/{token}")
async def resolve_verify_invite(token: str, db: AsyncSession = Depends(get_db)):
    return ok(await ProblemService(db).resolve_invite(token))

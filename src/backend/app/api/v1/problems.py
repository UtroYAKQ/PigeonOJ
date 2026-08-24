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
    ProblemQuery,
    ProblemSummary,
    ProblemUpdate,
    SamplesUpdate,
    TestCasesUpdate,
)
from app.controllers.problem import ProblemService, schedule_object_cleanup
from app.controllers.tag import TagService
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


def _detail(detail: dict) -> dict:
    """将题目详情字典转换为响应格式。"""
    problem = detail["problem"]
    payload = ProblemSummary.model_validate(problem).model_dump(mode="json")
    payload.update(
        {
            "description": problem.description,
            "input_description": problem.input_description,
            "output_description": problem.output_description,
            "owner_id": str(problem.owner_id),
            "samples": detail["samples"],
            "tags": detail["tags"],
            "can_manage": detail["can_manage"],
            # 发布门禁：未验题 / 测试点样例晚于验题通过时间变更 → 须重新验题
            "needs_reverification": bool(detail["needs_reverification"]),
        }
    )
    if problem.verified_at:
        payload["verified_at"] = problem.verified_at.isoformat()
    if problem.published_at:
        payload["published_at"] = problem.published_at.isoformat()
    # 官方题解与测试点内容仅题目管理角色可见（docs/contracts/problems.md 数据所有权）
    if detail["can_manage"]:
        payload["solution"] = problem.solution
        payload["test_cases"] = detail["test_cases"]
        if detail["cases_updated_at"]:
            payload["cases_updated_at"] = detail["cases_updated_at"].isoformat()
        if problem.samples_updated_at:
            payload["samples_updated_at"] = problem.samples_updated_at.isoformat()
    return payload


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
    rows, total = await ProblemService(db).list_published(query, viewer=user)
    service = ProblemService(db)
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

"""题库 / 判题路由（docs/contracts/problems.md / judge.md 端点表）。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.judge.gateway import REGISTRY, dispatch_submission
from app.modules.judge.schemas import (
    ProblemCreate,
    ProblemDetail,
    ProblemQuery,
    ProblemSummary,
    ProblemUpdate,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionQuery,
    SubmissionSummary,
    TestCaseResult,
    TestCasesUpdate,
    VerifyRequest,
)
from app.modules.judge.service import ProblemService, SubmissionService
from app.modules.users.models import User
from app.shared.infra.database import get_db
from app.modules.users.deps import get_current_admin, get_current_user, get_optional_user
from app.shared.common.errors import AUTH_NOT_LOGGED_IN, PARAM_FORMAT_INVALID, APIError
from app.shared.common.pagination import PaginatedResponse, PaginationParams
from app.shared.common.response import ok

router = APIRouter(tags=["judge"])


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
    return payload


# ---- 题目 ----


@router.get("/problems")
async def list_problems(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    difficulty: str | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=128),
    tag: str | None = Query(default=None, max_length=64),
    scope: str = Query(default="all"),
    status: str | None = Query(default=None),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        query = ProblemQuery(page=page, page_size=page_size, difficulty=difficulty, keyword=keyword, tag=tag, scope=scope, status=status)
    except Exception as exc:  # pydantic 校验失败转 1001 信封
        raise APIError(PARAM_FORMAT_INVALID, "查询参数不合法", 400) from exc
    if query.scope == "mine" and user is None:
        raise APIError(AUTH_NOT_LOGGED_IN, "查看我的题目需要登录", 401)
    rows, total = await ProblemService(db).list_published(query, viewer=user)
    items = [_summary(row) for row in rows]
    return ok(PaginatedResponse(items=items, total=total, page=query.page, page_size=query.page_size))


@router.post("/problems")
async def create_problem(body: ProblemCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    problem = await ProblemService(db).create(user, body)
    await db.commit()  # 显式提交：确保数据持久化后再返回（get_db 会再次 commit，但无害）
    return ok(_summary(problem))


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
    await ProblemService(db).replace_cases(user, problem_id, body)
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


@router.post("/problems/{problem_id}/promote")
async def promote_problem(problem_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    problem = await ProblemService(db).promote(user, problem_id)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(_summary(problem))


# ---- 验题 ----


@router.post("/problems/{problem_id}/verify")
async def verify_problem(problem_id: uuid.UUID, body: VerifyRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = ProblemService(db)
    if body.code is not None:
        submission = await service.submit_verification(user, problem_id, body)
        await db.commit()  # 显式提交：确保 submission 已持久化，dispatch_submission 才能找到它
        await dispatch_submission(submission.id)
        return ok({"submission_id": str(submission.id), "status": submission.status})
    result = await service.init_verification(user, problem_id, body)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(result)


@router.get("/verify-invites/{token}")
async def resolve_verify_invite(token: str, db: AsyncSession = Depends(get_db)):
    return ok(await ProblemService(db).resolve_invite(token))


# ---- 提交 ----


@router.post("/submissions")
async def create_submission(body: SubmissionCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    submission = await SubmissionService(db).create(user, body)
    await db.commit()  # 显式提交：确保 submission 已持久化，dispatch_submission 才能找到它
    await dispatch_submission(submission.id)
    return ok({"submission_id": str(submission.id), "status": submission.status})


@router.get("/submissions")
async def list_submissions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    problem_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        query = SubmissionQuery(page=page, page_size=page_size, problem_id=problem_id, status=status)
    except Exception as exc:
        raise APIError(PARAM_FORMAT_INVALID, "查询参数不合法", 400) from exc
    rows, total = await SubmissionService(db).list_for_user(user, query)
    items = [SubmissionSummary.model_validate(row).model_dump(mode="json") for row in rows]
    return ok(PaginatedResponse(items=items, total=total, page=query.page, page_size=query.page_size))


@router.get("/submissions/{submission_id}")
async def get_submission(submission_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    detail = await SubmissionService(db).get_detail(user, submission_id)
    submission = detail["submission"]
    submission_dict = SubmissionDetail.model_validate(submission).model_dump(mode="json")
    submission_dict["cases"] = detail["cases"]
    return ok(submission_dict)


# ---- 沙箱 ----


@router.get("/sandbox/health")
async def sandbox_health(admin: User = Depends(get_current_admin)):
    """沙箱节点健康（admin；docs/contracts/judge.md）：在线节点来自网关注册表。"""
    nodes = [conn.to_payload() for conn in REGISTRY.list_nodes()]
    return ok({"nodes": nodes})

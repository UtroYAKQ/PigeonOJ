"""判题路由（docs/contracts/judge.md 端点，统一前缀 /api/v1）。

POST /problems/{id}/verify（验题提交）在本模块注册：该端点创建判题提交并派发，
属于判题链路；保持 judge → problems 单向依赖（docs/decisions/2026-08-24-backend-module-packaging.md）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.judge.gateway import REGISTRY, dispatch_submission
from app.modules.judge.schemas import (
    SubmissionCreate,
    SubmissionDetail,
    SubmissionQuery,
    SubmissionSummary,
    VerifyRequest,
)
from app.modules.judge.service import SubmissionService
from app.modules.problems.api import ProblemService
from app.modules.users.api import User, get_current_admin, get_current_user
from app.shared.common.errors import PARAM_FORMAT_INVALID, APIError
from app.shared.common.pagination import PaginatedResponse
from app.shared.common.response import ok
from app.shared.infra.database import get_db

router = APIRouter(tags=["judge"])


# ---- 验题提交 ----


@router.post("/problems/{problem_id}/verify")
async def verify_problem(problem_id: uuid.UUID, body: VerifyRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = SubmissionService(db)
    if body.code is not None:
        submission = await service.create_verify_submission(user, problem_id, body)
        await db.commit()  # 显式提交：确保 submission 已持久化，dispatch_submission 才能找到它
        await dispatch_submission(submission.id)
        return ok({"submission_id": str(submission.id), "status": submission.status})
    result = await ProblemService(db).init_verification(user, problem_id, body.verifier_id, body.invite_expires_hours)
    await db.commit()  # 显式提交：确保数据持久化
    return ok(result)


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

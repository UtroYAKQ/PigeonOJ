"""判题提交业务逻辑（docs/contracts/judge.md）。

题目可见性与验题状态经 problems.api 钩子读写（依赖方向 judge → problems 单向）；
系统配置读取走 shared.infra.system_config 平台设施。
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.judge.models import SandboxConfig, Submission, SubmissionTestCaseResult
from app.modules.judge.schemas import SubmissionCreate, SubmissionQuery, VerifyRequest
from app.modules.problems import api as problems
from app.modules.users.api import User
from app.shared.common.errors import (
    APIError,
    AUTH_FORBIDDEN,
    PARAM_FORMAT_INVALID,
    RATE_LIMITED,
    RATE_SEND_TOO_FREQUENT,
    RESOURCE_NOT_FOUND,
)
from app.shared.infra.system_config import get_category_configs
from app.shared.infra.storage import get_storage

_ALLOWED_LANGUAGES = {"python3.12", "cpp17", "java21"}


class SubmissionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _can_access_problem(self, user: User, problem) -> bool:
        if problem.status == "published" and problem.visibility == "public":
            return True
        return await problems.can_manage_problem(self.db, user, problem)

    async def _language_enabled(self, language: str) -> bool:
        """语言白名单来自 sandbox_configs 且启用（docs/contracts/judge.md 提交校验）。"""
        config = await self.db.scalar(select(SandboxConfig).where(SandboxConfig.language == language))
        if config is not None:
            return config.is_enabled
        return language in _ALLOWED_LANGUAGES  # 配置缺失时兜底

    @staticmethod
    def _system_int(configs: dict[str, Any], key: str, default: int) -> int:
        try:
            return int(configs.get(key, default))
        except (TypeError, ValueError):
            return default

    async def _check_rate_limits(self, user: User, problem_id: uuid.UUID) -> None:
        """提交冷却（4001）与全局并发上限（4002），阈值取系统配置 sandbox 域。"""
        from app.modules.judge.dispatcher import active_judge_count
        from app.shared.infra.redis import get_redis

        configs = await get_category_configs(self.db, "sandbox")
        cooldown = max(0, self._system_int(configs, "sandbox.cooldown_seconds", 10))
        if cooldown > 0:
            r = get_redis()
            key = f"judge:cooldown:{user.id}:{problem_id}"
            set_ok = await r.set(key, "1", ex=cooldown, nx=True)
            if not set_ok:
                raise APIError(RATE_SEND_TOO_FREQUENT, "提交冷却中，请稍后再试", 429)
        concurrency = self._system_int(configs, "sandbox.judge_concurrency", 8)
        if concurrency > 0 and await active_judge_count() >= concurrency:
            raise APIError(RATE_LIMITED, "判题并发已达上限，请稍后再试", 429)

    async def create(self, user: User, body: SubmissionCreate) -> Submission:
        problem = await problems.get_problem(self.db, body.problem_id)
        if problem is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
        if not await self._can_access_problem(user, problem):
            raise APIError(AUTH_FORBIDDEN, "题目不可见", 403)
        if not await self._language_enabled(body.language):
            raise APIError(PARAM_FORMAT_INVALID, "语言不在白名单", 400)
        await self._check_rate_limits(user, body.problem_id)
        submission = Submission(user_id=user.id, problem_id=body.problem_id, language=body.language, code=body.code, submit_type="practice")
        self.db.add(submission)
        await self.db.flush()
        return submission

    async def create_verify_submission(self, user: User, problem_id: uuid.UUID, body: VerifyRequest) -> Submission:
        """验题提交（受邀验题人 / 凭邀请链接）：创建 submit_type=verify 的提交。

        验题记录状态机在题库模块（problems.api）；本方法只负责创建判题提交。
        """
        assert body.code is not None and body.language is not None  # schema 已校验
        if body.language not in _ALLOWED_LANGUAGES:
            raise APIError(PARAM_FORMAT_INVALID, "语言不在白名单", 400)
        problem = await problems.get_problem(self.db, problem_id)
        if problem is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
        verification = await problems.get_pending_verification(self.db, problem_id)
        if verification is None:
            raise APIError(RESOURCE_NOT_FOUND, "该题目没有进行中的验题", 404)

        if body.invite_token:
            invite = await problems.validate_verification_invite(self.db, problem_id, body.invite_token)
            if verification.invite_id != invite.id:
                raise APIError(AUTH_FORBIDDEN, "验题邀请与当前验题记录不匹配", 403)
        elif verification.verifier_id != user.id and not await problems.can_manage_problem(
            self.db, user, problem
        ):
            # 出题人 / 管理角色可自行验题：允许驱动当前进行中的验题记录
            raise APIError(AUTH_FORBIDDEN, "只有受邀验题人可以提交验题", 403)

        submission = Submission(
            user_id=user.id,
            problem_id=problem_id,
            verification_id=verification.id,
            language=body.language,
            code=body.code,
            submit_type="verify",
        )
        self.db.add(submission)
        await problems.attach_verification_code(self.db, verification.id, body.language, body.code)
        await self.db.flush()
        return submission

    async def list_for_user(self, user: User, query: SubmissionQuery) -> tuple[list[Submission], int]:
        conditions = [Submission.user_id == user.id]
        if query.problem_id:
            conditions.append(Submission.problem_id == query.problem_id)
        if query.status:
            conditions.append(Submission.status == query.status)
        total = (await self.db.scalar(select(func.count()).select_from(Submission).where(*conditions))) or 0
        rows = list(
            (
                await self.db.execute(
                    select(Submission)
                    .where(*conditions)
                    .order_by(Submission.created_at.desc())
                    .offset((query.page - 1) * query.page_size)
                    .limit(query.page_size)
                )
            ).scalars()
        )
        return rows, int(total)

    async def get_detail(self, user: User, submission_id: uuid.UUID) -> dict:
        """提交详情（owner 可见）：含逐测试点结果；不返回期望输出。"""
        submission = await self.db.scalar(
            select(Submission).where(Submission.id == submission_id, Submission.user_id == user.id)
        )
        if submission is None:
            raise APIError(RESOURCE_NOT_FOUND, "提交不存在", 404)
        rows = list(
            (
                await self.db.execute(
                    select(SubmissionTestCaseResult, problems.TestCase.name, problems.TestCase.sort_order)
                    .join(problems.TestCase, problems.TestCase.id == SubmissionTestCaseResult.test_case_id)
                    .where(SubmissionTestCaseResult.submission_id == submission_id)
                    .order_by(problems.TestCase.sort_order, problems.TestCase.created_at)
                )
            ).all()
        )
        cases = []
        for result, case_name, _sort in rows:
            output_text = None
            if result.output:
                try:
                    content, _ = await get_storage().get_bytes(result.output)
                    output_text = content[:8192].decode("utf-8", errors="replace")
                except Exception:  # noqa: BLE001 - 输出读取失败不阻塞详情
                    output_text = None
            cases.append(
                {
                    "id": str(result.id),
                    "case_name": case_name,
                    "status": result.status,
                    "time_used_ms": result.time_used_ms,
                    "memory_used_kb": result.memory_used_kb,
                    "score": result.score,
                    "output": output_text,
                }
            )
        return {
            "submission": submission,
            "cases": cases,
        }

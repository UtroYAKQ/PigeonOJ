"""判题域服务：提交创建、历史查询、详情、用户自测。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProblemStatus, RuleType, SubmissionStatus, SubmitType
from app.core.exceptions import (
    APIError,
    AUTH_FORBIDDEN,
    PARAM_FORMAT_INVALID,
    RESOURCE_NOT_FOUND,
)
from app.core.redis import get_redis
from app.core.storage import get_storage
from app.models.judge import SandboxConfig, Submission, SubmissionTestCaseResult
from app.models.problem import TestCase
from app.repositories.judge import JudgeRepository, SubmissionRepository, TestCaseRepository
from app.repositories.problem import ProblemRepository
from app.schemas.judge import (
    ProblemSubmissionItem,
    SelfTestRequest,
    SubmissionCreate,
    SubmissionDetailOut,
    SubmissionQuery,
    SubmissionSummary,
    TestCaseResult,
)
from app.services.problem import (
    can_manage_problem,
    get_problem,
)
from app.services.system_config import ConfigService

# 自测冷却 Redis Key 前缀（docs/operations.md Redis 约定；存在即冷却中）
_SELFTEST_COOLDOWN_KEY_PREFIX = "judge:selftest:"


@dataclass(frozen=True)
class SelfTestOrder:
    """已校验的自测派发载荷：api 层据此调用 dispatch_run_code。

    limit 基准取题目 time_limit_ms / memory_limit_mb（C++ 基准），
    换算由网关侧 resolve_limits 完成；max_concurrent 来自 sandbox 域系统配置。
    """

    problem_id: uuid.UUID
    language: str
    code: bytes
    stdin_data: bytes
    problem: object
    sandbox_config: SandboxConfig | None
    cooldown_seconds: int
    max_concurrent: int


class SelfTestService:
    """用户自测（轻量代码运行）：语言白名单、题目可见性、冷却与并发配置。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.problems = ProblemRepository(db)
        self.config_service = ConfigService(db)

    async def create_order(self, user: object, problem_id: uuid.UUID, body: SelfTestRequest) -> SelfTestOrder:
        """校验并组装自测派发载荷：404 / 403（可见性）/ 1001（语言白名单）。"""
        problem = await get_problem(self.db, problem_id)
        # 与题目详情页同一访问规则：已发布 或 具备管理权限（docs/contracts/judge.md 用户自测）
        if problem.status != ProblemStatus.PUBLISHED and not await can_manage_problem(self.db, user, problem):
            raise APIError(AUTH_FORBIDDEN, "无权限", 403)
        config = await self.db.scalar(select(SandboxConfig).where(SandboxConfig.language == body.language))
        if config is None or not config.is_enabled:
            raise APIError(PARAM_FORMAT_INVALID, "语言不在白名单或已禁用", 400)
        return SelfTestOrder(
            problem_id=problem.id,
            language=body.language,
            code=body.code.encode("utf-8"),
            stdin_data=(body.input or "").encode("utf-8"),
            problem=problem,
            sandbox_config=config,
            cooldown_seconds=int(
                await self.config_service.get_value("sandbox", "sandbox.cooldown_seconds", 10)
            ),
            max_concurrent=int(
                await self.config_service.get_value("sandbox", "sandbox.judge_concurrency", 8)
            ),
        )

    async def try_claim_cooldown(self, order: SelfTestOrder, user_id: uuid.UUID) -> bool:
        """按 user+problem 认领自测冷却槽（SETNX + TTL）；False 表示冷却中。"""
        r = get_redis()
        key = f"{_SELFTEST_COOLDOWN_KEY_PREFIX}{user_id}:{order.problem_id}"
        return bool(await r.set(key, "1", nx=True, ex=max(1, order.cooldown_seconds)))

    async def release_cooldown(self, order: SelfTestOrder, user_id: uuid.UUID) -> None:
        """派发失败时释放冷却槽，避免用户为失败的请求买单。"""
        await get_redis().delete(f"{_SELFTEST_COOLDOWN_KEY_PREFIX}{user_id}:{order.problem_id}")


class SubmissionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.submissions = SubmissionRepository(db)
        self.test_cases = TestCaseRepository(db)
        self.judge = JudgeRepository()

    async def create(self, user: object, body: SubmissionCreate) -> Submission:
        problem = await get_problem(self.db, body.problem_id)
        if problem.status != ProblemStatus.PUBLISHED:
            raise APIError(AUTH_FORBIDDEN, "题目未发布，不可提交", 403)
        submission = Submission(
            user_id=user.id,
            problem_id=body.problem_id,
            language=body.language,
            code=body.code,
            submit_type=SubmitType.PRACTICE,
            status=SubmissionStatus.PENDING,
        )
        return await self.submissions.create(submission)

    async def create_contest_submission(
        self,
        user: object,
        *,
        contest_id: uuid.UUID,
        problem_id: uuid.UUID,
        language: str,
        code: str,
        after_contest: bool,
        rule_type: RuleType,
    ) -> Submission:
        """比赛提交（docs/contracts/contests.md 统一入口）：窗口 / 报名 / 存在性校验由比赛服务完成。

        赛制与补题标记在创建时由比赛上下文经命令参数快照进提交行
        （submissions.rule_type / is_after_contest），判题计分按快照派生；
        判题上下文不回查比赛模型（docs/architecture.md 上下文协作）。
        """
        problem = await get_problem(self.db, problem_id)
        if problem.status != ProblemStatus.PUBLISHED:
            raise APIError(AUTH_FORBIDDEN, "题目未发布，不可提交", 403)
        submission = Submission(
            user_id=user.id,
            problem_id=problem_id,
            language=language,
            code=code,
            submit_type=SubmitType.CONTEST,
            contest_id=contest_id,
            rule_type=rule_type,
            is_after_contest=after_contest,
            status=SubmissionStatus.PENDING,
        )
        return await self.submissions.create(submission)

    async def list_for_user(self, user: object, query: SubmissionQuery) -> tuple[list[Submission], int]:
        return await self.submissions.list_for_user(
            user.id, query.problem_id, query.status, query.page, query.page_size,
        )

    async def list_summaries(self, user: object, query: SubmissionQuery) -> tuple[list[SubmissionSummary], int]:
        """本人提交历史摘要。"""
        rows, total = await self.list_for_user(user, query)
        return [SubmissionSummary.model_validate(row) for row in rows], total

    async def list_problem_summaries(
        self, user: object, problem_id: uuid.UUID, status: str | None, keyword: str | None,
        language: str | None, submit_type: str | None, page: int, page_size: int,
    ) -> tuple[list[ProblemSubmissionItem], int]:
        """题目全员提交（题目管理视角：创建者与管理角色，docs/contracts/judge.md）。

        keyword 模糊匹配提交人昵称；language / submit_type 精确匹配。
        """
        problem = await get_problem(self.db, problem_id)
        if not await can_manage_problem(self.db, user, problem):
            raise APIError(AUTH_FORBIDDEN, "无权限查看该题目提交", 403)
        rows, total = await self.submissions.list_for_problem(
            problem_id, status, keyword, language, submit_type, page, page_size,
        )
        return [
            ProblemSubmissionItem(
                id=submission.id,
                user_id=submission.user_id,
                nickname=user_row.nickname,
                language=submission.language,
                submit_type=submission.submit_type,
                status=submission.status,
                score=submission.score,
                time_used_ms=submission.time_used_ms,
                memory_used_kb=submission.memory_used_kb,
                created_at=submission.created_at,
            )
            for submission, user_row in rows
        ], total

    async def get_problem_submission_detail(
        self, user: object, problem_id: uuid.UUID, submission_id: uuid.UUID,
    ) -> SubmissionDetailOut:
        """题目管理视角的提交详情（统一入口）：管理权限 + 归属校验后复用统一装配。"""
        problem = await get_problem(self.db, problem_id)
        if not await can_manage_problem(self.db, user, problem):
            raise APIError(AUTH_FORBIDDEN, "无权限查看该题目提交", 403)
        submission = await self.submissions.get_by_id(submission_id)
        if submission is None or submission.problem_id != problem_id:
            raise APIError(RESOURCE_NOT_FOUND, "提交不存在", 404)
        return await self.build_detail(submission)

    async def get_detail(self, user: object, submission_id: uuid.UUID) -> SubmissionDetailOut:
        submission = await self.submissions.get_by_id(submission_id)
        if submission is None:
            raise APIError(RESOURCE_NOT_FOUND, "提交不存在", 404)
        if submission.user_id != user.id:
            raise APIError(RESOURCE_NOT_FOUND, "提交不存在", 404)
        return await self.build_detail(submission)

    async def build_detail(self, submission: Submission) -> SubmissionDetailOut:
        """装配提交详情（含代码、逐测试点明细；访问控制由调用方完成）。"""
        storage = get_storage()
        results = list(
            (
                await self.db.execute(
                    select(SubmissionTestCaseResult)
                    .where(SubmissionTestCaseResult.submission_id == submission.id)
                    .order_by(SubmissionTestCaseResult.id)
                )
            ).scalars()
        )
        case_ids = [r.test_case_id for r in results if r.test_case_id]
        name_by_id: dict[uuid.UUID, str | None] = (
            dict((await self.db.execute(select(TestCase.id, TestCase.name).where(TestCase.id.in_(case_ids)))).all())
            if case_ids
            else {}
        )
        cases = []
        for r in results:
            output = None
            if r.output:
                try:
                    raw, _ = await storage.get_bytes(r.output)
                    output = raw.decode("utf-8", errors="replace")
                except Exception:
                    output = None
            cases.append(TestCaseResult(
                id=r.id,
                case_name=name_by_id.get(r.test_case_id),
                status=r.status,
                time_used_ms=r.time_used_ms,
                memory_used_kb=r.memory_used_kb,
                score=r.score,
                output=output,
            ))
        detail = SubmissionDetailOut.model_validate(submission)
        detail.cases = cases
        return detail

    async def create_verify_submission(self, user: object, problem_id: uuid.UUID, body: object) -> Submission:
        from app.services.problem import get_pending_verification, attach_verification_code
        verification = await get_pending_verification(self.db, problem_id)
        if verification is None:
            raise APIError(RESOURCE_NOT_FOUND, "无进行中的验题记录", 404)
        token = getattr(body, "invite_token", None)
        if token is not None:
            from app.services.problem import validate_verification_invite
            await validate_verification_invite(self.db, verification.id, token)
        return await attach_verification_code(
            self.db,
            verification.id,
            user.id,
            body.code,
            body.language,
        )

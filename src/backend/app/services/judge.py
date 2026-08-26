"""判题域服务：提交创建、历史查询、详情。"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProblemStatus, SubmissionStatus, SubmitType
from app.core.exceptions import (
    APIError,
    AUTH_FORBIDDEN,
    RESOURCE_NOT_FOUND,
)
from app.core.storage import get_storage
from app.models.judge import Submission, SubmissionTestCaseResult
from app.models.problem import TestCase
from app.repositories.judge import JudgeRepository, SubmissionRepository, TestCaseRepository
from app.repositories.problem import ProblemRepository
from app.schemas.judge import (
    SubmissionCreate,
    SubmissionDetail,
    SubmissionDetailOut,
    SubmissionQuery,
    TestCaseResult,
)
from app.services.problem import (
    can_manage_problem,
    get_problem,
)


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

    async def list_for_user(self, user: object, query: SubmissionQuery) -> tuple[list[Submission], int]:
        return await self.submissions.list_for_user(
            user.id, query.problem_id, query.status, query.page, query.page_size,
        )

    async def is_score_restricted(self, submission: Submission) -> bool:
        """得分可见性策略：ACM 赛制比赛进行中的提交隐藏得分与测试点明细。

        IOI 赛制 / 练习 / 验题 / 赛后（含补题）恒为完整可见。
        contests 模块接入点：submit_type=contest 且关联比赛 rule_type=ACM
        且 end_time 未到时返回 True；contests 模块落地前无比赛数据，恒为 False。
        """
        if submission.submit_type != SubmitType.CONTEST or not submission.contest_id:
            return False
        # TODO(contests): 查 contests 表 —— rule_type == 'ACM' and now() < end_time 时返回 True
        return False

    async def get_detail(self, user: object, submission_id: uuid.UUID) -> SubmissionDetailOut:
        submission = await self.submissions.get_by_id(submission_id)
        if submission is None:
            raise APIError(RESOURCE_NOT_FOUND, "提交不存在", 404)
        if submission.user_id != user.id:
            raise APIError(RESOURCE_NOT_FOUND, "提交不存在", 404)
        restricted = await self.is_score_restricted(submission)
        storage = get_storage()
        results = [] if restricted else list(
            (
                await self.db.execute(
                    select(SubmissionTestCaseResult)
                    .where(SubmissionTestCaseResult.submission_id == submission_id)
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
        detail = SubmissionDetail.model_validate(submission).model_dump()
        if restricted:
            detail["score"] = None
        return SubmissionDetailOut(**detail, cases=cases, restricted=restricted)

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

"""Judge Worker 数据访问边界：只在内部读取提交和非样例测试点。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.judge.models import Problem, Submission, SubmissionTestCaseResult, TestCase


@dataclass(frozen=True)
class SubmissionBundle:
    submission: Submission
    problem: Problem
    test_cases: list[TestCase]


class JudgeRepository:
    async def get_bundle(self, db: AsyncSession, submission_id: uuid.UUID) -> SubmissionBundle | None:
        submission = await db.get(Submission, submission_id)
        if submission is None:
            return None
        problem = await db.get(Problem, submission.problem_id)
        if problem is None:
            return None
        cases = list(
            (await db.execute(
                select(TestCase)
                .where(TestCase.problem_id == submission.problem_id, TestCase.is_sample.is_(False))
                .order_by(TestCase.sort_order, TestCase.id)
            )).scalars()
        )
        return SubmissionBundle(submission, problem, cases)

    async def mark_judging(self, db: AsyncSession, submission: Submission) -> None:
        submission.status = "judging"
        submission.error_message = None
        await db.flush()

    async def write_case_result(
        self, db: AsyncSession, submission_id: uuid.UUID, test_case: TestCase, *, status: str,
        time_used_ms: int | None, memory_used_kb: int | None, score: int, output: str | None,
    ) -> None:
        record = await db.scalar(
            select(SubmissionTestCaseResult).where(
                SubmissionTestCaseResult.submission_id == submission_id,
                SubmissionTestCaseResult.test_case_id == test_case.id,
            )
        )
        if record is None:
            record = SubmissionTestCaseResult(submission_id=submission_id, test_case_id=test_case.id, status=status)
            db.add(record)
        record.status = status
        record.time_used_ms = time_used_ms
        record.memory_used_kb = memory_used_kb
        record.score = score
        record.output = output
        await db.flush()

    async def finish_submission(
        self, db: AsyncSession, submission: Submission, *, status: str, score: int,
        time_used_ms: int | None, memory_used_kb: int | None, error_message: str | None = None,
    ) -> None:
        submission.status = status
        submission.score = score
        submission.time_used_ms = time_used_ms
        submission.memory_used_kb = memory_used_kb
        submission.error_message = error_message
        await db.flush()

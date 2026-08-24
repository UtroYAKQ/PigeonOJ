"""Judge Worker 数据访问边界：只在内部读取提交和非样例测试点。

题目 / 测试点模型经 problems.api 门面引用（judge → problems 单向依赖）。
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.judge.models import Submission, SubmissionTestCaseResult
from app.modules.problems import api as problems


class JudgeRepository:
    async def write_case_result(
        self, db: AsyncSession, submission_id: uuid.UUID, test_case: problems.TestCase, *, status: str,
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

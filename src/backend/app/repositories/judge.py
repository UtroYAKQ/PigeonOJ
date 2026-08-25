"""判题域仓储：Submission / TestCase 数据访问。"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.judge import Submission, SubmissionTestCaseResult
from app.models.problem import TestCase


class JudgeRepository:
    async def write_case_result(
        self, db: AsyncSession, submission_id: uuid.UUID, test_case, *, status: str,
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


class SubmissionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, submission_id: uuid.UUID) -> Submission | None:
        return await self.db.get(Submission, submission_id)

    async def create(self, submission: Submission) -> Submission:
        self.db.add(submission)
        await self.db.flush()
        return submission

    async def list_for_user(
        self, user_id: uuid.UUID, problem_id: uuid.UUID | None, status: str | None,
        page: int, page_size: int,
    ) -> tuple[list[Submission], int]:
        conditions = [Submission.user_id == user_id]
        if problem_id:
            conditions.append(Submission.problem_id == problem_id)
        if status:
            conditions.append(Submission.status == status)
        total = (await self.db.scalar(select(func.count()).select_from(Submission).where(*conditions))) or 0
        rows = list(
            (
                await self.db.execute(
                    select(Submission)
                    .where(*conditions)
                    .order_by(Submission.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        return rows, int(total)


class TestCaseRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, test_case_id: uuid.UUID) -> TestCase | None:
        return await self.db.get(TestCase, test_case_id)

    async def list_formal_cases(self, problem_id: uuid.UUID) -> list[TestCase]:
        """按判题顺序返回正式测试点（test_cases 表内全部为正式数据）。"""
        return list(
            (
                await self.db.execute(
                    select(TestCase)
                    .where(TestCase.problem_id == problem_id)
                    .order_by(TestCase.sort_order, TestCase.created_at)
                )
            ).scalars()
        )

    async def count_formal_cases(self, problem_id: uuid.UUID) -> int:
        return (
            await self.db.scalar(
                select(func.count())
                .select_from(TestCase)
                .where(
                    TestCase.problem_id == problem_id,
                    TestCase.input_oss_id.is_not(None),
                    TestCase.expected_output_oss_id.is_not(None),
                )
            )
        ) or 0

    async def get_by_ids(self, problem_id: uuid.UUID, case_ids: list[uuid.UUID]) -> list[TestCase]:
        if not case_ids:
            return []
        return list(
            (
                await self.db.execute(
                    select(TestCase).where(TestCase.problem_id == problem_id, TestCase.id.in_(case_ids))
                )
            ).scalars()
        )

    async def add_test_case(self, row: TestCase) -> None:
        self.db.add(row)
        await self.db.flush()

    async def delete_cases(self, cases: list[TestCase]) -> None:
        for row in cases:
            await self.db.delete(row)

    async def max_updated_at(self, problem_id: uuid.UUID) -> uuid.UUID | None:
        return await self.db.scalar(
            select(func.max(TestCase.updated_at)).where(TestCase.problem_id == problem_id)
        )

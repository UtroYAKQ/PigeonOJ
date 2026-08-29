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
    """测试点数据访问。

    行不可变版本化：集合成员资格由 problems.active_case_ids / pending_case_ids
    引用列表定义，
    行永不物理删除，被取代的旧行自然退役留档。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, test_case_id: uuid.UUID) -> TestCase | None:
        return await self.db.get(TestCase, test_case_id)

    async def list_by_problem(self, problem_id: uuid.UUID) -> list[TestCase]:
        """题目全部版本行（含已退役），按判题顺序。"""
        return list(
            (
                await self.db.execute(
                    select(TestCase)
                    .where(TestCase.problem_id == problem_id)
                    .order_by(TestCase.sort_order, TestCase.created_at)
                )
            ).scalars()
        )

    async def list_by_ids(
        self, problem_id: uuid.UUID, case_ids: list[uuid.UUID],
    ) -> list[TestCase]:
        """按给定 id 顺序返回集合行（限定 problem 防越界；未知 id 忽略）。"""
        if not case_ids:
            return []
        rows = {
            row.id: row
            for row in (
                await self.db.execute(
                    select(TestCase).where(TestCase.problem_id == problem_id, TestCase.id.in_(case_ids))
                )
            ).scalars()
        }
        return [rows[cid] for cid in case_ids if cid in rows]

    async def add_test_case(self, row: TestCase) -> None:
        self.db.add(row)
        await self.db.flush()

    async def max_updated_at(
        self, problem_id: uuid.UUID, case_ids: list[uuid.UUID],
    ) -> object | None:
        """集合内最大 updated_at（详情展示用；空集返回 None）。"""
        if not case_ids:
            return None
        return await self.db.scalar(
            select(func.max(TestCase.updated_at)).where(
                TestCase.problem_id == problem_id, TestCase.id.in_(case_ids)
            )
        )

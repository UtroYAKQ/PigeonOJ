"""判题域仓储：Submission / TestCase 数据访问。"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.judge import Submission, SubmissionTestCaseResult
from app.models.problem import Problem, TestCase
from app.models.user import User


class JudgeRepository:
    async def write_case_result(
        self, db: AsyncSession, submission_id: uuid.UUID, test_case, *, status: str,
        time_used_ms: int | None, memory_used_kb: int | None, score: int, output: str | None,
        message: str | None = None,
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
        record.message = message
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

    async def list_for_problem(
        self, problem_id: uuid.UUID, status: str | None, keyword: str | None,
        language: str | None, submit_type: str | None, page: int, page_size: int,
    ) -> tuple[list[tuple[Submission, User]], int]:
        """题目全员提交（join 用户，提交时间倒序分页；题目管理视角，权限由服务层校验）。

        keyword 模糊匹配提交人昵称；language / submit_type 精确匹配。
        """
        conditions = [Submission.problem_id == problem_id]
        if status:
            conditions.append(Submission.status == status)
        if keyword:
            conditions.append(User.nickname.ilike(f"%{keyword}%"))
        if language:
            conditions.append(Submission.language == language)
        if submit_type:
            conditions.append(Submission.submit_type == submit_type)
        # 显式 join：keyword 条件引用 User 列，避免 count 查询被隐式交叉连接放大
        total = (
            await self.db.scalar(
                select(func.count())
                .select_from(Submission)
                .join(User, User.id == Submission.user_id)
                .where(*conditions)
            )
        ) or 0
        rows = (
            await self.db.execute(
                select(Submission, User)
                .join(User, User.id == Submission.user_id)
                .where(*conditions)
                .order_by(Submission.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [(submission, user) for submission, user in rows], int(total)

    async def list_all_for_admin(
        self, *, submit_type: str | None, user_id: uuid.UUID | None,
        problem_id: uuid.UUID | None, status: str | None, language: str | None,
        keyword: str | None, page: int, page_size: int,
    ) -> tuple[list[tuple[Submission, User]], dict[uuid.UUID, str], int]:
        """全站提交（admin 管理面板）：submit_type / user / problem / status / language 精确过滤，
        keyword 模糊匹配提交人昵称；join 用户 + join 题目取标题，提交时间倒序分页。

        返回 (行, 题目标题映射, total)；标题映射供 service 组装（列表项含题号短 ID + 标题）。
        """
        conditions = []
        if submit_type:
            conditions.append(Submission.submit_type == submit_type)
        if user_id:
            conditions.append(Submission.user_id == user_id)
        if problem_id:
            conditions.append(Submission.problem_id == problem_id)
        if status:
            conditions.append(Submission.status == status)
        if language:
            conditions.append(Submission.language == language)
        if keyword:
            conditions.append(User.nickname.ilike(f"%{keyword}%"))

        count_stmt = select(func.count()).select_from(Submission)
        rows_stmt = (
            select(Submission, User, Problem.title)
            # 显式 join：rows_stmt 引用 Problem.title，缺 join 会退化为笛卡尔积
            # （每行被题目总数放大，列表出现同一提交重复多行，回归修复）
            .join(User, User.id == Submission.user_id)
            .join(Problem, Problem.id == Submission.problem_id)
        )
        if conditions:
            count_stmt = count_stmt.join(User, User.id == Submission.user_id).where(*conditions)
            rows_stmt = rows_stmt.where(*conditions)
        total = (await self.db.scalar(count_stmt)) or 0
        rows = (
            await self.db.execute(
                rows_stmt.order_by(Submission.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        title_map = {submission.problem_id: title for submission, _user, title in rows}
        return (
            [(submission, user) for submission, user, _title in rows],
            title_map,
            int(total),
        )


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

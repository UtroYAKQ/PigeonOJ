"""比赛仓储：Contest / ContestProblem / ContestRegistration / ContestRanking 数据访问。

榜单更新全部为条件写入（WHERE is_frozen = false，docs/contracts/contests.md 第 4 条），
行不存在时经 INSERT ON CONFLICT DO NOTHING 原子补建，避免判题并发下的重复行。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ContestStatus,
    ContestType,
    ProblemStatus,
    ProblemVisibility,
    RegistrationStatus,
    SubmissionStatus,
    SubmitType,
)
from app.models.contest import Contest, ContestProblem, ContestRanking, ContestRegistration
from app.models.judge import Submission
from app.models.problem import Problem
from app.models.user import User


class ContestRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, contest_id: uuid.UUID) -> Contest | None:
        return await self.db.get(Contest, contest_id)

    async def create(self, contest: Contest) -> Contest:
        self.db.add(contest)
        await self.db.flush()
        return contest

    async def list_public(
        self, *, page: int, page_size: int, status: str | None, keyword: str | None = None
    ) -> tuple[list[Contest], int]:
        """比赛中心：仅公开比赛，可按状态过滤与名称关键字搜索，开赛时间倒序。"""
        conditions = [Contest.contest_type == ContestType.PUBLIC]
        if status:
            conditions.append(Contest.status == status)
        if keyword:
            conditions.append(Contest.title.ilike(f"%{keyword}%"))
        total = (
            await self.db.scalar(select(func.count()).select_from(Contest).where(*conditions))
        ) or 0
        rows = list(
            (
                await self.db.execute(
                    select(Contest)
                    .where(*conditions)
                    .order_by(Contest.start_time.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        return rows, int(total)

    async def count_registrations(self, contest_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not contest_ids:
            return {}
        rows = await self.db.execute(
            select(ContestRegistration.contest_id, func.count())
            .where(
                ContestRegistration.contest_id.in_(contest_ids),
                ContestRegistration.status == RegistrationStatus.REGISTERED,
            )
            .group_by(ContestRegistration.contest_id)
        )
        return {cid: int(count) for cid, count in rows.all()}

    async def count_problems(self, contest_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not contest_ids:
            return {}
        rows = await self.db.execute(
            select(ContestProblem.contest_id, func.count())
            .where(ContestProblem.contest_id.in_(contest_ids))
            .group_by(ContestProblem.contest_id)
        )
        return {cid: int(count) for cid, count in rows.all()}

    # ---------------- 报名 ----------------

    async def get_registration(
        self, contest_id: uuid.UUID, user_id: uuid.UUID
    ) -> ContestRegistration | None:
        return await self.db.scalar(
            select(ContestRegistration).where(
                ContestRegistration.contest_id == contest_id,
                ContestRegistration.user_id == user_id,
            )
        )

    async def register(self, registration: ContestRegistration) -> None:
        self.db.add(registration)
        await self.db.flush()

    async def list_user_registrations(
        self, user_id: uuid.UUID, *, page: int, page_size: int, status: str | None
    ) -> tuple[list[tuple[ContestRegistration, Contest]], int]:
        """我的比赛：报名记录 join 比赛，按开赛时间倒序。"""
        conditions = [ContestRegistration.user_id == user_id]
        if status:
            conditions.append(ContestRegistration.status == status)
        total = (
            await self.db.scalar(
                select(func.count())
                .select_from(ContestRegistration)
                .join(Contest, Contest.id == ContestRegistration.contest_id)
                .where(*conditions)
            )
        ) or 0
        rows = (
            await self.db.execute(
                select(ContestRegistration, Contest)
                .join(Contest, Contest.id == ContestRegistration.contest_id)
                .where(*conditions)
                .order_by(Contest.start_time.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [(reg, contest) for reg, contest in rows], int(total)

    # ---------------- 题目编排 ----------------

    async def list_contest_problems(
        self, contest_id: uuid.UUID
    ) -> list[tuple[ContestProblem, Problem]]:
        """比赛题目（带题目元信息），按 sort_order 排列。"""
        rows = await self.db.execute(
            select(ContestProblem, Problem)
            .join(Problem, Problem.id == ContestProblem.problem_id)
            .where(ContestProblem.contest_id == contest_id)
            .order_by(ContestProblem.sort_order)
        )
        return [(cp, problem) for cp, problem in rows.all()]

    async def get_contest_problem(
        self, contest_id: uuid.UUID, problem_id: uuid.UUID
    ) -> ContestProblem | None:
        return await self.db.scalar(
            select(ContestProblem).where(
                ContestProblem.contest_id == contest_id,
                ContestProblem.problem_id == problem_id,
            )
        )

    async def replace_problems(self, contest_id: uuid.UUID, rows: list[ContestProblem]) -> None:
        await self.db.execute(delete(ContestProblem).where(ContestProblem.contest_id == contest_id))
        self.db.add_all(rows)
        await self.db.flush()

    async def list_arrangeable(
        self, user_id: uuid.UUID, problem_ids: list[uuid.UUID]
    ) -> list[Problem]:
        """编排候选校验：已发布且（全站公开 或 本人私有）题目（docs/contracts/contests.md）。

        团队题目（team_id）随 teams 模块引入后，此处需一并排除团队题库题目。
        """
        if not problem_ids:
            return []
        return list(
            (
                await self.db.execute(
                    select(Problem).where(
                        Problem.id.in_(problem_ids),
                        Problem.status == ProblemStatus.PUBLISHED,
                        or_(
                            Problem.visibility == ProblemVisibility.PUBLIC,
                            Problem.owner_id == user_id,
                        ),
                    )
                )
            ).scalars()
        )

    async def search_arrangeable(
        self,
        user_id: uuid.UUID,
        *,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Problem], int]:
        """编排页题目搜索：已发布且（全站公开 或 本人私有），标题模糊，开题时间倒序。"""
        conditions = [
            Problem.status == ProblemStatus.PUBLISHED,
            or_(
                Problem.visibility == ProblemVisibility.PUBLIC,
                Problem.owner_id == user_id,
            ),
        ]
        if keyword:
            conditions.append(Problem.title.ilike(f"%{keyword}%"))
        total = (
            await self.db.scalar(select(func.count()).select_from(Problem).where(*conditions))
        ) or 0
        rows = list(
            (
                await self.db.execute(
                    select(Problem)
                    .where(*conditions)
                    .order_by(Problem.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        return rows, int(total)


    # ---- 周期状态推进（ContestService.transition 调用）----

    async def start_due_contests(self, now: datetime) -> None:
        """开赛：scheduled 且到达开始时间的比赛置为 running。"""
        await self.db.execute(
            update(Contest)
            .where(Contest.status == ContestStatus.SCHEDULED, Contest.start_time <= now)
            .values(status=ContestStatus.RUNNING)
        )

    async def list_freeze_candidates(self, now: datetime) -> list[Contest]:
        """封榜候选：running 且未冻结且已到封榜时间（freeze_time 非空且 <= now）。"""
        rows = await self.db.execute(
            select(Contest).where(
                Contest.status == ContestStatus.RUNNING,
                Contest.board_frozen == False,  # noqa: E712
                Contest.freeze_time.is_not(None),
                Contest.freeze_time <= now,
            )
        )
        return list(rows.scalars())

    async def freeze_contests(self, contest_ids: list[uuid.UUID], frozen_at: datetime) -> None:
        """批量置为已冻结（frozen_at 记录进入封榜时刻，滚榜揭晓序列的边界）。"""
        await self.db.execute(
            update(Contest)
            .where(Contest.id.in_(contest_ids))
            .values(board_frozen=True, frozen_at=frozen_at)
        )

    async def finish_due_contests(self, now: datetime) -> None:
        """结束：running 且到达结束时间的比赛置为 finished（解冻始终人工触发）。"""
        await self.db.execute(
            update(Contest)
            .where(Contest.status == ContestStatus.RUNNING, Contest.end_time <= now)
            .values(status=ContestStatus.FINISHED)
        )


class ContestRankingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_row(
        self, contest_id: uuid.UUID, user_id: uuid.UUID, problem_id: uuid.UUID
    ) -> ContestRanking | None:
        return await self.db.scalar(
            select(ContestRanking).where(
                ContestRanking.contest_id == contest_id,
                ContestRanking.user_id == user_id,
                ContestRanking.problem_id == problem_id,
            )
        )

    async def ensure_row(
        self, contest_id: uuid.UUID, user_id: uuid.UUID, problem_id: uuid.UUID, *, frozen: bool
    ) -> None:
        """原子补建榜单行（判题并发下 INSERT ON CONFLICT 幂等）。"""
        await self.db.execute(
            pg_insert(ContestRanking)
            .values(
                contest_id=contest_id,
                user_id=user_id,
                problem_id=problem_id,
                is_frozen=frozen,
            )
            .on_conflict_do_nothing(constraint="uq_contest_rankings_row")
        )

    async def increment_attempts(
        self, contest_id: uuid.UUID, user_id: uuid.UUID, problem_id: uuid.UUID
    ) -> int:
        """错误提交：attempts + 1（仅未通过且未冻结行生效，返回是否命中）。"""
        result = await self.db.execute(
            update(ContestRanking)
            .where(
                ContestRanking.contest_id == contest_id,
                ContestRanking.user_id == user_id,
                ContestRanking.problem_id == problem_id,
                ContestRanking.accepted == False,  # noqa: E712 - 条件更新契约原文
                ContestRanking.is_frozen == False,  # noqa: E712
            )
            .values(attempts=ContestRanking.attempts + 1, updated_at=func.now())
        )
        return result.rowcount or 0

    async def mark_accepted(
        self,
        contest_id: uuid.UUID,
        user_id: uuid.UUID,
        problem_id: uuid.UUID,
        *,
        accepted_at: datetime,
        penalty: int,
    ) -> int:
        """首次通过：幂等条件更新（仅 accepted=false 且未冻结行生效）。"""
        result = await self.db.execute(
            update(ContestRanking)
            .where(
                ContestRanking.contest_id == contest_id,
                ContestRanking.user_id == user_id,
                ContestRanking.problem_id == problem_id,
                ContestRanking.accepted == False,  # noqa: E712
                ContestRanking.is_frozen == False,  # noqa: E712
            )
            .values(accepted=True, accepted_at=accepted_at, penalty=penalty, updated_at=func.now())
        )
        return result.rowcount or 0

    async def bump_score(
        self, contest_id: uuid.UUID, user_id: uuid.UUID, problem_id: uuid.UUID, score: int
    ) -> int:
        """IOI：每题取历史最高分（仅未冻结行生效）。"""
        result = await self.db.execute(
            update(ContestRanking)
            .where(
                ContestRanking.contest_id == contest_id,
                ContestRanking.user_id == user_id,
                ContestRanking.problem_id == problem_id,
                ContestRanking.is_frozen == False,  # noqa: E712
            )
            .values(
                score=func.greatest(ContestRanking.score, score), updated_at=func.now()
            )
        )
        return result.rowcount or 0

    async def freeze_rows(self, contest_id: uuid.UUID) -> None:
        """封榜快照：该比赛全部榜单行置 is_frozen=true。"""
        await self.db.execute(
            update(ContestRanking)
            .where(ContestRanking.contest_id == contest_id)
            .values(is_frozen=True, updated_at=func.now())
        )

    async def delete_rows(self, contest_id: uuid.UUID) -> None:
        await self.db.execute(delete(ContestRanking).where(ContestRanking.contest_id == contest_id))

    async def add_rows(self, rows: list[ContestRanking]) -> None:
        self.db.add_all(rows)
        await self.db.flush()

    async def list_rows_with_users(
        self, contest_id: uuid.UUID
    ) -> list[tuple[ContestRanking, User]]:
        rows = await self.db.execute(
            select(ContestRanking, User)
            .join(User, User.id == ContestRanking.user_id)
            .where(ContestRanking.contest_id == contest_id)
        )
        return [(row, user) for row, user in rows.all()]


class ContestSubmissionQueryRepository:
    """比赛提交查询（榜单重算的权威数据源）。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_team_nicknames(self, contest_id: uuid.UUID) -> dict[uuid.UUID, str]:
        """该比赛出现过提交的用户昵称映射（滚榜/榜单装配用，单查询无 N+1）。"""
        rows = await self.db.execute(
            select(Submission.user_id, User.nickname)
            .join(User, User.id == Submission.user_id)
            .where(
                Submission.contest_id == contest_id,
                Submission.submit_type == SubmitType.CONTEST,
                Submission.is_after_contest == False,  # noqa: E712
            )
            .distinct()
        )
        return dict(rows.all())

    async def list_contest_submissions(
        self, contest_id: uuid.UUID
    ) -> list[Submission]:
        """比赛内正式提交（不含赛后补题），按提交时间正序。"""
        return list(
            (
                await self.db.execute(
                    select(Submission)
                    .where(
                        Submission.contest_id == contest_id,
                        Submission.submit_type == SubmitType.CONTEST,
                        Submission.is_after_contest == False,  # noqa: E712
                    )
                    .order_by(Submission.created_at)
                )
            ).scalars()
        )

    async def list_records_with_users(
        self, contest_id: uuid.UUID, *, page: int, page_size: int,
        keyword: str | None = None, language: str | None = None,
        status: str | None = None, problem_id: uuid.UUID | None = None,
    ) -> tuple[list[tuple[Submission, User]], int]:
        """比赛提交记录（join 用户，提交时间倒序分页）。

        keyword 模糊匹配提交人昵称；language / status / problem_id 精确过滤。
        """
        conditions = [
            Submission.contest_id == contest_id,
            Submission.submit_type == SubmitType.CONTEST,
        ]
        if keyword:
            conditions.append(User.nickname.ilike(f"%{keyword}%"))
        if language:
            conditions.append(Submission.language == language)
        if status:
            conditions.append(Submission.status == status)
        if problem_id:
            conditions.append(Submission.problem_id == problem_id)
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

    async def get_contest_submission(
        self, contest_id: uuid.UUID, submission_id: uuid.UUID
    ) -> Submission | None:
        """比赛内提交（详情访问按 contest 归属校验，不信任客户端 contest_id）。"""
        return await self.db.scalar(
            select(Submission).where(
                Submission.id == submission_id,
                Submission.contest_id == contest_id,
                Submission.submit_type == SubmitType.CONTEST,
            )
        )

    async def list_accepted_submissions(
        self, contest_id: uuid.UUID, user_id: uuid.UUID, problem_id: uuid.UUID
    ) -> list[Submission]:
        """榜单单格成功提交：该 (选手, 题目) 在比赛内的 AC 提交（不含赛后补题），时间正序。"""
        return list(
            (
                await self.db.execute(
                    select(Submission)
                    .where(
                        Submission.contest_id == contest_id,
                        Submission.user_id == user_id,
                        Submission.problem_id == problem_id,
                        Submission.submit_type == SubmitType.CONTEST,
                        Submission.status == SubmissionStatus.ACCEPTED,
                        Submission.is_after_contest == False,  # noqa: E712
                    )
                    .order_by(Submission.created_at)
                )
            ).scalars()
        )

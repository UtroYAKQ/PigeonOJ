"""题库仓储：Problem / Tag / Verification 数据访问。"""
from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ProblemScope,
    ProblemStatus,
    ProblemVisibility,
    SubmissionStatus,
    SubmitType,
    TagStatus,
    VerificationStatus,
)
from app.models.judge import Submission
from app.models.problem import (
    Problem,
    ProblemCounter,
    ProblemTag,
    ProblemTagRelation,
    ProblemVerification,
    TestCase,
)
from app.schemas.problem import ProblemQuery


class ProblemRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, problem_id: uuid.UUID) -> Problem | None:
        return await self.db.get(Problem, problem_id)

    async def create(self, problem: Problem) -> Problem:
        self.db.add(problem)
        await self.db.flush()
        return problem

    async def bump_counters(self, problem_id: uuid.UUID, *, accepted: bool) -> None:
        """通过率计数 upsert 原子累加（INSERT ... ON CONFLICT，并发安全；docs/contracts/judge.md）。

        计数行不存在时自动创建；统计口径由调用方保证。
        """
        step_accepted = 1 if accepted else 0
        stmt = (
            pg_insert(ProblemCounter)
            .values(problem_id=problem_id, submission_count=1, accepted_count=step_accepted)
            .on_conflict_do_update(
                index_elements=[ProblemCounter.problem_id],
                set_={
                    # 键用 Column 对象（= 目标表列）；值中同名列引用的是已存在行（DO UPDATE SET col = col + 1 语义）
                    ProblemCounter.submission_count: ProblemCounter.submission_count + 1,
                    ProblemCounter.accepted_count: ProblemCounter.accepted_count + step_accepted,
                    ProblemCounter.updated_at: func.now(),
                },
            )
        )
        await self.db.execute(stmt)

    async def counters_for(self, problem_ids: list[uuid.UUID]) -> dict[uuid.UUID, ProblemCounter]:
        """按 id 批量取通过率计数行（无记录的 id 不在返回中）。"""
        if not problem_ids:
            return {}
        rows = (
            await self.db.execute(
                select(ProblemCounter).where(ProblemCounter.problem_id.in_(problem_ids))
            )
        ).scalars()
        return {row.problem_id: row for row in rows}

    async def solve_status_map(
        self, user_id: uuid.UUID, problem_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, bool]:
        """按题批量返回当前用户作答状态（题库列表 solved 标识）。

        True=已通过（存在 AC 提交）；False=已尝试未通过；用户未提交过的题不在返回中。
        验题提交为管理动作不计入（与 problem_counters 口径一致）；
        走 ix_submissions_user_problem_created (user_id, problem_id) 前缀，页大小 ≤100 毫秒级。
        """
        if not problem_ids:
            return {}
        rows = (
            await self.db.execute(
                select(
                    Submission.problem_id,
                    func.bool_or(Submission.status == SubmissionStatus.ACCEPTED).label("solved"),
                )
                .where(
                    Submission.user_id == user_id,
                    Submission.problem_id.in_(problem_ids),
                    Submission.submit_type != SubmitType.VERIFY,
                )
                .group_by(Submission.problem_id)
            )
        ).all()
        return {row.problem_id: bool(row.solved) for row in rows}

    async def verification_snapshot_fields(self, problem_ids: list[uuid.UUID]) -> list:
        """批量取重验判定所需字段（id / verified_at / samples_updated_at / pending_case_ids）。"""
        if not problem_ids:
            return []
        return list(
            (
                await self.db.execute(
                    select(
                        Problem.id,
                        Problem.verified_at,
                        Problem.samples_updated_at,
                        Problem.pending_case_ids,
                    ).where(Problem.id.in_(problem_ids))
                )
            ).all()
        )

    async def list_published(self, query: ProblemQuery, viewer_id: uuid.UUID | None, see_all: bool) -> tuple[list[Problem], int]:
        """题库列表：scope=all 仅 published+public；scope=mine 为管理视图
        （admin 见全量，其余用户仅本人创建，docs/contracts/problems.md 数据所有权）。"""
        conditions = []
        if query.scope == ProblemScope.MINE:
            if not see_all and viewer_id is not None:
                conditions.append(Problem.owner_id == viewer_id)
            if query.status:
                conditions.append(Problem.status == query.status)
        elif query.mine and viewer_id is not None:
            # 题库中心「我的」勾选：仅本人已发布题目（任意可见性，含私有已发布；草稿/归档走管理视图）
            conditions.extend([
                Problem.owner_id == viewer_id,
                Problem.status == ProblemStatus.PUBLISHED,
            ])
        else:
            conditions.extend([Problem.status == ProblemStatus.PUBLISHED, Problem.visibility == ProblemVisibility.PUBLIC])
        if query.keyword:
            conditions.append(Problem.title.ilike(f"%{query.keyword}%"))
        if query.tag:
            conditions.append(
                Problem.id.in_(
                    select(ProblemTagRelation.problem_id)
                    .join(ProblemTag, ProblemTag.id == ProblemTagRelation.tag_id)
                    .where(ProblemTag.name == query.tag)
                )
            )
        # 难度分闭区间筛选（未评分题目不落在任何区间内）
        if query.difficulty_min is not None:
            conditions.append(Problem.difficulty >= query.difficulty_min)
        if query.difficulty_max is not None:
            conditions.append(Problem.difficulty <= query.difficulty_max)
        total = (
            await self.db.scalar(select(func.count()).select_from(Problem).where(*conditions))
        ) or 0
        rows = list(
            (
                await self.db.execute(
                    select(Problem)
                    .where(*conditions)
                    .order_by(Problem.created_at.desc())
                    .offset((query.page - 1) * query.page_size)
                    .limit(query.page_size)
                )
            ).scalars()
        )
        return rows, int(total)

    async def get_test_cases(self, problem_id: uuid.UUID) -> list[TestCase]:
        return list(
            (
                await self.db.execute(
                    select(TestCase)
                    .where(TestCase.problem_id == problem_id)
                    .order_by(TestCase.sort_order, TestCase.created_at)
                )
            ).scalars()
        )

    async def add_test_cases(self, cases: list[TestCase]) -> None:
        self.db.add_all(cases)
        await self.db.flush()


class TagRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, tag_id: uuid.UUID) -> ProblemTag | None:
        return await self.db.get(ProblemTag, tag_id)

    async def get_by_name(self, name: str) -> ProblemTag | None:
        return await self.db.scalar(select(ProblemTag).where(ProblemTag.name == name))

    async def create(self, tag: ProblemTag) -> ProblemTag:
        self.db.add(tag)
        await self.db.flush()
        return tag

    async def list_active(self) -> list[ProblemTag]:
        return list(
            (
                await self.db.execute(
                    select(ProblemTag)
                    .where(ProblemTag.status == TagStatus.ACTIVE)
                    .order_by(ProblemTag.name)
                )
            ).scalars()
        )

    async def list_page(
        self, keyword: str | None, page: int, page_size: int
    ) -> tuple[list[ProblemTag], int]:
        """激活标签分页列表（支持 keyword 搜索）。"""
        where = [ProblemTag.status == TagStatus.ACTIVE]
        if keyword:
            where.append(ProblemTag.name.ilike(f"%{keyword}%"))
        total = await self.db.scalar(select(func.count()).where(*where)) or 0
        rows = list(
            (
                await self.db.execute(
                    select(ProblemTag)
                    .where(*where)
                    .order_by(ProblemTag.name)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        return rows, total

    async def list_all_page(
        self, keyword: str | None, page: int, page_size: int
    ) -> tuple[list[ProblemTag], int]:
        """管理分页列表：含已归档（激活在前、归档在后，组内按名称），支持 keyword 模糊。"""
        where = []
        if keyword:
            where.append(ProblemTag.name.ilike(f"%{keyword}%"))
        total = await self.db.scalar(select(func.count()).select_from(ProblemTag).where(*where)) or 0
        rows = list(
            (
                await self.db.execute(
                    select(ProblemTag)
                    .where(*where)
                    .order_by(ProblemTag.status, ProblemTag.name)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        return rows, total

    async def list_by_names(self, names: list[str]) -> list[ProblemTag]:
        return list(
            (await self.db.execute(select(ProblemTag).where(ProblemTag.name.in_(names)))).scalars()
        )

    async def delete_relations(self, problem_id: uuid.UUID) -> None:
        await self.db.execute(delete(ProblemTagRelation).where(ProblemTagRelation.problem_id == problem_id))

    async def add_relation(self, problem_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        self.db.add(ProblemTagRelation(problem_id=problem_id, tag_id=tag_id))
        await self.db.flush()


class VerificationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_pending(self, problem_id: uuid.UUID) -> ProblemVerification | None:
        return await self.db.scalar(
            select(ProblemVerification).where(
                ProblemVerification.problem_id == problem_id, ProblemVerification.status == VerificationStatus.PENDING
            )
        )

    async def create(self, verification: ProblemVerification) -> ProblemVerification:
        self.db.add(verification)
        await self.db.flush()
        return verification

    async def get_by_id(self, verification_id: uuid.UUID) -> ProblemVerification | None:
        return await self.db.get(ProblemVerification, verification_id)

    async def tag_names(self, problem_id: uuid.UUID) -> list[str]:
        return list(
            (
                await self.db.execute(
                    select(ProblemTag.name)
                    .join(ProblemTagRelation, ProblemTagRelation.tag_id == ProblemTag.id)
                    .where(ProblemTagRelation.problem_id == problem_id)
                    .order_by(ProblemTag.name)
                )
            ).scalars()
        )

    async def tags_for(self, problem_id: uuid.UUID) -> list[ProblemTag]:
        """返回题目标签 ORM 对象列表（id/name/color）。"""
        rows = (
            await self.db.execute(
                select(ProblemTag)
                .join(ProblemTagRelation, ProblemTagRelation.tag_id == ProblemTag.id)
                .where(ProblemTagRelation.problem_id == problem_id)
                .order_by(ProblemTag.name)
            )
        ).scalars()
        return list(rows)

    async def tags_for_problems(self, problem_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[ProblemTag]]:
        """批量返回题目的标签 ORM 对象列表。

        返回 {problem_id: [ProblemTag, ...]}；无标签的题目不在返回字典中。
        """
        if not problem_ids:
            return {}
        rows = (
            await self.db.execute(
                select(ProblemTag, ProblemTagRelation.problem_id)
                .join(ProblemTagRelation, ProblemTagRelation.tag_id == ProblemTag.id)
                .where(ProblemTagRelation.problem_id.in_(problem_ids))
                .order_by(ProblemTag.name)
            )
        ).all()
        result: dict[uuid.UUID, list[ProblemTag]] = {}
        for tag, pid in rows:
            result.setdefault(pid, []).append(tag)
        return result

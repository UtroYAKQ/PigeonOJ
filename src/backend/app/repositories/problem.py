"""题库仓储：Problem / Tag / Verification 数据访问。"""
from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProblemScope, ProblemStatus, ProblemVisibility, TagStatus, VerificationStatus
from app.models.problem import (
    Problem,
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

    async def list_published(self, query: ProblemQuery, viewer_id: uuid.UUID | None, is_manager: bool) -> tuple[list[Problem], int]:
        """题库列表：scope=all 仅 published+public；scope=mine 为创建者/管理角色的管理视图。"""
        conditions = []
        if query.scope == ProblemScope.MINE:
            if not is_manager and viewer_id is not None:
                conditions.append(Problem.owner_id == viewer_id)
            if query.status:
                conditions.append(Problem.status == query.status)
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

    async def list_all(self) -> list[ProblemTag]:
        return list(
            (
                await self.db.execute(
                    select(ProblemTag).order_by(ProblemTag.status, ProblemTag.name)
                )
            ).scalars()
        )

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

"""题单仓储：ProblemSet / ProblemSetItem 数据访问（纯 CRUD，docs/contracts/problem-sets.md）。"""
from __future__ import annotations

import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ProblemSetStatus,
    ProblemSetVisibility,
    ProblemStatus,
    ProblemVisibility,
)
from app.models.problem import Problem
from app.models.problem_set import ProblemSet, ProblemSetItem
from app.schemas.problem_set import ProblemSetSummary


class ProblemSetRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, set_id: uuid.UUID) -> ProblemSet | None:
        return await self.db.get(ProblemSet, set_id)

    async def get_item(self, set_id: uuid.UUID, problem_id: uuid.UUID) -> ProblemSetItem | None:
        """题单内条目（交题前置校验：题目必须属于该题单）。"""
        return await self.db.scalar(
            select(ProblemSetItem).where(
                ProblemSetItem.problem_set_id == set_id,
                ProblemSetItem.problem_id == problem_id,
            )
        )

    async def create(self, problem_set: ProblemSet) -> ProblemSet:
        self.db.add(problem_set)
        await self.db.flush()
        return problem_set

    async def list_public(
        self, *, page: int, page_size: int, keyword: str | None,
        viewer_id: uuid.UUID | None = None, mine: bool = False,
    ) -> tuple[list[ProblemSet], int]:
        """题单中心：仅 visibility=public 且 status=active 的全站题单；
        mine=true（须登录）改为仅本人创建的未下线题单（含私有，题单中心「我的」勾选）。"""
        conditions = [ProblemSet.status == ProblemSetStatus.ACTIVE]
        if mine and viewer_id is not None:
            conditions.append(ProblemSet.owner_id == viewer_id)
        else:
            conditions.append(ProblemSet.visibility == ProblemSetVisibility.PUBLIC)
        if keyword:
            conditions.append(ProblemSet.title.ilike(f"%{keyword}%"))
        total = (
            await self.db.scalar(select(func.count()).select_from(ProblemSet).where(*conditions))
        ) or 0
        rows = list(
            (
                await self.db.execute(
                    select(ProblemSet)
                    .where(*conditions)
                    .order_by(ProblemSet.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        return rows, int(total)

    async def list_all(
        self, *, page: int, page_size: int, keyword: str | None, status: str | None,
        owner_id: uuid.UUID | None = None,
    ) -> tuple[list[ProblemSet], int]:
        """管理视图题单：含私有与已下线；owner_id 非 None 时仅该创建者（单一所有权模型）。"""
        conditions = []
        if owner_id is not None:
            conditions.append(ProblemSet.owner_id == owner_id)
        if keyword:
            conditions.append(ProblemSet.title.ilike(f"%{keyword}%"))
        if status is not None:
            conditions.append(ProblemSet.status == status)
        total = (
            await self.db.scalar(select(func.count()).select_from(ProblemSet).where(*conditions))
        ) or 0
        rows = list(
            (
                await self.db.execute(
                    select(ProblemSet)
                    .where(*conditions)
                    .order_by(ProblemSet.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        return rows, int(total)

    async def count_items(self, set_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """题单内题目数（列表页展示用；无条目的题单不计入返回）。"""
        if not set_ids:
            return {}
        rows = await self.db.execute(
            select(ProblemSetItem.problem_set_id, func.count())
            .where(ProblemSetItem.problem_set_id.in_(set_ids))
            .group_by(ProblemSetItem.problem_set_id)
        )
        return {sid: int(count) for sid, count in rows.all()}

    async def list_items_with_problem(self, set_id: uuid.UUID) -> list[tuple[ProblemSetItem, Problem]]:
        """题单内条目（带题目元信息），按 sort_order、加入时间排序。"""
        rows = await self.db.execute(
            select(ProblemSetItem, Problem)
            .join(Problem, Problem.id == ProblemSetItem.problem_id)
            .where(ProblemSetItem.problem_set_id == set_id)
            .order_by(ProblemSetItem.sort_order, ProblemSetItem.created_at)
        )
        return [(item, problem) for item, problem in rows.all()]

    async def replace_items(
        self, set_id: uuid.UUID, items: list[ProblemSetItem], added_by: uuid.UUID
    ) -> None:
        """全量替换题单内题目列表（单事务：先删后插）。"""
        await self.db.execute(delete(ProblemSetItem).where(ProblemSetItem.problem_set_id == set_id))
        for item in items:
            item.added_by = added_by
        self.db.add_all(items)
        await self.db.flush()

    async def list_accessible_problems(
        self,
        problem_ids: list[uuid.UUID],
        viewer_id: uuid.UUID | None = None,
        see_all: bool = False,
    ) -> list[Problem]:
        """按 id 批量取可加入题单的题目（编排候选校验）。

        规则：须为已发布，且（全站公开 或 创建者本人的私有题）；admin 不受可见性限制。
        未发布（草稿）/ 已归档的题目一律不可加入。
        """
        if not problem_ids:
            return []
        conditions: list = [
            Problem.id.in_(problem_ids),
            Problem.status == ProblemStatus.PUBLISHED,
        ]
        if not see_all:
            if viewer_id is None:
                return []
            conditions.append(
                or_(
                    Problem.visibility == ProblemVisibility.PUBLIC,
                    Problem.owner_id == viewer_id,
                )
            )
        return list(
            (await self.db.execute(select(Problem).where(*conditions))).scalars()
        )


def to_summary(problem_set: ProblemSet, item_count: int) -> ProblemSetSummary:
    """ORM 行 → 列表契约模型（item_count 由仓储聚合注入）。"""
    return ProblemSetSummary(
        id=problem_set.id,
        title=problem_set.title,
        description=problem_set.description,
        visibility=problem_set.visibility,
        status=problem_set.status,
        owner_id=problem_set.owner_id,
        item_count=item_count,
        created_at=problem_set.created_at,
        updated_at=problem_set.updated_at,
    )

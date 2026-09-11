"""题库仓储：Problem / Tag / Verification 数据访问。"""
from __future__ import annotations

import uuid

from sqlalchemy import delete, false, func, or_, select
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

    async def get_team_source(
        self, team_id: uuid.UUID, source_problem_id: uuid.UUID
    ) -> Problem | None:
        """团队题库内是否已存在某源题的引用快照（引用防重）。"""
        stmt = select(Problem).where(
            Problem.team_id == team_id,
            Problem.source_problem_id == source_problem_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create(self, problem: Problem) -> Problem:
        self.db.add(problem)
        await self.db.flush()
        return problem

    async def copy_test_cases(self, source: Problem, target: Problem) -> None:
        """快照复制生效测试点（引用题继承判题数据；docs/contracts/teams.md 团队空间节）。

        - 仅复制 source.active_case_ids 引用的行（暂存集不复制）
        - MinIO 对象逐份复制（新 oss id），源 / 目标对象互不影响，可独立清理
        - 判题读取按 problems.active_case_ids 指向新行 id
        """
        from app.core.storage import get_storage

        if not source.active_case_ids:
            return
        rows = list(
            (
                await self.db.execute(
                    select(TestCase).where(
                        TestCase.problem_id == source.id,
                        TestCase.id.in_(source.active_case_ids),
                    )
                )
            ).scalars()
        )
        by_id = {row.id: row for row in rows}
        storage = get_storage()
        new_ids: list[uuid.UUID] = []
        for case_id in source.active_case_ids:
            row = by_id.get(case_id)
            if row is None:  # 生效集指向缺失行（异常数据）：跳过保持集合完整
                continue
            input_oss_id, expected_oss_id = await storage.copy_object(
                row.input_oss_id
            ), await storage.copy_object(row.expected_output_oss_id)
            copy = TestCase(
                problem_id=target.id,
                name=row.name,
                input_oss_id=input_oss_id,
                expected_output_oss_id=expected_oss_id,
                origin_id=row.id,  # 指回源题行（版本化语义：复制来源）
                sort_order=row.sort_order,
            )
            self.db.add(copy)
            await self.db.flush()
            new_ids.append(copy.id)
        target.active_case_ids = new_ids
        target.cases_revision = 0  # 新题生效集即基线，暂存集为空
        await self.db.flush()

    async def copy_tag_relations(self, source: Problem, target: Problem) -> None:
        """复制题目-标签关联（引用快照继承分类，docs/contracts/teams.md 团队空间节）。"""
        rows = list(
            (
                await self.db.execute(
                    select(ProblemTagRelation).where(ProblemTagRelation.problem_id == source.id)
                )
            ).scalars()
        )
        for row in rows:
            self.db.add(ProblemTagRelation(problem_id=target.id, tag_id=row.tag_id))
        await self.db.flush()

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
        """批量取重验判定所需字段（id / verified_at / samples_updated_at / pending_case_ids / pending_spj_oss_id）。"""
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
                        Problem.pending_spj_oss_id,
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
            # 来源过滤（题目管理页）：solo=全站题 / team=团队题（引用快照 + 直建）
            if query.ownership == "solo":
                conditions.append(Problem.team_id.is_(None))
            elif query.ownership == "team":
                conditions.append(Problem.team_id.is_not(None))
        elif query.mine and viewer_id is not None:
            # 题库中心「我的」勾选：仅本人已发布的**全站题**（任意可见性，含私有已发布；
            # 团队题目属封闭空间，即使是自己引用 / 直建的快照也不进题库中心）
            conditions.extend([
                Problem.owner_id == viewer_id,
                Problem.status == ProblemStatus.PUBLISHED,
                Problem.team_id.is_(None),
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

    async def list_team_problems(
        self,
        team_id: uuid.UUID,
        *,
        viewer_id: uuid.UUID,
        is_team_manager: bool,
        keyword: str | None = None,
        status: str | None = None,
        visibility: str | None = None,
        page: int = 1,
        page_size: int = 20,
        admin_view: bool = False,
    ) -> tuple[list[Problem], int]:
        """团队题库列表（docs/contracts/teams.md 团队空间节）。

        - 成员视图：published 且 team_visible（admin_visible 仅团队管理可见）
        - 团队管理视图（创建者 / 管理员）：主列表仅已发布（草稿收敛到 status='draft'
          草稿箱视图，仍仅本人草稿、他人草稿不可见）；归档在团队空间不返回
          （下线即从团队消失）；status 显式传入时按值过滤
        - admin 管理视图（admin_view=True）：全部状态 / 可见性（含草稿与归档）
        """
        conditions: list = [Problem.team_id == team_id]
        if admin_view:
            if status:
                conditions.append(Problem.status == status)
            if visibility:
                conditions.append(Problem.visibility == visibility)
        elif is_team_manager:
            if status == ProblemStatus.DRAFT:
                # 草稿箱视图：仅本人草稿（草稿仅创建者本人可见，docs/contracts/problems.md）
                conditions.append(Problem.status == ProblemStatus.DRAFT)
                conditions.append(Problem.owner_id == viewer_id)
            elif status == ProblemStatus.ARCHIVED:
                # 团队空间归档即不可见（管理后台 admin_view 仍可查）：恒返回空
                conditions.append(false())
            elif status:
                conditions.append(Problem.status == status)
            else:
                conditions.append(Problem.status == ProblemStatus.PUBLISHED)
            if visibility:
                conditions.append(Problem.visibility == visibility)
        else:
            conditions.append(Problem.status == ProblemStatus.PUBLISHED)
            conditions.append(Problem.visibility == ProblemVisibility.TEAM_VISIBLE)
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

    async def list_team_arrangeable(
        self,
        team_id: uuid.UUID,
        viewer_id: uuid.UUID,
        problem_ids: list[uuid.UUID],
    ) -> list[Problem]:
        """团队上下文编排候选校验（团队题单 / 团队比赛共用规则）：

        已发布且（全站公开 或 本人私有 或 本团队题目）；团队管理动作专用。
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
                            Problem.owner_id == viewer_id,
                            Problem.team_id == team_id,
                        ),
                    )
                )
            ).scalars()
        )

    async def list_team_arrangeable_search(
        self,
        team_id: uuid.UUID,
        viewer_id: uuid.UUID,
        *,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Problem], int]:
        """团队编排候选搜索（列表）：已发布且（本团队题目 ∪ 全站公开 ∪ 本人私有），标题模糊。"""
        conditions: list = [
            Problem.status == ProblemStatus.PUBLISHED,
            or_(
                Problem.team_id == team_id,
                Problem.visibility == ProblemVisibility.PUBLIC,
                Problem.owner_id == viewer_id,
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

    async def add_test_cases(self, cases: list[TestCase]) -> None:
        self.db.add_all(cases)
        await self.db.flush()

    async def list_referenceable(
        self,
        team_id: uuid.UUID,
        owner_id: uuid.UUID,
        *,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Problem], int]:
        """团队题目引用候选（引用页列表）：本人创建 + 已发布 + 全站题（team_id IS NULL）
        + 未被该团队引用过（同团队同源仅一份快照，docs/contracts/teams.md 团队空间节）。"""
        conditions: list = [
            Problem.owner_id == owner_id,
            Problem.status == ProblemStatus.PUBLISHED,
            Problem.team_id.is_(None),
            Problem.source_problem_id.is_(None),
            Problem.id.not_in(
                select(Problem.source_problem_id).where(
                    Problem.team_id == team_id,
                    Problem.source_problem_id.is_not(None),
                )
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

"""团队空间服务：团队题库 / 团队题单 / 团队比赛（docs/contracts/teams.md 团队空间节）。

限界上下文：团队空间对题目 / 题单 / 比赛的创建与编排经本模块独立端点完成
（/teams/{team_id}/...），与公开上下文（题库中心 / 题单中心 / 比赛中心）互相隔离；
跨上下文协作经显式端口（ProblemService / ContestService / SubmissionService
装配进本服务），不直读对方聚合。

可见性模型：
- 团队题目：题库裸路径（GET /problems/{id} 等）严格按可见性门控，成员只能经
  团队上下文端点（详情 / 交题 / 自测）访问——上下文隔离；
- 团队题单 / 团队比赛：详情浏览复用题单 / 比赛模块统一端点（对团队成员放行，
  对非成员 2003），创建与编排收敛在团队空间端点。

引用语义（referenced_at 非空标记引用来源）：
- 团队题目：引用导师本人创建的全站题目（private）进团队，team_id 归属切换 +
  可见性转团队分支（单向，不设移出 / 升级公开通道，docs/contracts/problems.md）；
- 团队题单：引用本人创建的全站题单进团队（visibility='team'，单向）；
- 团队比赛：团队空间直接创建（contest_type='team'），无引用语义。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependency import is_admin
from app.core.exceptions import (
    APIError,
    AUTH_FORBIDDEN,
    PARAM_FORMAT_INVALID,
    RESOURCE_DUPLICATE,
    RESOURCE_NOT_FOUND,
    RESOURCE_STATE_CONFLICT,
)
from app.enums import (
    ProblemSetStatus,
    ProblemSetVisibility,
    ProblemStatus,
    ProblemVisibility,
)
from app.models.problem import Problem
from app.models.problem_set import ProblemSet, ProblemSetItem
from app.models.user import User
from app.repositories.problem import ProblemRepository
from app.repositories.problem_set import ProblemSetRepository, to_summary as set_to_summary
from app.schemas.contest import ContestSummary
from app.schemas.judge import SubmissionCreate
from app.schemas.problem import ProblemDetail, ProblemUpdate, TeamProblemSummary
from app.schemas.problem_set import ProblemSetSummary
from app.schemas.team import (
    TeamContestCreate,
    TeamProblemReferenceCreate,
    TeamProblemSetCreate,
)
from app.services.contest import ContestService
from app.services.judge import SubmissionService
from app.services.problem import ProblemService, to_problem_detail
from app.services.problem_set import ProblemSetService
from app.services.team import TeamService


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TeamSpaceService:
    """团队空间门面（Facade）：团队上下文内题目 / 题单 / 比赛的统一入口。"""

    def __init__(
        self,
        db: AsyncSession,
        teams: TeamService,
        problems: ProblemService,
        contests: ContestService,
        submissions: SubmissionService,
    ) -> None:
        self.db = db
        self.teams = teams
        self.problems = problems
        self.contests = contests
        self.submissions = submissions
        self.problem_repo = ProblemRepository(db)
        self.set_repo = ProblemSetRepository(db)
        self.set_service = ProblemSetService(db)

    # ---------------- 团队角色辅助 ----------------

    async def require_member(self, user: User, team_id: uuid.UUID) -> None:
        """团队上下文访问门：非团队成员一律 2003（团队资源不对公开上下文泄漏）。"""
        await self.teams._require_team_roles(user, team_id, level="member")

    async def require_manager(self, user: User, team_id: uuid.UUID) -> None:
        """团队空间管理动作门（引用 / 建题单 / 建比赛 / 编排）：team_creator / team_admin。"""
        await self.teams._require_team_roles(user, team_id, level="admin")

    async def _is_team_manager(self, user: User, team_id: uuid.UUID) -> bool:
        return await self.teams.has_team_roles(user, team_id, level="admin")

    # ---------------- 团队题库 ----------------

    async def list_problems(
        self,
        user: User,
        team_id: uuid.UUID,
        *,
        keyword: str | None,
        status: str | None,
        visibility: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[TeamProblemSummary], int]:
        """团队题库列表：成员仅见 published + team_visible；团队管理主列表仅见已发布
        （草稿经 status='draft' 进入草稿箱视图，仍仅本人草稿、他人草稿不可见），
        并回填 needs_reverification 供发布与验题状态展示。"""
        await self.require_member(user, team_id)
        is_manager = await self._is_team_manager(user, team_id)
        rows, total = await self.problem_repo.list_team_problems(
            team_id,
            viewer_id=user.id,
            is_team_manager=is_manager,
            keyword=keyword,
            status=status,
            visibility=visibility,
            page=page,
            page_size=page_size,
        )
        items = [TeamProblemSummary.model_validate(row) for row in rows]
        if is_manager:
            flags = await self.problems.verification_flags([row.id for row in rows])
            for item in items:
                item.needs_reverification = flags.get(item.id, False)
        await self.problems.attach_counters(items)
        await self.problems.attach_tags(items)
        await self.problems.attach_solve_status(items, user)
        return items, total

    async def reference_problem(
        self, user: User, team_id: uuid.UUID, body: TeamProblemReferenceCreate
    ) -> TeamProblemSummary:
        """引用本人全站题目进入团队题库（team_creator / team_admin）。

        引用 = 快照复制新题（非归属切换，docs/contracts/teams.md 团队空间节）：
        - 题目须为本人创建的已发布全站题目（team_id IS NULL；admin 全站同权）
        - 新题继承题面 / 样例 / 生效测试点（MinIO 对象复制）/ 验题与发布状态，
          归属团队、可见性落团队分支、referenced_at = 引用时间
        - 统计数据（problem_counters / submissions）从零开始 → 团队通过率为纯团队口径；
          源题留在个人题库，复制后两题独立演进（源题改动不跟随）
        """
        await self.require_manager(user, team_id)
        source = await self.problem_repo.get_by_id(body.problem_id)
        if source is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
        if source.team_id is not None:
            raise APIError(PARAM_FORMAT_INVALID, "团队题目不可被引用", 400)
        if source.status != ProblemStatus.PUBLISHED:
            raise APIError(RESOURCE_STATE_CONFLICT, "仅可引用已发布题目", 409)
        if not (await is_admin(self.db, user) or source.owner_id == user.id):
            raise APIError(AUTH_FORBIDDEN, "仅可引用本人创建的题目", 403)
        # 同团队同源题仅一份快照（防重，uq_problems_team_source 兜底）
        if await self.problem_repo.get_team_source(team_id, source.id):
            raise APIError(RESOURCE_DUPLICATE, "该题目已引用进团队", 409)

        problem = Problem(
            title=source.title,
            background=source.background,
            description=source.description,
            input_description=source.input_description,
            output_description=source.output_description,
            note=source.note,
            solution=source.solution,
            samples=source.samples,
            samples_updated_at=source.samples_updated_at,
            # 快照继承生效测试点集合（暂存集不复制：新题在团队内独立暂存 / 验题）
            active_case_ids=source.active_case_ids,
            pending_case_ids=None,
            case_status=source.case_status,
            cases_revision=source.cases_revision,
            pending_verified=False,
            time_limit_ms=source.time_limit_ms,
            memory_limit_mb=source.memory_limit_mb,
            difficulty=source.difficulty,
            visibility=body.visibility,
            team_id=team_id,
            status=source.status,
            # 验题事实继承：快照题面与源题发布版一致，无需重新验题
            verified_by=source.verified_by,
            verified_at=source.verified_at,
            published_at=source.published_at,
            referenced_at=_now(),
            source_problem_id=source.id,
            owner_id=user.id,
        )
        problem = await self.problem_repo.create(problem)
        await self.problem_repo.copy_test_cases(source, problem)
        await self.problem_repo.copy_tag_relations(source, problem)
        item = TeamProblemSummary.model_validate(problem)
        await self.problems.attach_counters([item])
        await self.problems.attach_tags([item])
        return item

    async def _team_problem_or_404(
        self, team_id: uuid.UUID, problem_id: uuid.UUID
    ) -> Problem:
        problem = await self.problem_repo.get_by_id(problem_id)
        if problem is None or problem.team_id != team_id:
            raise APIError(RESOURCE_NOT_FOUND, "题目不在该团队题库中", 404)
        return problem

    async def get_problem_detail(
        self, user: User, team_id: uuid.UUID, problem_id: uuid.UUID
    ) -> ProblemDetail:
        """团队题库内题目详情（统一入口）：团队可见 + 题目属于该团队校验后
        复用题库详情装配；团队题目在题库裸路径不可见（上下文隔离）。"""
        await self.require_member(user, team_id)
        problem = await self._team_problem_or_404(team_id, problem_id)
        if problem.status != ProblemStatus.PUBLISHED:
            # 草稿 / 归档仅题目创建者（或 admin）可经团队空间查看
            if not (await is_admin(self.db, user) or problem.owner_id == user.id):
                raise APIError(AUTH_FORBIDDEN, "题目未发布", 403)
        elif (
            problem.visibility == ProblemVisibility.ADMIN_VISIBLE
            and not await self._is_team_manager(user, team_id)
        ):
            raise APIError(AUTH_FORBIDDEN, "无权限查看该题目", 403)
        return to_problem_detail(
            await self.problems.get_detail(problem_id, user, bypass_visibility=True)
        )

    async def create_problem_submission(
        self,
        user: User,
        team_id: uuid.UUID,
        problem_id: uuid.UUID,
        *,
        language: str,
        code: str,
    ) -> object:
        """团队题库内交题（统一入口）：可见性校验后走统一判题链路
        （submit_type='practice'；派发由路由层 commit 后执行）。"""
        await self.require_member(user, team_id)
        problem = await self._team_problem_or_404(team_id, problem_id)
        if problem.status != ProblemStatus.PUBLISHED:
            raise APIError(AUTH_FORBIDDEN, "题目未发布，不可提交", 403)
        if (
            problem.visibility == ProblemVisibility.ADMIN_VISIBLE
            and not await self._is_team_manager(user, team_id)
        ):
            raise APIError(AUTH_FORBIDDEN, "无权限提交该题目", 403)
        return await self.submissions.create(
            user,
            SubmissionCreate(problem_id=problem_id, language=language, code=code),
            bypass_visibility=True,  # 团队题目豁免题库可见性：团队门控（成员 + 归属）已通过
        )

    async def update_team_problem_statement(
        self,
        user: User,
        team_id: uuid.UUID,
        problem_id: uuid.UUID,
        body: ProblemUpdate,
    ) -> TeamProblemSummary:
        """团队上下文编辑题面（编辑向导第一步）：团队门（成员）+ 归属校验后
        复用题库 update（_require_manage 再校验 owner/admin；快照题豁免裸路径拦截）。"""
        await self.require_member(user, team_id)
        problem = await self._team_problem_or_404(team_id, problem_id)
        # 可见性切换收敛到独立编辑动线（ProblemStatementView 下拉），题面更新不携带
        updated = await self.problems.update(user, problem.id, body)
        item = TeamProblemSummary.model_validate(updated)
        await self.problems.attach_counters([item])
        await self.problems.attach_tags([item])
        return item

    # ---------------- 团队题单 ----------------

    async def list_problem_sets(
        self,
        user: User,
        team_id: uuid.UUID,
        *,
        keyword: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ProblemSetSummary], int]:
        """团队题单列表：默认仅未下线（status 显式传入时按值过滤，团队管理视图）。"""
        await self.require_member(user, team_id)
        rows, total = await self.set_repo.list_team(
            team_id, keyword=keyword, status=status, page=page, page_size=page_size
        )
        counts = await self.set_repo.count_items([row.id for row in rows])
        return [set_to_summary(row, counts.get(row.id, 0)) for row in rows], total

    async def create_problem_set(
        self, user: User, team_id: uuid.UUID, body: TeamProblemSetCreate
    ) -> ProblemSetSummary:
        """创建团队题单（team_creator / team_admin；visibility='team'，仅团队空间可见）。

        copy_items_from 非空 = 复制本人全站题单的题目条目（快照复制语义，与题目引用一致）：
        - 源题单须存在、未下线、为全站题单（team_id IS NULL）且为本人创建（admin 同权）
        - 复制条目（problem_id / sort_order），源题单本身保留在全站，两题单独立演进
        """
        await self.require_manager(user, team_id)
        problem_set = await self.set_repo.create(
            ProblemSet(
                title=body.title.strip(),
                description=body.description,
                owner_id=user.id,
                team_id=team_id,
                visibility=ProblemSetVisibility.TEAM,
                status=ProblemSetStatus.ACTIVE,
                # 复制来源标记（referenced_at 语义随复制语义沿用：非空 = 复制自本人全站题单）
                referenced_at=_now() if body.copy_items_from is not None else None,
            )
        )
        item_count = 0
        if body.copy_items_from is not None:
            source = await self.set_repo.get_by_id(body.copy_items_from)
            if source is None:
                raise APIError(RESOURCE_NOT_FOUND, "源题单不存在", 404)
            if source.team_id is not None:
                raise APIError(PARAM_FORMAT_INVALID, "团队题单不可作为复制来源", 400)
            if source.status != ProblemSetStatus.ACTIVE:
                raise APIError(RESOURCE_STATE_CONFLICT, "已下线题单不可复制", 409)
            if not (await is_admin(self.db, user) or source.owner_id == user.id):
                raise APIError(AUTH_FORBIDDEN, "仅可复制本人创建的题单", 403)
            source_rows = await self.set_repo.list_items_with_problem(source.id)
            await self.set_repo.replace_items(
                problem_set.id,
                [
                    ProblemSetItem(
                        problem_set_id=problem_set.id,
                        problem_id=problem.id,
                        sort_order=item.sort_order,
                        added_by=user.id,
                    )
                    for item, problem in source_rows
                ],
                user.id,
            )
            item_count = len(source_rows)
        return set_to_summary(problem_set, item_count)

    async def _team_set_or_404(self, team_id: uuid.UUID, set_id: uuid.UUID) -> ProblemSet:
        problem_set = await self.set_repo.get_by_id(set_id)
        if problem_set is None or problem_set.team_id != team_id:
            raise APIError(RESOURCE_NOT_FOUND, "题单不在该团队中", 404)
        return problem_set

    async def get_set_detail(self, user: User, team_id: uuid.UUID, set_id: uuid.UUID) -> object:
        """团队题单详情（团队上下文统一入口）：成员门 + 归属校验后复用题单详情装配
        （条目按 sort_order、作答状态、owner_name）；不再走 /problem-sets/{id} 统一端点。"""
        await self.require_member(user, team_id)
        problem_set = await self._team_set_or_404(team_id, set_id)
        return await self.set_service.get_detail_for_team(problem_set, user)

    async def get_set_problem_detail(
        self, user: User, team_id: uuid.UUID, set_id: uuid.UUID, problem_id: uuid.UUID
    ) -> ProblemDetail:
        """团队题单内题目详情（团队上下文统一入口）：成员门 + 归属校验
        （题目属于该题单）后复用题库详情装配（私有题豁免同题单统一端点口径）。"""
        await self.require_member(user, team_id)
        problem_set = await self._team_set_or_404(team_id, set_id)
        if await self.set_repo.get_item(problem_set.id, problem_id) is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不在该题单中", 404)
        detail = await self.problems.get_detail(problem_id, user, bypass_visibility=True)
        return to_problem_detail(detail)

    async def create_set_submission(
        self,
        user: User,
        team_id: uuid.UUID,
        set_id: uuid.UUID,
        problem_id: uuid.UUID,
        *,
        language: str,
        code: str,
    ) -> object:
        """团队题单内交题（团队上下文统一入口）：门控同上，走统一判题链路
        （submit_type='practice'；派发由路由层 commit 后执行）。"""
        await self.require_member(user, team_id)
        problem_set = await self._team_set_or_404(team_id, set_id)
        if await self.set_repo.get_item(problem_set.id, problem_id) is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不在该题单中", 404)
        problem = await self.problem_repo.get_by_id(problem_id)
        if problem is None or problem.status != ProblemStatus.PUBLISHED:
            raise APIError(AUTH_FORBIDDEN, "题目未发布，不可提交", 403)
        return await self.submissions.create(
            user,
            SubmissionCreate(problem_id=problem_id, language=language, code=code),
            bypass_visibility=True,  # 团队门控（成员 + 归属）已通过，豁免题库可见性
        )

    async def list_arrangeable_problems(
        self,
        user: User,
        team_id: uuid.UUID,
        *,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[TeamProblemSummary], int]:
        """团队编排候选搜索（团队题单编排挑题用）：已发布且
        （本团队题目 ∪ 全站公开 ∪ 本人私有），标题模糊；仅团队管理可调。"""
        await self.require_manager(user, team_id)
        rows, total = await self.problem_repo.list_team_arrangeable_search(
            team_id, user.id, keyword=keyword, page=page, page_size=page_size
        )
        return [TeamProblemSummary.model_validate(row) for row in rows], total

    async def list_referenceable_problems(
        self,
        user: User,
        team_id: uuid.UUID,
        *,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[TeamProblemSummary], int]:
        """团队题目引用候选搜索（引用页列表用）：本人创建 + 已发布 + 全站题 +
        未被该团队引用过（同团队同源仅一份快照）；仅团队管理可调。"""
        await self.require_manager(user, team_id)
        rows, total = await self.problem_repo.list_referenceable(
            team_id, user.id, keyword=keyword, page=page, page_size=page_size
        )
        items = [TeamProblemSummary.model_validate(row) for row in rows]
        await self.problems.attach_counters(items)
        await self.problems.attach_tags(items)
        return items, total

    async def replace_set_items(
        self, user: User, team_id: uuid.UUID, set_id: uuid.UUID, items: list
    ) -> None:
        """编排团队题单题目（team_creator / team_admin）：候选 = 已发布且
        （本团队题目 ∪ 全站公开 ∪ 本人私有）；同一题单内不得重复。"""
        await self.require_manager(user, team_id)
        problem_set = await self._team_set_or_404(team_id, set_id)
        seen: set[uuid.UUID] = set()
        for item in items:
            if item.problem_id in seen:
                raise APIError(RESOURCE_DUPLICATE, "题目在题单中重复", 409)
            seen.add(item.problem_id)
        found = {
            problem.id: problem
            for problem in await self.problem_repo.list_team_arrangeable(
                team_id, user.id, list(seen)
            )
        }
        missing = seen - set(found)
        if missing:
            raise APIError(PARAM_FORMAT_INVALID, "题目未发布或不可见，不可加入题单", 400)
        rows = [
            ProblemSetItem(
                problem_set_id=problem_set.id,
                problem_id=item.problem_id,
                sort_order=item.sort_order,
                added_by=user.id,
            )
            for item in items
        ]
        await self.set_repo.replace_items(problem_set.id, rows, user.id)

    async def archive_problem_set(
        self, user: User, team_id: uuid.UUID, set_id: uuid.UUID
    ) -> ProblemSetSummary:
        """下线团队题单（team_creator / team_admin；不做物理删除）。"""
        await self.require_manager(user, team_id)
        problem_set = await self._team_set_or_404(team_id, set_id)
        problem_set.status = ProblemSetStatus.ARCHIVED
        problem_set.updated_at = _now()
        await self.db.flush()
        counts = await self.set_repo.count_items([problem_set.id])
        return set_to_summary(problem_set, counts.get(problem_set.id, 0))

    # ---------------- 团队比赛 ----------------

    async def list_contests(
        self,
        user: User,
        team_id: uuid.UUID,
        *,
        keyword: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ContestSummary], int]:
        """团队比赛列表：本团队全部状态比赛（成员可见；报名 / 看题窗口随比赛端点校验）。"""
        await self.require_member(user, team_id)
        return await self.contests.list_team_contests(
            team_id, page=page, page_size=page_size, status=status, keyword=keyword
        )

    async def create_contest(
        self, user: User, team_id: uuid.UUID, body: TeamContestCreate
    ) -> ContestSummary:
        """创建团队比赛（team_creator / team_admin；contest_type='team'）。

        编排候选在公开比赛规则（已发布公开 / 本人私有）之上放开本团队题目；
        报名 / 看题 / 交题窗口复用比赛统一端点（团队比赛报名叠加团队成员校验）。
        """
        await self.require_manager(user, team_id)
        return await self.contests.create_team_contest(user, team_id, body)

    # ---------------- 管理端只读视图（admin，免团队成员校验；docs/contracts/teams.md 管理端） ----------------

    async def count_team_resources(
        self, team_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, dict[str, int]]:
        """批量统计各团队空间资源数（管理端列表 / 详情展示用）：
        题库 / 题单 / 比赛均为全部状态（与详情 tab 分页 total 口径一致）。"""
        from sqlalchemy import func, select

        from app.models.contest import Contest
        from app.enums import ContestType

        if not team_ids:
            return {}
        result: dict[uuid.UUID, dict[str, int]] = {
            team_id: {"problems": 0, "sets": 0, "contests": 0} for team_id in team_ids
        }
        problem_rows = (
            await self.db.execute(
                select(Problem.team_id, func.count())
                .where(Problem.team_id.in_(team_ids))
                .group_by(Problem.team_id)
            )
        ).all()
        for team_id, count in problem_rows:
            result[team_id]["problems"] = int(count)
        set_rows = (
            await self.db.execute(
                select(ProblemSet.team_id, func.count())
                .where(ProblemSet.team_id.in_(team_ids))
                .group_by(ProblemSet.team_id)
            )
        ).all()
        for team_id, count in set_rows:
            result[team_id]["sets"] = int(count)
        contest_rows = (
            await self.db.execute(
                select(Contest.team_id, func.count())
                .where(
                    Contest.team_id.in_(team_ids),
                    Contest.contest_type == ContestType.TEAM,
                )
                .group_by(Contest.team_id)
            )
        ).all()
        for team_id, count in contest_rows:
            result[team_id]["contests"] = int(count)
        return result

    async def admin_list_problems(
        self,
        team_id: uuid.UUID,
        *,
        keyword: str | None,
        status: str | None,
        visibility: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[TeamProblemSummary], int]:
        """团队题库列表（admin 管理视图）：全部状态 / 可见性（含草稿与归档）；
        作答状态为个人视角，管理端不装配。"""
        rows, total = await self.problem_repo.list_team_problems(
            team_id,
            viewer_id=None,
            is_team_manager=False,
            admin_view=True,
            keyword=keyword,
            status=status,
            visibility=visibility,
            page=page,
            page_size=page_size,
        )
        items = [TeamProblemSummary.model_validate(row) for row in rows]
        await self.problems.attach_counters(items)
        await self.problems.attach_tags(items)
        return items, total

    async def admin_list_problem_sets(
        self,
        team_id: uuid.UUID,
        *,
        keyword: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ProblemSetSummary], int]:
        """团队题单列表（admin 管理视图）：含已下线（status 显式传入时按值过滤）。"""
        rows, total = await self.set_repo.list_team(
            team_id, keyword=keyword, status=status, page=page, page_size=page_size, admin_view=True
        )
        counts = await self.set_repo.count_items([row.id for row in rows])
        return [set_to_summary(row, counts.get(row.id, 0)) for row in rows], total

    async def admin_list_contests(
        self,
        team_id: uuid.UUID,
        *,
        keyword: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ContestSummary], int]:
        """团队比赛列表（admin 管理视图）：本团队全部状态比赛。"""
        return await self.contests.list_team_contests(
            team_id, page=page, page_size=page_size, status=status, keyword=keyword
        )

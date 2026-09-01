"""题单域服务：创建 / 编辑 / 编排题目 / 下线与可见性控制（docs/contracts/problem-sets.md）。"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependency import get_user_role_codes
from app.core.exceptions import APIError, AUTH_FORBIDDEN, PARAM_FORMAT_INVALID, RESOURCE_DUPLICATE, RESOURCE_NOT_FOUND
from app.enums import ProblemSetStatus, ProblemSetVisibility
from app.models.problem_set import ProblemSet, ProblemSetItem
from app.models.user import User
from app.repositories.problem_set import ProblemSetRepository, to_summary
from app.schemas.problem import ProblemDetail
from app.schemas.problem_set import (
    ProblemSetCreate,
    ProblemSetDetail,
    ProblemSetItemsUpdate,
    ProblemSetItemOut,
    ProblemSetSummary,
    ProblemSetUpdate,
)
from app.services.problem import ProblemService, to_problem_detail

# 全站题单管理角色（docs/contracts/problem-sets.md：公开题单由 admin/tutor 创建）
SET_MANAGER_ROLES: set[str] = {"admin", "tutor"}


class ProblemSetService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ProblemSetRepository(db)

    async def _can_manage(self, user: User | None, problem_set: ProblemSet) -> bool:
        """管理权限：admin/tutor 管理全站题单；团队题单权限随 teams 模块接入。"""
        if user is None:
            return False
        codes = await get_user_role_codes(self.db, user.id)
        return bool(SET_MANAGER_ROLES.intersection(codes))

    async def _get_visible(self, set_id: uuid.UUID, viewer: User | None) -> ProblemSet:
        """按可见性取题单：不存在 → 3001；私有 / 已下线对无权限者 → 2003。"""
        problem_set = await self.repo.get_by_id(set_id)
        if problem_set is None:
            raise APIError(RESOURCE_NOT_FOUND, "题单不存在", 404)
        can_manage = await self._can_manage(viewer, problem_set)
        is_owner = viewer is not None and viewer.id == problem_set.owner_id
        visible = problem_set.status == ProblemSetStatus.ACTIVE and (
            problem_set.visibility == ProblemSetVisibility.PUBLIC or is_owner or can_manage
        )
        if not visible:
            if can_manage or is_owner:
                return problem_set  # 管理角色 / 创建者可见已下线题单
            raise APIError(AUTH_FORBIDDEN, "无权限：题单不可见", 403)
        return problem_set

    async def require_manage(self, set_id: uuid.UUID, user: User) -> ProblemSet:
        """取题单并断言管理权限（编辑 / 编排 / 下线共用）。"""
        problem_set = await self.repo.get_by_id(set_id)
        if problem_set is None:
            raise APIError(RESOURCE_NOT_FOUND, "题单不存在", 404)
        if not await self._can_manage(user, problem_set):
            raise APIError(AUTH_FORBIDDEN, "无权限管理该题单", 403)
        return problem_set

    async def require_manager(self, user: User) -> None:
        """断言当前用户为题单管理角色（admin/tutor；管理后台列表入口用）。"""
        if not await self._can_manage(user, None):
            raise APIError(AUTH_FORBIDDEN, "无权限：需要管理角色", 403)

    async def ensure_set_problem(
        self, set_id: uuid.UUID, problem_id: uuid.UUID, viewer: User | None
    ) -> ProblemSet:
        """题单上下文资源访问前置校验（docs/contracts/problem-sets.md 统一入口）：

        题单必须可见（私有 / 已下线按可见性拦截），题目必须属于该题单（否则 3001）。
        """
        problem_set = await self._get_visible(set_id, viewer)
        if await self.repo.get_item(problem_set.id, problem_id) is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不在该题单中", 404)
        return problem_set

    async def get_problem_detail(
        self, set_id: uuid.UUID, problem_id: uuid.UUID, viewer: User | None
    ) -> ProblemDetail:
        """题单内题目详情（统一入口）：归属校验通过后复用题库详情装配，
        结构与可见性门控与 GET /problems/{id} 完全一致（docs/contracts/problem-sets.md）。"""
        await self.ensure_set_problem(set_id, problem_id, viewer)
        detail = await ProblemService(self.db).get_detail(problem_id, viewer)
        return to_problem_detail(detail)

    # ---------------- 查询 ----------------

    async def list_center(
        self, *, page: int, page_size: int, keyword: str | None
    ) -> tuple[list[ProblemSetSummary], int]:
        """题单中心：仅公开且未下线的全站题单。"""
        rows, total = await self.repo.list_public(page=page, page_size=page_size, keyword=keyword)
        counts = await self.repo.count_items([row.id for row in rows])
        return [to_summary(row, counts.get(row.id, 0)) for row in rows], total

    async def list_manage(
        self, *, page: int, page_size: int, keyword: str | None, status: str | None
    ) -> tuple[list[ProblemSetSummary], int]:
        """管理视图（admin/tutor）：全量题单，含私有与已下线。"""
        rows, total = await self.repo.list_all(
            page=page, page_size=page_size, keyword=keyword, status=status
        )
        counts = await self.repo.count_items([row.id for row in rows])
        return [to_summary(row, counts.get(row.id, 0)) for row in rows], total

    async def get_detail(self, set_id: uuid.UUID, viewer: User | None) -> ProblemSetDetail:
        """题单详情：匿名可看公开题单；条目按 sort_order 展示。"""
        problem_set = await self._get_visible(set_id, viewer)
        rows = await self.repo.list_items_with_problem(problem_set.id)
        return ProblemSetDetail(
            **to_summary(problem_set, len(rows)).model_dump(),
            items=[
                ProblemSetItemOut(
                    problem_id=problem.id,
                    title=problem.title,
                    difficulty=problem.difficulty,
                    sort_order=item.sort_order,
                )
                for item, problem in rows
            ],
            can_manage=await self._can_manage(viewer, problem_set),
        )

    # ---------------- 管理 ----------------

    async def create(self, user: User, body: ProblemSetCreate) -> ProblemSetSummary:
        """创建题单：全站题单（team_id 为空）由 admin/tutor 创建。"""
        if not await self._can_manage(user, None):
            raise APIError(AUTH_FORBIDDEN, "无权限：需要管理角色", 403)
        problem_set = await self.repo.create(
            ProblemSet(
                title=body.title.strip(),
                description=body.description,
                owner_id=user.id,
                visibility=body.visibility,
                status=ProblemSetStatus.ACTIVE,
            )
        )
        return to_summary(problem_set, 0)

    async def update(self, set_id: uuid.UUID, user: User, body: ProblemSetUpdate) -> ProblemSetSummary:
        """编辑题单元信息（title / description / visibility 缺省不动）。"""
        problem_set = await self.require_manage(set_id, user)
        if body.title is not None:
            problem_set.title = body.title.strip()
        if body.description is not None:
            problem_set.description = body.description
        if body.visibility is not None and body.visibility != problem_set.visibility:
            if problem_set.team_id is not None:
                raise APIError(PARAM_FORMAT_INVALID, "团队题单可见性不可修改", 400)
            if body.visibility == ProblemSetVisibility.TEAM:
                raise APIError(PARAM_FORMAT_INVALID, "团队题单随 teams 模块开放", 400)
            problem_set.visibility = body.visibility
        await self.db.flush()
        count = await self.repo.count_items([problem_set.id])
        return to_summary(problem_set, count.get(problem_set.id, 0))

    async def replace_items(
        self, set_id: uuid.UUID, user: User, body: ProblemSetItemsUpdate
    ) -> None:
        """全量替换题单内题目：题目须为已发布的全站公开题；同一题单内不得重复。"""
        problem_set = await self.require_manage(set_id, user)

        seen: set[uuid.UUID] = set()
        for item in body.items:
            if item.problem_id in seen:
                raise APIError(RESOURCE_DUPLICATE, "题目在题单中重复", 409)
            seen.add(item.problem_id)

        found = {
            problem.id: problem
            for problem in await self.repo.list_accessible_problems(list(seen))
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
            for item in body.items
        ]
        await self.repo.replace_items(problem_set.id, rows, user.id)

    async def archive(self, set_id: uuid.UUID, user: User) -> ProblemSetSummary:
        """下线题单：status='archived'，退出题单中心；不做物理删除。"""
        problem_set = await self.require_manage(set_id, user)
        problem_set.status = ProblemSetStatus.ARCHIVED
        await self.db.flush()
        count = await self.repo.count_items([problem_set.id])
        return to_summary(problem_set, count.get(problem_set.id, 0))

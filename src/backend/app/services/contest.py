"""比赛域服务：建赛编排、报名、赛内访问窗口、ACM/IOI 计分与封榜解冻。

时间语义：全部使用 UTC aware datetime（TIMESTAMPTZ 列；naive 输入按 UTC 归一）。
封榜按时间自动触发；解冻必须由 admin/tutor 手动执行，解冻时从 submissions
权威重算榜单回填封榜期间结果（docs/contracts/contests.md 第 5 条修订版）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependency import get_user_role_codes
from app.core.exceptions import APIError, AUTH_FORBIDDEN, PARAM_FORMAT_INVALID, RESOURCE_DUPLICATE, RESOURCE_NOT_FOUND, RESOURCE_STATE_CONFLICT
from app.enums import (
    ContestStatus,
    ContestType,
    ProblemStatus,
    RegistrationStatus,
    RuleType,
    SubmissionStatus,
    SubmitType,
)
from app.models.contest import Contest, ContestProblem, ContestRanking, ContestRegistration
from app.models.judge import Submission
from app.models.problem import Problem
from app.models.user import User
from app.repositories.contest import (
    ContestRankingRepository,
    ContestRepository,
    ContestSubmissionQueryRepository,
)
from app.schemas.contest import (
    BoardCell,
    BoardOut,
    BoardRow,
    ContestCreate,
    ContestDetail,
    ContestProblemItemOut,
    ContestSubmissionItem,
    ContestSummary,
    ContestUpdate,
    MyContestItem,
)
from app.schemas.problem import ProblemDetail
from app.services.problem import ProblemService, to_problem_detail
from app.services.system_config import ConfigService

# 全站比赛管理角色（docs/contracts/contests.md：公开比赛由 admin/tutor 创建管理）
CONTEST_MANAGER_ROLES: set[str] = {"admin", "tutor"}
# ACM 罚时系数默认值（分钟；system_configs contest.penalty_factor_minutes 可覆盖）
DEFAULT_PENALTY_FACTOR_MINUTES = 20


def _aware(value: datetime) -> datetime:
    """naive datetime 按 UTC 归一（前端 ISO 串通常自带时区）。"""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _letter(index: int) -> str:
    """比赛题号：A..Z，超出后 A1、B1…（letter VARCHAR(4)）。"""
    return chr(ord("A") + index % 26) + (str(index // 26) if index >= 26 else "")


class ContestService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ContestRepository(db)
        self.rankings = ContestRankingRepository(db)
        self.submissions = ContestSubmissionQueryRepository(db)
        self.config = ConfigService(db)

    async def _can_manage(self, user: User | None) -> bool:
        if user is None:
            return False
        codes = await get_user_role_codes(self.db, user.id)
        return bool(CONTEST_MANAGER_ROLES.intersection(codes))

    async def require_manage(self, contest_id: uuid.UUID, user: User) -> Contest:
        contest = await self.repo.get_by_id(contest_id)
        if contest is None:
            raise APIError(RESOURCE_NOT_FOUND, "比赛不存在", 404)
        if not await self._can_manage(user):
            raise APIError(AUTH_FORBIDDEN, "无权限管理该比赛", 403)
        return contest

    async def _get_contest(self, contest_id: uuid.UUID) -> Contest:
        contest = await self.repo.get_by_id(contest_id)
        if contest is None:
            raise APIError(RESOURCE_NOT_FOUND, "比赛不存在", 404)
        return contest

    async def _require_registered(self, contest: Contest, user: User) -> ContestRegistration:
        registration = await self.repo.get_registration(contest.id, user.id)
        if registration is None or registration.status != RegistrationStatus.REGISTERED:
            raise APIError(AUTH_FORBIDDEN, "未报名该比赛", 403)
        return registration

    async def _is_registered(self, contest: Contest, user: User) -> bool:
        registration = await self.repo.get_registration(contest.id, user.id)
        return registration is not None and registration.status == RegistrationStatus.REGISTERED

    async def _ensure_submissions_visible(self, contest: Contest, user: User) -> None:
        """提交记录窗口：比赛期间（end_time 之前）对所有人隐藏，赛后仅已报名用户与管理角色。"""
        if _now() < _aware(contest.end_time):
            raise APIError(AUTH_FORBIDDEN, "比赛期间提交记录不可见，结束后开放查看", 403)
        if not (await self._is_registered(contest, user) or await self._can_manage(user)):
            raise APIError(AUTH_FORBIDDEN, "未报名该比赛，无权查看提交记录", 403)

    @staticmethod
    def _validate_times(start: datetime, end: datetime, reg_start: datetime, reg_end: datetime) -> None:
        if _aware(start) >= _aware(end):
            raise APIError(PARAM_FORMAT_INVALID, "结束时间必须晚于开始时间", 400)
        if _aware(reg_start) > _aware(reg_end):
            raise APIError(PARAM_FORMAT_INVALID, "报名开始时间不能晚于报名截止时间", 400)
        if _aware(reg_end) > _aware(end):
            raise APIError(PARAM_FORMAT_INVALID, "报名截止不能晚于比赛结束", 400)

    async def _validate_problem_ids(
        self, user: User, problem_ids: list[uuid.UUID]
    ) -> None:
        """编排候选校验：已发布且（全站公开 或 本人私有）题目（docs/contracts/contests.md）。"""
        seen: list[uuid.UUID] = []
        for pid in problem_ids:
            if pid not in seen:
                seen.append(pid)
        found = await self.repo.list_arrangeable(user.id, seen)
        if len(found) != len(seen):
            raise APIError(PARAM_FORMAT_INVALID, "题目未发布或不可见，不可加入比赛", 400)

    async def search_arrangeable_problems(
        self,
        user: User,
        *,
        contest_id: uuid.UUID,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ContestProblemItemOut], int]:
        """编排页题目搜索（统一入口）：公开题 + 本人私有题（已发布），标题模糊。

        仅比赛管理角色可调（编排是管理动作）。
        """
        await self.require_manage(contest_id, user)
        rows, total = await self.repo.search_arrangeable(
            user.id, keyword=keyword, page=page, page_size=page_size
        )
        return [
            ContestProblemItemOut(
                problem_id=row.id,
                letter=None,
                score=0,
                sort_order=0,
                title=row.title,
                difficulty=row.difficulty,
            )
            for row in rows
        ], total

    @staticmethod
    async def _to_summary(repo: ContestRepository, contest: Contest) -> ContestSummary:
        counts = await repo.count_registrations([contest.id])
        problems = await repo.count_problems([contest.id])
        return ContestSummary(
            id=contest.id,
            title=contest.title,
            description=contest.description,
            logo=contest.logo,
            contest_type=contest.contest_type,
            rule_type=contest.rule_type,
            start_time=contest.start_time,
            end_time=contest.end_time,
            register_start_time=contest.register_start_time,
            register_end_time=contest.register_end_time,
            freeze_offset_seconds=contest.freeze_offset_seconds,
            board_frozen=contest.board_frozen,
            status=contest.status,
            problem_count=problems.get(contest.id, 0),
            registered_count=counts.get(contest.id, 0),
            created_at=contest.created_at,
            updated_at=contest.updated_at,
        )

    # ---------------- 查询 ----------------

    async def list_center(
        self, *, page: int, page_size: int, status: str | None, keyword: str | None = None
    ) -> tuple[list[ContestSummary], int]:
        rows, total = await self.repo.list_public(
            page=page, page_size=page_size, status=status, keyword=keyword
        )
        return [await self._to_summary(self.repo, row) for row in rows], total

    async def get_detail(self, contest_id: uuid.UUID, viewer: User | None) -> ContestDetail:
        contest = await self._get_contest(contest_id)
        summary = await self._to_summary(self.repo, contest)
        now = _now()
        start = _aware(contest.start_time)
        end = _aware(contest.end_time)
        registration = (
            await self.repo.get_registration(contest.id, viewer.id) if viewer else None
        )
        my_status = registration.status if registration else None
        registered = my_status == RegistrationStatus.REGISTERED
        can_manage = await self._can_manage(viewer)
        # 题目可见性：开赛后报名者 / 结束后所有人可见；管理角色赛前即可见（编排需要）
        can_view_problems = (start <= now and (registered or now >= end)) or can_manage
        items: list[ContestProblemItemOut] = []
        if can_view_problems:
            for cp, problem in await self.repo.list_contest_problems(contest.id):
                items.append(
                    ContestProblemItemOut(
                        problem_id=problem.id,
                        letter=cp.letter,
                        score=cp.score,
                        sort_order=cp.sort_order,
                        title=problem.title,
                        difficulty=problem.difficulty,
                    )
                )
        in_register_window = (
            _aware(contest.register_start_time) <= now <= _aware(contest.register_end_time)
        )
        return ContestDetail(
            **summary.model_dump(),
            my_registration=my_status,
            can_register=in_register_window and not registered,
            can_view_problems=can_view_problems,
            can_submit=registered and start <= now <= end,
            can_manage=can_manage,
            problems=items,
        )

    async def list_problems(
        self, user: User, contest_id: uuid.UUID
    ) -> list[ContestProblemItemOut]:
        """比赛题目列表：已报名 + 开赛后可见（赛后保持可见便于补题）。"""
        contest = await self._get_contest(contest_id)
        await self._require_registered(contest, user)
        if _now() < _aware(contest.start_time):
            raise APIError(AUTH_FORBIDDEN, "比赛尚未开始，题目不可见", 403)
        return [
            ContestProblemItemOut(
                problem_id=problem.id,
                letter=cp.letter,
                score=cp.score,
                sort_order=cp.sort_order,
                title=problem.title,
                difficulty=problem.difficulty,
            )
            for cp, problem in await self.repo.list_contest_problems(contest.id)
        ]

    async def get_problem_detail(
        self, user: User, contest_id: uuid.UUID, problem_id: uuid.UUID
    ) -> ProblemDetail:
        """比赛内题目详情（统一入口）：窗口校验后复用题库详情装配。"""
        contest = await self._get_contest(contest_id)
        await self._require_registered(contest, user)
        if _now() < _aware(contest.start_time):
            raise APIError(AUTH_FORBIDDEN, "比赛尚未开始，题目不可见", 403)
        if await self.repo.get_contest_problem(contest.id, problem_id) is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不在该比赛中", 404)
        detail = await ProblemService(self.db).get_detail(problem_id, user)
        return to_problem_detail(detail)

    async def submit_problem(
        self,
        user: User,
        contest_id: uuid.UUID,
        problem_id: uuid.UUID,
        *,
        language: str,
        code: str,
        create_submission,
    ) -> tuple[object, bool]:
        """比赛交题（统一入口）：窗口校验 → 创建 contest 提交。

        返回 (submission, after_contest)；创建函数由路由注入（避免跨模块循环依赖）。
        赛后提交自动标记补题，不计榜单（docs/contracts/contests.md 第 6 条）。
        """
        contest = await self._get_contest(contest_id)
        await self._require_registered(contest, user)
        if await self.repo.get_contest_problem(contest.id, problem_id) is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不在该比赛中", 404)
        now = _now()
        if now < _aware(contest.start_time):
            raise APIError(AUTH_FORBIDDEN, "比赛尚未开始，不可提交", 403)
        after = now > _aware(contest.end_time)
        submission = await create_submission(
            user,
            contest_id=contest.id,
            problem_id=problem_id,
            language=language,
            code=code,
            after_contest=after,
        )
        return submission, after

    async def list_my_contests(
        self, user: User, *, page: int, page_size: int, status: str | None
    ) -> tuple[list[MyContestItem], int]:
        rows, total = await self.repo.list_user_registrations(
            user.id, page=page, page_size=page_size, status=status
        )
        items: list[MyContestItem] = []
        for registration, contest in rows:
            summary = await self._to_summary(self.repo, contest)
            items.append(MyContestItem(**summary.model_dump(), my_registration=registration.status))
        return items, total

    # ---------------- 提交记录（赛后开放） ----------------

    async def list_submissions(
        self, user: User, contest_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[ContestSubmissionItem], int]:
        """比赛提交记录列表（比赛期间对所有人隐藏，赛后仅已报名用户与管理角色可见）。"""
        contest = await self._get_contest(contest_id)
        await self._ensure_submissions_visible(contest, user)
        rows, total = await self.submissions.list_records_with_users(
            contest.id, page=page, page_size=page_size
        )
        letters = {
            cp.problem_id: cp.letter
            for cp, _problem in await self.repo.list_contest_problems(contest.id)
        }
        return [
            ContestSubmissionItem(
                id=submission.id,
                problem_id=submission.problem_id,
                letter=letters.get(submission.problem_id),
                language=submission.language,
                status=submission.status,
                score=submission.score,
                time_used_ms=submission.time_used_ms,
                memory_used_kb=submission.memory_used_kb,
                nickname=user_row.nickname,
                created_at=submission.created_at,
            )
            for submission, user_row in rows
        ], total

    async def get_visible_submission(
        self, user: User, contest_id: uuid.UUID, submission_id: uuid.UUID
    ) -> Submission:
        """比赛提交详情访问校验（窗口与归属），返回提交实体；装配由路由层复用判题服务。"""
        contest = await self._get_contest(contest_id)
        await self._ensure_submissions_visible(contest, user)
        submission = await self.submissions.get_contest_submission(contest.id, submission_id)
        if submission is None:
            raise APIError(RESOURCE_NOT_FOUND, "提交不存在", 404)
        return submission

    async def cell_submissions(
        self, user: User, contest_id: uuid.UUID, cell_user_id: uuid.UUID, problem_id: uuid.UUID
    ) -> list[ContestSubmissionItem]:
        """榜单单格成功提交：该 (选手, 题目) 比赛内的 AC 提交（不含补题），赛后按提交记录窗口开放。"""
        contest = await self._get_contest(contest_id)
        await self._ensure_submissions_visible(contest, user)
        contest_problem = await self.repo.get_contest_problem(contest.id, problem_id)
        if contest_problem is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不在该比赛中", 404)
        target = await self.db.get(User, cell_user_id)
        if target is None:
            return []
        rows = await self.submissions.list_accepted_submissions(
            contest.id, cell_user_id, problem_id
        )
        return [
            ContestSubmissionItem(
                id=submission.id,
                problem_id=submission.problem_id,
                letter=contest_problem.letter,
                language=submission.language,
                status=submission.status,
                score=submission.score,
                time_used_ms=submission.time_used_ms,
                memory_used_kb=submission.memory_used_kb,
                nickname=target.nickname,
                created_at=submission.created_at,
            )
            for submission in rows
        ]

    # ---------------- 报名 ----------------

    async def register(self, user: User, contest_id: uuid.UUID) -> None:
        contest = await self._get_contest(contest_id)
        if contest.contest_type != ContestType.PUBLIC:
            raise APIError(AUTH_FORBIDDEN, "团队比赛随 teams 模块开放", 403)
        now = _now()
        if now < _aware(contest.register_start_time):
            raise APIError(RESOURCE_STATE_CONFLICT, "报名尚未开始", 409)
        if now > _aware(contest.register_end_time):
            raise APIError(RESOURCE_STATE_CONFLICT, "报名已截止", 409)
        existing = await self.repo.get_registration(contest.id, user.id)
        if existing is not None:
            if existing.status == RegistrationStatus.REGISTERED:
                raise APIError(RESOURCE_DUPLICATE, "已报名该比赛", 409)
            existing.status = RegistrationStatus.REGISTERED  # 取消后重新报名（复用唯一行）
            await self.db.flush()
            return
        await self.repo.register(
            ContestRegistration(contest_id=contest.id, user_id=user.id)
        )

    # ---------------- 创建 / 编辑 ----------------

    async def create(self, user: User, body: ContestCreate) -> ContestSummary:
        if not await self._can_manage(user):
            raise APIError(AUTH_FORBIDDEN, "无权限：需要管理角色", 403)
        self._validate_times(
            body.start_time, body.end_time, body.register_start_time, body.register_end_time
        )
        await self._validate_problem_ids(user, [p.problem_id for p in body.problems])
        contest = await self.repo.create(
            Contest(
                title=body.title.strip(),
                description=body.description,
                logo=body.logo,
                contest_type=ContestType.PUBLIC,
                owner_id=user.id,
                rule_type=body.rule_type,
                start_time=_aware(body.start_time),
                end_time=_aware(body.end_time),
                register_start_time=_aware(body.register_start_time),
                register_end_time=_aware(body.register_end_time),
                freeze_offset_seconds=body.freeze_offset_seconds,
                status=ContestStatus.SCHEDULED,
            )
        )
        await self._replace_problems(contest.id, body.problems)
        return await self._to_summary(self.repo, contest)

    async def update(
        self, contest_id: uuid.UUID, user: User, body: ContestUpdate
    ) -> ContestSummary:
        contest = await self.require_manage(contest_id, user)
        if body.title is not None:
            contest.title = body.title.strip()
        if body.description is not None:
            contest.description = body.description
        if body.logo is not None:
            contest.logo = body.logo
        if body.rule_type is not None:
            contest.rule_type = body.rule_type
        if body.freeze_offset_seconds is not None:
            contest.freeze_offset_seconds = body.freeze_offset_seconds
        # 时间四元组为整体约束：合并补丁与现值后整体校验，再统一回写
        start = _aware(body.start_time) if body.start_time else _aware(contest.start_time)
        end = _aware(body.end_time) if body.end_time else _aware(contest.end_time)
        reg_start = (
            _aware(body.register_start_time)
            if body.register_start_time
            else _aware(contest.register_start_time)
        )
        reg_end = (
            _aware(body.register_end_time)
            if body.register_end_time
            else _aware(contest.register_end_time)
        )
        self._validate_times(start, end, reg_start, reg_end)
        contest.start_time = start
        contest.end_time = end
        contest.register_start_time = reg_start
        contest.register_end_time = reg_end
        if body.problems is not None:
            await self._validate_problem_ids(user, [p.problem_id for p in body.problems])
            await self._replace_problems(contest.id, body.problems)
        await self.db.flush()
        return await self._to_summary(self.repo, contest)

    async def _replace_problems(
        self,
        contest_id: uuid.UUID,
        items: list,
    ) -> None:
        rows = [
            ContestProblem(
                contest_id=contest_id,
                problem_id=item.problem_id,
                letter=_letter(index),
                sort_order=index,
                score=item.score if item.score > 0 else 0,
            )
            for index, item in enumerate(items)
        ]
        await self.repo.replace_problems(contest_id, rows)

    # ---------------- 榜单 ----------------

    async def board(self, contest_id: uuid.UUID) -> BoardOut:
        """榜单：按赛制排序（ACM 通过数↓罚时↑；IOI 总分↓通过数↑），封榜展示冻结快照。"""
        contest = await self._get_contest(contest_id)
        contest_problems = await self.repo.list_contest_problems(contest.id)
        problem_meta = {cp.problem_id: cp for cp, _ in contest_problems}
        rows = await self.rankings.list_rows_with_users(contest.id)

        grouped: dict[uuid.UUID, list[ContestRanking]] = {}
        for row, _user in rows:
            grouped.setdefault(row.user_id, []).append(row)

        board_rows: list[BoardRow] = []
        for user_id, user_rows in grouped.items():
            nickname = next(u.nickname for r, u in rows if r.user_id == user_id)
            cells: list[BoardCell] = []
            for cp, _problem in contest_problems:
                rank_row = next((r for r in user_rows if r.problem_id == cp.problem_id), None)
                cells.append(
                    BoardCell(
                        problem_id=cp.problem_id,
                        letter=cp.letter,
                        problem_score=cp.score,
                        accepted=rank_row.accepted if rank_row else False,
                        attempts=rank_row.attempts if rank_row else 0,
                        penalty=rank_row.penalty if rank_row else 0,
                        score=rank_row.score if rank_row else 0,
                        is_frozen=rank_row.is_frozen if rank_row else contest.board_frozen,
                        accepted_at=rank_row.accepted_at if rank_row else None,
                    )
                )
            board_rows.append(
                BoardRow(
                    rank=0,
                    user_id=user_id,
                    nickname=nickname,
                    solved=sum(1 for c in cells if c.accepted),
                    total_penalty=sum(c.penalty for c in cells),
                    total_score=sum(c.score for c in cells),
                    cells=cells,
                )
            )
        if contest.rule_type == RuleType.ACM:
            board_rows.sort(key=lambda r: (-r.solved, r.total_penalty, r.nickname))
        else:
            board_rows.sort(key=lambda r: (-r.total_score, -r.solved, r.nickname))
        for index, row in enumerate(board_rows):
            row.rank = index + 1
        return BoardOut(
            contest_id=contest.id,
            rule_type=contest.rule_type,
            board_frozen=contest.board_frozen,
            rows=board_rows,
        )

    # ---------------- 判题挂钩（judge_jobs 终态调用） ----------------

    async def update_ranking_on_result(self, submission: Submission, status: str) -> None:
        """判题终态回写榜单（条件更新，docs/contracts/contests.md 第 4 条）。

        仅统计比赛内正式提交：赛后补题与 system_error（平台故障）不计；
        封榜期间（board_frozen=true）不更新榜单行。
        """
        if submission.submit_type != SubmitType.CONTEST or submission.contest_id is None:
            return
        if submission.is_after_contest or status == SubmissionStatus.SYSTEM_ERROR:
            return
        contest = await self.repo.get_by_id(submission.contest_id)
        if contest is None or contest.board_frozen:
            return

        user_id = submission.user_id
        problem_id = submission.problem_id
        await self.rankings.ensure_row(contest.id, user_id, problem_id, frozen=False)

        if contest.rule_type == RuleType.ACM:
            if status == SubmissionStatus.ACCEPTED:
                row = await self.rankings.get_row(contest.id, user_id, problem_id)
                if row is None or row.accepted:
                    return  # 幂等：已通过的重复结果不再计罚时
                factor = int(
                    await self.config.get_value(
                        "contest", "contest.penalty_factor_minutes", DEFAULT_PENALTY_FACTOR_MINUTES
                    )
                )
                elapsed = int(
                    (_now() - _aware(contest.start_time)).total_seconds() // 60
                )
                await self.rankings.mark_accepted(
                    contest.id,
                    user_id,
                    problem_id,
                    accepted_at=_now(),
                    penalty=elapsed + row.attempts * factor,
                )
            else:
                await self.rankings.increment_attempts(contest.id, user_id, problem_id)
        else:  # IOI
            await self.rankings.bump_score(
                contest.id, user_id, problem_id, int(submission.score or 0)
            )
            if status != SubmissionStatus.ACCEPTED:
                await self.rankings.increment_attempts(contest.id, user_id, problem_id)

    # ---------------- 封榜 / 解冻 / 状态推进 ----------------

    async def unfreeze(self, user: User, contest_id: uuid.UUID) -> ContestSummary:
        """手动解冻（admin/tutor）：从 submissions 权威重算榜单，回填封榜期间结果。"""
        contest = await self.require_manage(contest_id, user)
        if not contest.board_frozen:
            raise APIError(RESOURCE_STATE_CONFLICT, "榜单未处于冻结中", 409)
        await self._recompute_rankings(contest)
        contest.board_frozen = False
        await self.db.flush()
        return await self._to_summary(self.repo, contest)

    async def _recompute_rankings(self, contest: Contest) -> None:
        """重算榜单：以 submissions 为唯一事实源重建 (user, problem) 行。

        ACM：attempts = 首次通过前的错误提交数（非 system_error），penalty = 分钟差 + attempts × 系数；
        IOI：score = 各题历史最高分。
        """
        subs = await self.submissions.list_contest_submissions(contest.id)
        terminal = [
            s
            for s in subs
            if s.status
            not in (SubmissionStatus.PENDING, SubmissionStatus.JUDGING, SubmissionStatus.SYSTEM_ERROR)
        ]
        factor = int(
            await self.config.get_value(
                "contest", "contest.penalty_factor_minutes", DEFAULT_PENALTY_FACTOR_MINUTES
            )
        )
        start = _aware(contest.start_time)
        grouped: dict[tuple[uuid.UUID, uuid.UUID], list[Submission]] = {}
        for s in terminal:
            grouped.setdefault((s.user_id, s.problem_id), []).append(s)

        fresh: list[ContestRanking] = []
        for (user_id, problem_id), group in grouped.items():
            group.sort(key=lambda s: s.created_at)
            accepted_subs = [s for s in group if s.status == SubmissionStatus.ACCEPTED]
            accepted = bool(accepted_subs)
            first_accepted = accepted_subs[0] if accepted else None
            if first_accepted is not None:
                attempts = sum(1 for s in group if s.status != SubmissionStatus.ACCEPTED and s.created_at < first_accepted.created_at)
                penalty = (
                    int((_aware(first_accepted.created_at) - start).total_seconds() // 60)
                    + attempts * factor
                    if contest.rule_type == RuleType.ACM
                    else 0
                )
            else:
                attempts = len(group)
                penalty = 0
            # 提交分数按赛制原生派生（ACM 二值 / IOI 部分计分），取组内最高即为该题得分
            score = max((int(s.score or 0) for s in group), default=0)
            fresh.append(
                ContestRanking(
                    contest_id=contest.id,
                    user_id=user_id,
                    problem_id=problem_id,
                    accepted=accepted,
                    accepted_at=first_accepted.created_at if first_accepted else None,
                    attempts=attempts,
                    penalty=penalty,
                    score=score,
                    is_frozen=False,
                )
            )
        await self.rankings.delete_rows(contest.id)
        await self.rankings.add_rows(fresh)

    async def transition(self) -> None:
        """周期状态推进：开赛 → running；封榜（自动）；结束 → finished（不自动解冻）。

        解冻由 admin/tutor 手动触发（unfreeze），结束后榜单保持冻结快照直到人工解冻。
        本方法运行在独立后台会话（init_app.contest_transition_loop），
        请求级 get_db 不会为其提交，故由本方法显式 commit。
        """
        now = _now()
        # 开赛
        await self.repo.start_due_contests(now)
        # 封榜：进入封榜窗口（end_time - now <= freeze_offset）
        freezing = [
            contest
            for contest in await self.repo.list_freeze_candidates(now)
            if contest.end_time <= now + timedelta(seconds=contest.freeze_offset_seconds)
        ]
        if freezing:
            await self.repo.freeze_contests([c.id for c in freezing])
            for contest in freezing:
                await self.rankings.freeze_rows(contest.id)
        # 结束（不自动解冻：真实榜单回填由人工解冻触发）
        await self.repo.finish_due_contests(now)
        await self.db.commit()

"""比赛域服务：建赛编排、报名、赛内访问窗口、ACM/IOI 计分与封榜解冻。

时间语义：全部使用 UTC aware datetime（TIMESTAMPTZ 列；naive 输入按 UTC 归一）。
封榜按时间自动触发；解冻必须由 admin/tutor 手动执行，解冻时从 submissions
权威重算榜单回填封榜期间结果（docs/contracts/contests.md 第 5 条修订版）。
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependency import get_user_role_codes, is_admin
from app.core.exceptions import APIError, AUTH_FORBIDDEN, PARAM_FORMAT_INVALID, RESOURCE_DUPLICATE, RESOURCE_NOT_FOUND, RESOURCE_STATE_CONFLICT
from app.core.redis import RANK_CONTEST_KEY_PREFIX, get_redis
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
    AnnouncementUpdate,
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
    RevealStep,
    ScoreboardShowOut,
)
from app.schemas.problem import ProblemDetail
from app.services.problem import ProblemService, to_problem_detail
from app.services.system_config import ConfigService

# 全站比赛管理角色（docs/contracts/contests.md：公开比赛由 admin/tutor 创建管理）
CONTEST_MANAGER_ROLES: set[str] = {"admin", "tutor"}
# 赛时仍可编辑的字段（赛时工具端点承载；PUT 守卫 = ContestUpdate 全部字段 - 本集合）。
# 从 ContestUpdate.model_fields 推导守卫清单，新增 schema 字段自动纳入锁定
ANNOUNCEMENT_EDITABLE_FIELDS: set[str] = {"announcement"}
# ACM 罚时系数默认值（分钟；system_configs contest.penalty_factor_minutes 可覆盖）
DEFAULT_PENALTY_FACTOR_MINUTES = 20
# 榜单缓存 TTL 分级（秒）：进行中 3 秒、封榜 60 秒、已结束 24 小时（永久级别）
BOARD_CACHE_TTL_RUNNING = 3
BOARD_CACHE_TTL_FROZEN = 60
BOARD_CACHE_TTL_FINISHED = 24 * 3600
# 缓存击穿重建锁
BOARD_CACHE_LOCK_TTL_SECONDS = 10
BOARD_CACHE_LOCK_WAIT_SECONDS = 3

logger = logging.getLogger(__name__)


def _board_cache_key(contest_id: uuid.UUID) -> str:
    return f"{RANK_CONTEST_KEY_PREFIX}{contest_id}"


def _aware(value: datetime) -> datetime:
    """naive datetime 按 UTC 归一（前端 ISO 串通常自带时区）。"""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _letter(index: int) -> str:
    """比赛题号：A..Z，超出后 A1、B1…（letter VARCHAR(4)）。"""
    return chr(ord("A") + index % 26) + (str(index // 26) if index >= 26 else "")


# ---------------- 滚榜纯函数（可单测；不触库） ----------------


def _row_key(rule_type: str, row: BoardRow) -> tuple:
    """榜单排序键（与 board() 口径一致）：ACM 通过数↓罚时↑；IOI 总分↓通过数↑。"""
    if rule_type == RuleType.ACM:
        return (-row.solved, row.total_penalty, row.nickname)
    return (-row.total_score, -row.solved, row.nickname)


def _aggregate_final_rows(
    contest: Contest,
    subs: list[Submission],
    contest_problems: list,
    factor: int,
    nickname_of: dict[uuid.UUID, str],
) -> tuple[list[BoardRow], dict]:
    """以 submissions 现算最终榜（与 _recompute_rankings 同口径，纯函数不落库）。

    返回 (rows, cell_state)：cell_state[(user_id, problem_id)] 为每格终局真值
    {accepted, attempts, penalty, score}，供揭晓序列逐步演化。
    """
    start = _aware(contest.start_time)
    grouped: dict[tuple[uuid.UUID, uuid.UUID], list[Submission]] = {}
    for s in subs:
        if s.status in (
            SubmissionStatus.PENDING,
            SubmissionStatus.JUDGING,
            SubmissionStatus.SYSTEM_ERROR,
        ):
            continue
        grouped.setdefault((s.user_id, s.problem_id), []).append(s)

    cell_state: dict[tuple[uuid.UUID, uuid.UUID], dict] = {}
    for (user_id, problem_id), group in grouped.items():
        group.sort(key=lambda s: s.created_at)
        accepted_subs = [s for s in group if s.status == SubmissionStatus.ACCEPTED]
        accepted = bool(accepted_subs)
        first_accepted = accepted_subs[0] if accepted else None
        if first_accepted is not None:
            attempts = sum(
                1 for s in group
                if s.status != SubmissionStatus.ACCEPTED and s.created_at < first_accepted.created_at
            )
            penalty = (
                int((_aware(first_accepted.created_at) - start).total_seconds() // 60) + attempts * factor
                if contest.rule_type == RuleType.ACM
                else 0
            )
        else:
            attempts = len(group)
            penalty = 0
        score = max((int(s.score or 0) for s in group), default=0)
        cell_state[(user_id, problem_id)] = {
            "accepted": accepted,
            "attempts": attempts,
            "penalty": penalty,
            "score": score,
        }

    user_ids = {uid for uid, _pid in grouped}
    rows: list[BoardRow] = []
    for user_id in user_ids:
        cells = [
            BoardCell(
                problem_id=cp.problem_id,
                letter=cp.letter,
                problem_score=cp.score,
                accepted=cell_state.get((user_id, cp.problem_id), {}).get("accepted", False),
                attempts=cell_state.get((user_id, cp.problem_id), {}).get("attempts", 0),
                penalty=cell_state.get((user_id, cp.problem_id), {}).get("penalty", 0),
                score=cell_state.get((user_id, cp.problem_id), {}).get("score", 0),
                is_frozen=False,
            )
            for cp, _problem in contest_problems
        ]
        rows.append(
            BoardRow(
                rank=0,
                user_id=user_id,
                nickname=nickname_of.get(user_id, ""),
                solved=sum(1 for c in cells if c.accepted),
                total_penalty=sum(c.penalty for c in cells),
                total_score=sum(c.score for c in cells),
                cells=cells,
            )
        )
    rows.sort(key=lambda r: _row_key(contest.rule_type, r))
    for index, row in enumerate(rows):
        row.rank = index + 1
    return rows, cell_state


def build_reveal_steps(
    rule_type: str,
    pending: list[Submission],
    final_rows: list[BoardRow],
    base_rows: list[BoardRow],
    nickname_of: dict[uuid.UUID, str],
) -> list[RevealStep]:
    """domjudge 式揭晓序列（纯函数，可单测）。

    队伍按「最终名次从差到好」依次结算（同队内按提交时间序）。每一步只把该队
    向其终局状态演化一格：partial 演化 ⊆ 终局 ⇒ 部分名次恒不劣于终局名次，
    已结算的更差队伍永远在其下方——动画中队伍名次单调（ICPC 滚榜不变式）。
    """
    if not pending:
        return []
    letters: dict[uuid.UUID, str | None] = {}
    for row in final_rows:
        for cell in row.cells:
            letters.setdefault(cell.problem_id, cell.letter)

    # 演化起点 = 冻结快照（base_rows）；终点真值 = final_rows
    state: dict[tuple[uuid.UUID, uuid.UUID], dict] = {}
    for row in base_rows:
        for cell in row.cells:
            state[(row.user_id, cell.problem_id)] = {
                "accepted": cell.accepted,
                "attempts": cell.attempts,
                "penalty": cell.penalty,
                "score": cell.score,
            }
    final_state: dict[tuple[uuid.UUID, uuid.UUID], dict] = {
        (row.user_id, cell.problem_id): {
            "accepted": cell.accepted,
            "attempts": cell.attempts,
            "penalty": cell.penalty,
            "score": cell.score,
        }
        for row in final_rows
        for cell in row.cells
    }

    queue: dict[uuid.UUID, list[Submission]] = {}
    for s in sorted(pending, key=lambda s: s.created_at):
        queue.setdefault(s.user_id, []).append(s)

    # 最差终局名次先滚（rank 越大越差）
    final_rank_of = {row.user_id: row.rank for row in final_rows}
    reveal_order = sorted(queue, key=lambda uid: -final_rank_of.get(uid, 0))

    steps: list[RevealStep] = []
    for uid in reveal_order:
        for s in queue[uid]:
            key = (uid, s.problem_id)
            st = state.get(key, {"accepted": False, "attempts": 0, "penalty": 0, "score": 0})
            fin = final_state.get(key, {"accepted": False, "attempts": 0, "penalty": 0, "score": 0})
            if s.status == SubmissionStatus.ACCEPTED:
                st["accepted"] = True
                st["penalty"] = fin["penalty"]
            else:
                st["attempts"] += 1
            st["score"] = max(st["score"], int(s.score or 0))
            state[key] = st
            steps.append(
                RevealStep(
                    user_id=uid,
                    nickname=nickname_of.get(uid, ""),
                    problem_id=s.problem_id,
                    letter=letters.get(s.problem_id),
                    submission_id=s.id,
                    created_at=s.created_at,
                    accepted=s.status == SubmissionStatus.ACCEPTED,
                    score=st["score"] if rule_type == RuleType.IOI else 0,
                    penalty=st["penalty"] if rule_type == RuleType.ACM else 0,
                    attempts=st["attempts"],
                )
            )
    return steps


class ContestSubmitter(Protocol):
    """判题上下文端口：比赛交题创建（消费方拥有接口，docs/architecture.md 依赖注入约定）。

    由 ContestService 构造注入（路由层经 app/api/deps.py 装配 SubmissionService），
    避免比赛上下文直接依赖判题服务实现。
    """

    async def create_contest_submission(
        self,
        user: object,
        *,
        contest_id: uuid.UUID,
        problem_id: uuid.UUID,
        language: str,
        code: str,
        after_contest: bool,
        rule_type: RuleType,
    ) -> object: ...


class ContestService:
    def __init__(self, db: AsyncSession, *, submitter: ContestSubmitter | None = None) -> None:
        self.db = db
        self.repo = ContestRepository(db)
        self.rankings = ContestRankingRepository(db)
        self.submissions = ContestSubmissionQueryRepository(db)
        self.config = ConfigService(db)
        self._submitter = submitter

    async def _is_contest_manager(self, user: User | None) -> bool:
        """比赛管理角色门（创建入口 / 管理后台列表）：admin / tutor。"""
        if user is None:
            return False
        codes = await get_user_role_codes(self.db, user.id)
        return bool(CONTEST_MANAGER_ROLES.intersection(codes))

    async def require_manager(self, user: User) -> None:
        """断言当前用户为比赛管理角色（管理后台列表入口用）。"""
        if not await self._is_contest_manager(user):
            raise APIError(AUTH_FORBIDDEN, "无权限：需要管理角色", 403)

    async def list_manage(
        self, *, user: User, page: int, page_size: int, status: str | None,
        keyword: str | None = None,
    ) -> tuple[list[ContestSummary], int]:
        """管理视图：admin 全量比赛；tutor 仅本人创建（单一所有权模型），全部状态。"""
        owner_id = None if await is_admin(self.db, user) else user.id
        rows, total = await self.repo.list_manage(
            page=page, page_size=page_size, status=status, keyword=keyword, owner_id=owner_id
        )
        return [await self._to_summary(self.repo, row) for row in rows], total

    async def _can_manage(self, user: User | None, contest: Contest | None = None) -> bool:
        """单个比赛的管理权限（单一所有权模型，docs/security.md）：admin 管理全站比赛；
        其余管理角色（tutor）仅可管理本人创建的比赛。团队比赛权限随 teams 模块接入。"""
        if user is None:
            return False
        if await is_admin(self.db, user):
            return True
        return contest is not None and user.id == contest.owner_id

    async def require_manage(self, contest_id: uuid.UUID, user: User) -> Contest:
        contest = await self.repo.get_by_id(contest_id)
        if contest is None:
            raise APIError(RESOURCE_NOT_FOUND, "比赛不存在", 404)
        if not await self._can_manage(user, contest):
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
        """提交记录窗口：比赛管理者（admin / 创建者）随时可见；比赛期间对参赛者隐藏，赛后开放已报名用户。"""
        if await self._can_manage(user, contest):
            return
        if _now() < _aware(contest.end_time):
            raise APIError(AUTH_FORBIDDEN, "比赛期间提交记录不可见，结束后开放查看", 403)
        if not await self._is_registered(contest, user):
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
            freeze_time=contest.freeze_time,
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
        can_manage = await self._can_manage(viewer, contest)
        # 题目可见性：开赛后报名者 / 结束后所有人可见；比赛管理者赛前即可见（编排需要）
        can_view_problems = (start <= now and (registered or now >= end)) or can_manage
        items: list[ContestProblemItemOut] = []
        if can_view_problems:
            rows = await self.repo.list_contest_problems(contest.id)
            solved_map = await self._contest_solve_map(contest.id, viewer, rows)
            for cp, problem in rows:
                items.append(
                    ContestProblemItemOut(
                        problem_id=problem.id,
                        letter=cp.letter,
                        score=cp.score,
                        sort_order=cp.sort_order,
                        title=problem.title,
                        difficulty=problem.difficulty,
                        solved=solved_map.get(problem.id),
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
            announcement=contest.announcement,
            announcement_updated_at=contest.announcement_updated_at,
            problems=items,
        )

    async def _contest_solve_map(
        self,
        contest_id: uuid.UUID,
        viewer: User | None,
        rows: list[tuple[ContestProblem, Problem]],
    ) -> dict[uuid.UUID, bool]:
        """查看者在本场比赛的逐题作答状态（匿名 / 无查看需要时为空 map）。

        口径 = 本场比赛提交（含补题）：AC 为已解出，有提交未 AC 为已尝试；
        练习 / 验题通过不计入，避免跨场景误标「已写」。
        """
        if viewer is None:
            return {}
        return await self.repo.solve_status_map_for_contest(
            contest_id, viewer.id, [problem.id for _, problem in rows]
        )

    async def list_problems(
        self, user: User, contest_id: uuid.UUID
    ) -> list[ContestProblemItemOut]:
        """比赛题目列表：已报名 + 开赛后可见（赛后保持可见便于补题）；带本场作答状态。"""
        contest = await self._get_contest(contest_id)
        await self._require_registered(contest, user)
        if _now() < _aware(contest.start_time):
            raise APIError(AUTH_FORBIDDEN, "比赛尚未开始，题目不可见", 403)
        rows = await self.repo.list_contest_problems(contest.id)
        solved_map = await self._contest_solve_map(contest.id, user, rows)
        return [
            ContestProblemItemOut(
                problem_id=problem.id,
                letter=cp.letter,
                score=cp.score,
                sort_order=cp.sort_order,
                title=problem.title,
                difficulty=problem.difficulty,
                solved=solved_map.get(problem.id),
            )
            for cp, problem in rows
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
        detail = await ProblemService(self.db).get_detail(
            problem_id, user, bypass_visibility=True
        )
        return to_problem_detail(detail)

    async def submit_problem(
        self,
        user: User,
        contest_id: uuid.UUID,
        problem_id: uuid.UUID,
        *,
        language: str,
        code: str,
    ) -> tuple[object, bool]:
        """比赛交题（统一入口）：窗口校验 → 经 ContestSubmitter 端口创建 contest 提交。

        返回 (submission, after_contest)；判题上下文端口由构造注入，非路由组合根
        （rpc / 测试）未装配端口时延迟自建兜底。赛后提交自动标记补题，不计榜单
        （docs/contracts/contests.md 第 6 条）。
        """
        contest = await self._get_contest(contest_id)
        await self._require_registered(contest, user)
        if await self.repo.get_contest_problem(contest.id, problem_id) is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不在该比赛中", 404)
        now = _now()
        if now < _aware(contest.start_time):
            raise APIError(AUTH_FORBIDDEN, "比赛尚未开始，不可提交", 403)
        after = now > _aware(contest.end_time)
        if self._submitter is not None:
            submitter = self._submitter
        else:  # 非路由组合根兜底：延迟导入避免模块环
            from app.services.judge import SubmissionService

            submitter = SubmissionService(self.db)
        submission = await submitter.create_contest_submission(
            user,
            contest_id=contest.id,
            problem_id=problem_id,
            language=language,
            code=code,
            after_contest=after,
            rule_type=contest.rule_type,
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
        self, user: User, contest_id: uuid.UUID, *, page: int, page_size: int,
        keyword: str | None = None, language: str | None = None,
        status: str | None = None, problem_id: uuid.UUID | None = None,
    ) -> tuple[list[ContestSubmissionItem], int]:
        """比赛提交记录列表（管理角色随时可见；参赛者赛后开放）。

        keyword 模糊匹配提交人昵称；language / status / problem_id 精确过滤。
        """
        contest = await self._get_contest(contest_id)
        await self._ensure_submissions_visible(contest, user)
        rows, total = await self.submissions.list_records_with_users(
            contest.id, page=page, page_size=page_size,
            keyword=keyword, language=language, status=status, problem_id=problem_id,
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
        if not await self._is_contest_manager(user):
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
                freeze_time=_aware(body.freeze_time) if body.freeze_time else None,
                status=ContestStatus.SCHEDULED,
            )
        )
        await self._replace_problems(contest.id, body.problems)
        return await self._to_summary(self.repo, contest)

    async def update(
        self, contest_id: uuid.UUID, user: User, body: ContestUpdate
    ) -> ContestSummary:
        contest = await self.require_manage(contest_id, user)
        # 赛时守卫：比赛开始后结构性信息冻结（docs/contracts/contests.md 状态守卫节）——
        # 影响比赛公平 / 结构的字段一律拒绝；赛中调整走受控端点（公告 / 后续延时）。
        # 守卫字段从 ContestUpdate 模型定义推导（杜绝与 schema 脱节的「魔法字段清单」）：
        # 即「全部字段 - 公告类」，freeze_time 的显式 null（取消封榜）同样计入
        if contest.status != ContestStatus.SCHEDULED:
            structural = set(ContestUpdate.model_fields) - ANNOUNCEMENT_EDITABLE_FIELDS
            touched = {
                field
                for field in structural
                if getattr(body, field) is not None or field in body.model_fields_set
            }
            if touched:
                raise APIError(
                    RESOURCE_STATE_CONFLICT,
                    "比赛已开始，不可修改结构性信息（公告等赛时调整请使用赛时工具）",
                    409,
                )
        if body.title is not None:
            contest.title = body.title.strip()
        if body.description is not None:
            contest.description = body.description
        if body.logo is not None:
            contest.logo = body.logo
        if body.rule_type is not None:
            contest.rule_type = body.rule_type
        # 时间五元组为整体约束：合并补丁与现值后整体校验，再统一回写。
        # freeze_time 经 model_fields_set 区分「未传（不动）」与「显式 null（取消封榜）」
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
        if "freeze_time" in body.model_fields_set:
            freeze_at = _aware(body.freeze_time) if body.freeze_time else None
        else:
            freeze_at = _aware(contest.freeze_time) if contest.freeze_time else None
        self._validate_times(start, end, reg_start, reg_end)
        if freeze_at is not None and not (start < freeze_at <= end):
            raise APIError(
                PARAM_FORMAT_INVALID, "封榜时间必须晚于开始时间且不晚于结束时间", 400
            )
        contest.start_time = start
        contest.end_time = end
        contest.register_start_time = reg_start
        contest.register_end_time = reg_end
        contest.freeze_time = freeze_at
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
        """榜单：Redis 读缓存（rank:contest:<id>，docs/operations.md「Redis 约定」）优先。

        缓存未命中才全量计算（contest_rankings 为权威）并回填，TTL 按场景分级：
        进行中 3s / 封榜 60s / 已结束 24h；写路径（判题回写、封榜、解冻）主动失效。
        并发未命中以 Redis SETNX 重建锁防击穿，Redis 异常一律降级直查数据库。
        """
        cache_key = _board_cache_key(contest_id)
        cached = await self._load_board_cache(cache_key)
        if cached is not None:
            return cached

        contest = await self._get_contest(contest_id)
        lock_key = f"{cache_key}:lock"
        acquired = False
        try:
            try:
                acquired = bool(
                    await get_redis().set(lock_key, "1", nx=True, ex=BOARD_CACHE_LOCK_TTL_SECONDS)
                )
            except Exception:
                acquired = True  # Redis 异常：放弃互斥，正确性优先直算

            if not acquired:
                # 等待持锁者回填缓存，期间轮询重读；超时则自行回源兜底
                deadline = asyncio.get_running_loop().time() + BOARD_CACHE_LOCK_WAIT_SECONDS
                while asyncio.get_running_loop().time() < deadline:
                    await asyncio.sleep(0.1)
                    cached = await self._load_board_cache(cache_key)
                    if cached is not None:
                        return cached
                return await self._compute_board(contest)

            result = await self._compute_board(contest)
            await self._store_board_cache(contest, result)
            return result
        finally:
            if acquired:
                try:
                    await get_redis().delete(lock_key)
                except Exception:
                    pass

    async def _load_board_cache(self, cache_key: str) -> BoardOut | None:
        try:
            raw = await get_redis().get(cache_key)
        except Exception:
            return None  # Redis 瞬断：降级直查数据库
        if raw is None:
            return None
        try:
            return BoardOut.model_validate_json(raw)
        except ValidationError:
            logger.warning("榜单缓存载荷损坏，回源重算 key=%s", cache_key)
            return None

    async def _store_board_cache(self, contest: Contest, result: BoardOut) -> None:
        if contest.status == ContestStatus.FINISHED:
            ttl = BOARD_CACHE_TTL_FINISHED if contest.board_frozen else None  # 永久
        elif contest.board_frozen:
            ttl = BOARD_CACHE_TTL_FROZEN
        else:
            ttl = BOARD_CACHE_TTL_RUNNING
        try:
            await get_redis().set(_board_cache_key(contest.id), result.model_dump_json(), ex=ttl)
        except Exception:
            logger.warning("榜单缓存回填失败 contest_id=%s（不影响本次返回）", contest.id, exc_info=True)

    async def invalidate_board_cache(self, contest_id: uuid.UUID) -> None:
        """公开失效端口：外部（API 层 commit 后）补一次失效，消除「先删缓存后提交」竞态。"""
        await self._invalidate_board_cache(contest_id)

    async def _invalidate_board_cache(self, contest_id: uuid.UUID) -> None:
        """写路径主动失效榜单缓存（Redis 异常仅告警，短 TTL 兜底最终一致）。"""
        try:
            await get_redis().delete(_board_cache_key(contest_id))
        except Exception:
            logger.warning("榜单缓存失效失败 contest_id=%s（等待 TTL 兜底）", contest_id, exc_info=True)

    async def _compute_board(self, contest: Contest) -> BoardOut:
        """全量计算榜单：按赛制排序（ACM 通过数↓罚时↑；IOI 总分↓通过数↑），封榜展示冻结快照。"""
        contest_problems = await self.repo.list_contest_problems(contest.id)
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

    async def full_score_for(self, contest_id: uuid.UUID, problem_id: uuid.UUID) -> int | None:
        """单题满分基准（比赛上下文自持的计分知识，docs/contracts/contests.md 第 4 条）。

        返回比赛配置的单题分值；未配置（<= 0）或题目不在比赛中返回 None（调用方用练习满分兜底）。
        判题上下文不直查 ContestProblem，经本方法获取。
        """
        contest_problem = await self.repo.get_contest_problem(contest_id, problem_id)
        if contest_problem is not None and contest_problem.score > 0:
            return contest_problem.score
        return None

    async def on_submission_finalized(self, submission: Submission, status: str) -> None:
        """判题终态回写端口：比赛提交的榜单条件更新（judge 上下文唯一入口）。

        内部委托 update_ranking_on_result；非比赛提交为无操作。
        """
        await self.update_ranking_on_result(submission, status)

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
        await self._invalidate_board_cache(contest.id)

    # ---------------- 封榜 / 解冻 / 状态推进 ----------------

    async def unfreeze(self, user: User, contest_id: uuid.UUID) -> ContestSummary:
        """手动解冻（admin/tutor）：从 submissions 权威重算榜单，回填封榜期间结果。

        仅赛后可执行（running 时返回 3002）——封榜是赛时公平性机制，
        赛中解冻会提前泄露封榜期提交结果；比赛结束前榜单保持冻结快照。
        """
        contest = await self.require_manage(contest_id, user)
        if contest.status == ContestStatus.RUNNING:
            raise APIError(RESOURCE_STATE_CONFLICT, "比赛进行中不可解冻榜单", 409)
        if not contest.board_frozen:
            raise APIError(RESOURCE_STATE_CONFLICT, "榜单未处于冻结中", 409)
        await self._recompute_rankings(contest)
        contest.board_frozen = False
        await self.db.flush()
        await self._invalidate_board_cache(contest.id)
        return await self._to_summary(self.repo, contest)

    async def update_announcement(
        self, user: User, contest_id: uuid.UUID, body: AnnouncementUpdate
    ) -> ContestSummary:
        """更新比赛公告（admin/tutor / 团队管理角色；赛时唯一允许的题外编辑）。

        空字符串 = 清空公告（详情页公告条随之隐藏）。
        """
        contest = await self.require_manage(contest_id, user)
        content = body.announcement.strip()
        contest.announcement = content or None
        contest.announcement_updated_at = _now()
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

    # ---------------- 滚榜（赛后大屏工具；只读，不改变榜单状态） ----------------

    async def scoreboard_show(self, user: User, contest_id: uuid.UUID) -> ScoreboardShowOut:
        """滚榜数据包：冻结快照榜（起点）+ 最终榜（终点）+ 封榜期提交揭晓序列。

        管理角色专用（require_manage）；不落库、不解冻——final_rows 由 submissions
        现算，base_rows 为榜单表当前快照。封榜期提交以 frozen_at 为界；
        frozen_at 缺失（历史比赛未记录）回退为封榜配置时间 freeze_time 推导。
        """
        contest = await self.require_manage(contest_id, user)
        contest_problems = await self.repo.list_contest_problems(contest.id)
        items = sorted(
            (
                ContestProblemItemOut(
                    problem_id=cp.problem_id, letter=cp.letter, score=cp.score,
                    sort_order=cp.sort_order, title=problem.title,
                )
                for cp, problem in contest_problems
            ),
            key=lambda i: i.sort_order,
        )

        # 起点：榜单表现状（封榜快照；未封榜则与 final 一致，滚榜退化为纯展示）
        base_rows = (await self.board(contest.id)).rows

        # 终点：以 submissions 为唯一事实源现算最终榜（不落库）
        subs = await self.submissions.list_contest_submissions(contest.id)
        nickname_of = await self.submissions.list_team_nicknames(contest.id)
        factor = int(
            await self.config.get_value(
                "contest", "contest.penalty_factor_minutes", DEFAULT_PENALTY_FACTOR_MINUTES
            )
        )
        final_rows, _cell_state = _aggregate_final_rows(
            contest, subs, contest_problems, factor, nickname_of
        )

        # 揭晓序列：封榜期终态提交（frozen_at 为界，缺省按封榜窗口推导）
        if contest.frozen_at is not None:
            freeze_moment = _aware(contest.frozen_at)
        else:
            # frozen_at 缺失（历史数据）回退：封榜配置时刻；仍缺失（未封榜）回退比赛开始
            freeze_moment = (
                _aware(contest.freeze_time) if contest.freeze_time else _aware(contest.start_time)
            )
        pending = [
            s
            for s in subs
            if s.status
            not in (SubmissionStatus.PENDING, SubmissionStatus.JUDGING, SubmissionStatus.SYSTEM_ERROR)
            and _aware(s.created_at) >= freeze_moment
        ]
        steps = build_reveal_steps(contest.rule_type, pending, final_rows, base_rows, nickname_of)

        return ScoreboardShowOut(
            contest_id=contest.id,
            title=contest.title,
            rule_type=contest.rule_type,
            board_frozen=contest.board_frozen,
            frozen_at=contest.frozen_at,
            problems=items,
            base_rows=base_rows,
            final_rows=final_rows,
            steps=steps,
        )

    async def transition(self) -> None:
        """周期状态推进：开赛 → running；封榜（自动）；结束 → finished（不自动解冻）。

        解冻由 admin/tutor 手动触发（unfreeze），结束后榜单保持冻结快照直到人工解冻。
        本方法运行在独立后台会话（init_app.contest_transition_loop），
        请求级 get_db 不会为其提交，故由本方法显式 commit。
        """
        now = _now()
        # 开赛
        await self.repo.start_due_contests(now)
        # 封榜：到达封榜时间（freeze_time <= now，repo 直接筛出候选）
        freezing = await self.repo.list_freeze_candidates(now)
        if freezing:
            await self.repo.freeze_contests([c.id for c in freezing], now)
            for contest in freezing:
                await self.rankings.freeze_rows(contest.id)
        # 结束（不自动解冻：真实榜单回填由人工解冻触发）
        await self.repo.finish_due_contests(now)
        await self.db.commit()
        # 封榜改变 board_frozen 快照标记，commit 后失效对应榜单缓存（并发读不可见未提交数据）
        for contest in freezing:
            await self._invalidate_board_cache(contest.id)

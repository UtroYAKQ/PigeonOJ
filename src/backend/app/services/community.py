"""社区服务：官方题解展示、用户题解分享、评论与举报（docs/contracts/community.md）。

门控复用：题目可见性一律经 ProblemService.get_detail（题解 / 评论继承题目可见性），
比赛进行中门禁经 ContestService 公开端口 is_problem_locked_by_running_contest，
功能开关读 system_configs `community.feature_switches`（admin.md community 域）。
频控：Redis 固定窗口（SETNX + TTL，docs/security.md 频控口径）。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependency import is_admin
from app.core.exceptions import (
    APIError,
    AUTH_FORBIDDEN,
    AUTH_NOT_LOGGED_IN,
    PARAM_FORMAT_INVALID,
    RATE_LIMITED,
    RESOURCE_DUPLICATE,
    RESOURCE_NOT_FOUND,
    RESOURCE_STATE_CONFLICT,
)
from app.core.redis import get_redis
from app.enums import (
    CodeShareLanguage,
    CodeShareStatus,
    CommentTargetType,
    ReportTargetType,
    SolutionStatus,
)
from app.models.admin import Report
from app.models.community import CodeShare, Comment, Solution
from app.models.user import User
from app.repositories.admin import ReportRepository
from app.repositories.community import (
    CodeShareRepository,
    CommentRepository,
    SolutionRepository,
)
from app.repositories.problem import ProblemRepository
from app.repositories.user import UserRepository
from app.schemas.community import (
    AdminCodeShareOut,
    AdminSolutionOut,
    AuthorBrief,
    CodeShareCreate,
    CodeShareDetail,
    CodeShareSummary,
    CommentAdminOut,
    CommentCreate,
    CommentOut,
    EditorialOut,
    ProblemBrief,
    ReportCreate,
    SolutionCreate,
    SolutionDetail,
    SolutionSummary,
    SolutionUpdate,
)
from app.services.contest import is_problem_locked_by_running_contest
from app.services.problem import ProblemDetailData, ProblemService
from app.services.system_config import ConfigService
from app.utils.pagination import PaginatedResponse

# 冷却窗口（秒）与内容上限（community.md「端点」节）
SOLUTION_CREATE_COOLDOWN_SECONDS = 60
COMMENT_CREATE_COOLDOWN_SECONDS = 10
REPORT_CREATE_COOLDOWN_SECONDS = 60
CODE_SHARE_CREATE_COOLDOWN_SECONDS = 60
EXCERPT_MAX_CHARS = 200
COMMENT_REPLY_PREVIEW_LIMIT = 2
FEATURE_SWITCHES_KEY = "community.feature_switches"
COOLDOWN_KEY_PREFIX = "community:cooldown:"

_UNKNOWN_AUTHOR_NICKNAME = "未知用户"


async def _claim_cooldown(kind: str, user_id: uuid.UUID, window_seconds: int) -> None:
    """认领冷却槽（SETNX + TTL）；冷却中抛 4002（窗口内重复请求不重置 TTL）。"""
    key = f"{COOLDOWN_KEY_PREFIX}{kind}:{user_id}"
    claimed = await get_redis().set(key, "1", nx=True, ex=max(1, window_seconds))
    if not claimed:
        raise APIError(RATE_LIMITED, "操作过于频繁，请稍后再试", 429)


def _solution_summary(
    row: Solution, author: AuthorBrief, comment_count: int
) -> SolutionSummary:
    return SolutionSummary(
        id=row.id,
        problem_id=row.problem_id,
        author=author,
        title=row.title,
        excerpt=row.content[:EXCERPT_MAX_CHARS],
        status=row.status,
        comment_count=comment_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _comment_out(row: Comment, authors: dict[uuid.UUID, AuthorBrief]) -> CommentOut:
    """软删行输出占位：content / author 置空（community.md「数据所有权」）。"""
    if row.is_deleted:
        return CommentOut(
            id=row.id,
            parent_id=row.parent_id,
            content=None,
            author=None,
            is_deleted=True,
            created_at=row.created_at,
        )
    return CommentOut(
        id=row.id,
        parent_id=row.parent_id,
        content=row.content,
        author=authors.get(
            row.user_id,
            AuthorBrief(id=row.user_id, nickname=_UNKNOWN_AUTHOR_NICKNAME, avatar_url=None),
        ),
        is_deleted=False,
        created_at=row.created_at,
    )


def _code_share_excerpt(row: CodeShare) -> str:
    """列表摘要：说明优先，无说明退化为代码首行（截断）。"""
    if row.description:
        return row.description[:EXCERPT_MAX_CHARS]
    stripped = row.code.strip()
    return stripped.splitlines()[0][:120] if stripped else ""


class CommunityService:
    def __init__(
        self,
        db: AsyncSession,
        problems: ProblemService,
        config: ConfigService,
    ) -> None:
        self.db = db
        self.problems = problems
        self.config = config
        self.solutions = SolutionRepository(db)
        self.comments = CommentRepository(db)
        self.code_shares = CodeShareRepository(db)
        self.reports = ReportRepository(db)

    # ---- 门控 ----

    async def _feature_enabled(self, name: str) -> bool:
        raw = await self.config.get_value("community", FEATURE_SWITCHES_KEY, {})
        if isinstance(raw, dict):
            return bool(raw.get(name, True))
        return True

    async def _is_admin(self, user: User | None) -> bool:
        return user is not None and await is_admin(self.db, user)

    async def _require_problem_readable(
        self, problem_id: uuid.UUID, user: User | None
    ) -> ProblemDetailData:
        """题解 / 评论的一切读写先过题目访问检查 + 比赛进行中门禁。"""
        detail = await self.problems.get_detail(problem_id, user)
        if await is_problem_locked_by_running_contest(self.db, problem_id):
            raise APIError(RESOURCE_STATE_CONFLICT, "比赛进行中，题解与评论暂不开放", 409)
        return detail

    async def _require_solutions_enabled(self) -> None:
        if not await self._feature_enabled("solutions"):
            raise APIError(RESOURCE_STATE_CONFLICT, "题解功能未开放", 409)

    async def _require_comments_enabled(self) -> None:
        if not await self._feature_enabled("comments"):
            raise APIError(RESOURCE_STATE_CONFLICT, "评论功能未开放", 409)

    # ---- 作者信息 ----

    async def _author_briefs(
        self, user_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, AuthorBrief]:
        rows = await UserRepository(self.db).get_briefs(list(dict.fromkeys(user_ids)))
        return {u.id: AuthorBrief.model_validate(u) for u in rows}

    # ---- 官方题解 ----

    async def get_editorial(
        self, problem_id: uuid.UUID, user: User | None
    ) -> EditorialOut:
        detail = await self._require_problem_readable(problem_id, user)
        return EditorialOut(solution=detail.problem.solution, can_manage=detail.can_manage)

    # ---- 用户题解 ----

    async def list_solutions(
        self,
        problem_id: uuid.UUID,
        user: User | None,
        page: int,
        page_size: int,
        keyword: str | None,
        mine: bool,
    ) -> PaginatedResponse[SolutionSummary]:
        await self._require_problem_readable(problem_id, user)
        author_id = None
        if mine:
            if user is None:
                raise APIError(AUTH_NOT_LOGGED_IN, "查看我的题解需要登录", 401)
            author_id = user.id
        rows, total = await self.solutions.list_for_problem(
            problem_id, page, page_size, keyword, author_id
        )
        counts = await self.solutions.count_comments([r.id for r in rows])
        authors = await self._author_briefs([r.user_id for r in rows])
        items = [
            _solution_summary(
                row,
                authors.get(
                    row.user_id,
                    AuthorBrief(id=row.user_id, nickname=_UNKNOWN_AUTHOR_NICKNAME),
                ),
                counts.get(row.id, 0),
            )
            for row in rows
        ]
        return PaginatedResponse[SolutionSummary](
            items=items, total=total, page=page, page_size=page_size
        )

    async def _require_solution(self, solution_id: uuid.UUID) -> Solution:
        row = await self.solutions.get_by_id(solution_id)
        if row is None:
            raise APIError(RESOURCE_NOT_FOUND, "题解不存在", 404)
        return row

    async def _require_solution_readable(
        self, row: Solution, user: User | None
    ) -> None:
        """published 对题目可见者开放；draft / removed 仅作者与 admin 可读（404 不泄漏存在性）。"""
        if row.status == SolutionStatus.PUBLISHED:
            return
        is_owner = user is not None and row.user_id == user.id
        if not is_owner and not await self._is_admin(user):
            raise APIError(RESOURCE_NOT_FOUND, "题解不存在", 404)

    def _solution_detail_out(
        self, row: Solution, comment_count: int, author: AuthorBrief
    ) -> SolutionDetail:
        summary = _solution_summary(row, author, comment_count)
        return SolutionDetail(**summary.model_dump(), content=row.content)

    async def get_solution(self, solution_id: uuid.UUID, user: User | None) -> SolutionDetail:
        row = await self._require_solution(solution_id)
        await self._require_problem_readable(row.problem_id, user)
        await self._require_solution_readable(row, user)
        counts = await self.solutions.count_comments([row.id])
        authors = await self._author_briefs([row.user_id])
        return self._solution_detail_out(
            row,
            counts.get(row.id, 0),
            authors.get(
                row.user_id, AuthorBrief(id=row.user_id, nickname=_UNKNOWN_AUTHOR_NICKNAME)
            ),
        )

    async def create_solution(
        self, problem_id: uuid.UUID, user: User, body: SolutionCreate
    ) -> SolutionDetail:
        await self._require_solutions_enabled()
        await self._require_problem_readable(problem_id, user)
        await _claim_cooldown("solution", user.id, SOLUTION_CREATE_COOLDOWN_SECONDS)
        row = await self.solutions.create(
            Solution(
                problem_id=problem_id,
                user_id=user.id,
                title=body.title,
                content=body.content,
                status=SolutionStatus.PUBLISHED,
            )
        )
        author = AuthorBrief.model_validate(user)
        return self._solution_detail_out(row, 0, author)

    async def update_solution(
        self, solution_id: uuid.UUID, user: User, body: SolutionUpdate
    ) -> SolutionDetail:
        """owner 编辑；admin 不经此端点改内容（治理走 admin status 端点）。"""
        await self._require_solutions_enabled()
        row = await self._require_solution(solution_id)
        if row.user_id != user.id:
            raise APIError(AUTH_FORBIDDEN, "无权限操作他人题解", 403)
        if row.status == SolutionStatus.REMOVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "题解已下架，不可编辑", 409)
        if body.title is not None:
            row.title = body.title
        if body.content is not None:
            row.content = body.content
        row.updated_at = datetime.now()
        await self.db.flush()
        counts = await self.solutions.count_comments([row.id])
        return self._solution_detail_out(row, counts.get(row.id, 0), AuthorBrief.model_validate(user))

    async def remove_solution(self, solution_id: uuid.UUID, user: User) -> None:
        """下架（owner / admin；幂等；恢复仅经 admin 端点）。"""
        await self._require_solutions_enabled()
        row = await self._require_solution(solution_id)
        is_owner = row.user_id == user.id
        if not is_owner and not await self._is_admin(user):
            raise APIError(AUTH_FORBIDDEN, "无权限操作他人题解", 403)
        if row.status != SolutionStatus.REMOVED:
            row.status = SolutionStatus.REMOVED
            row.updated_at = datetime.now()
            await self.db.flush()

    # ---- 评论 ----

    async def _require_comment_target(
        self, target_type: str, target_id: uuid.UUID, user: User | None
    ) -> Solution | CodeShare:
        """评论目标可见性门控：题解继承题目可见性；代码分享 published 公开 /
        removed 仅作者与 admin；关联题目同样走题目门控 + 比赛门禁。"""
        if target_type == CommentTargetType.SOLUTION:
            row: Solution | CodeShare = await self.solutions.get_by_id(target_id)
            if row is None:
                raise APIError(RESOURCE_NOT_FOUND, "评论目标不存在", 404)
            await self._require_problem_readable(row.problem_id, user)
            await self._require_solution_readable(row, user)  # type: ignore[arg-type]
            return row
        raise APIError(PARAM_FORMAT_INVALID, "暂不支持该评论目标", 400)

    async def list_comments(
        self,
        target_type: str,
        target_id: uuid.UUID,
        user: User | None,
        page: int,
        page_size: int,
        parent_id: uuid.UUID | None,
        include_deleted: bool,
    ) -> PaginatedResponse[CommentOut]:
        if include_deleted and not await self._is_admin(user):
            raise APIError(AUTH_FORBIDDEN, "无权限", 403)
        await self._require_comment_target(target_type, target_id, user)
        if parent_id is not None:
            parent = await self.comments.get_by_id(parent_id)
            if (
                parent is None
                or parent.target_type != target_type
                or parent.target_id != target_id
                or parent.parent_id is not None
            ):
                raise APIError(RESOURCE_NOT_FOUND, "评论不存在", 404)
            rows, total = await self.comments.list_replies(
                parent_id, page, page_size, include_deleted
            )
            authors = await self._author_briefs([r.user_id for r in rows])
            items = [_comment_out(row, authors) for row in rows]
            return PaginatedResponse[CommentOut](
                items=items, total=total, page=page, page_size=page_size
            )
        rows, total = await self.comments.list_top(
            target_type, target_id, page, page_size, include_deleted
        )
        reply_counts = await self.comments.count_replies([r.id for r in rows])
        grouped = await self.comments.replies_for_parents([r.id for r in rows], include_deleted)
        authors = await self._author_briefs(
            [r.user_id for r in rows]
            + [c.user_id for group in grouped.values() for c in group]
        )
        items: list[CommentOut] = []
        for row in rows:
            out = _comment_out(row, authors)
            out.reply_count = reply_counts.get(row.id, 0)
            out.replies = [
                _comment_out(reply, authors)
                for reply in grouped.get(row.id, [])[:COMMENT_REPLY_PREVIEW_LIMIT]
            ]
            items.append(out)
        return PaginatedResponse[CommentOut](
            items=items, total=total, page=page, page_size=page_size
        )

    async def create_comment(self, user: User, body: CommentCreate) -> CommentOut:
        await self._require_comments_enabled()
        target = await self._require_comment_target(body.target_type, body.target_id, user)
        if target.status != SolutionStatus.PUBLISHED:
            raise APIError(RESOURCE_STATE_CONFLICT, "评论目标当前不可评论", 409)
        if body.parent_id is not None:
            parent = await self.comments.get_by_id(body.parent_id)
            if (
                parent is None
                or parent.target_type != body.target_type
                or parent.target_id != body.target_id
                or parent.parent_id is not None
            ):
                raise APIError(RESOURCE_STATE_CONFLICT, "回复的评论不存在", 409)
            if parent.is_deleted:
                raise APIError(RESOURCE_STATE_CONFLICT, "回复的评论已删除", 409)
        await _claim_cooldown("comment", user.id, COMMENT_CREATE_COOLDOWN_SECONDS)
        comment = await self.comments.create(
            Comment(
                user_id=user.id,
                target_type=body.target_type,
                target_id=body.target_id,
                parent_id=body.parent_id,
                content=body.content,
            )
        )
        return _comment_out(comment, {user.id: AuthorBrief.model_validate(user)})

    async def delete_comment(self, comment_id: uuid.UUID, user: User) -> None:
        """软删（owner / admin；幂等；恢复走 admin 端点）。"""
        row = await self.comments.get_by_id(comment_id)
        if row is None:
            raise APIError(RESOURCE_NOT_FOUND, "评论不存在", 404)
        await self._require_comment_target(row.target_type, row.target_id, user)
        is_owner = row.user_id == user.id
        if not is_owner and not await self._is_admin(user):
            raise APIError(AUTH_FORBIDDEN, "无权限操作他人评论", 403)
        if not row.is_deleted:
            row.is_deleted = True
            row.updated_at = datetime.now()
            await self.db.flush()

    # ---- 举报 ----

    async def create_report(self, user: User, body: ReportCreate) -> None:
        # 目标存在性：P1 校验题解 / 代码分享 / 评论；其余类型交由治理端人工核对（community.md）
        if body.target_type == ReportTargetType.SOLUTION:
            if await self.solutions.get_by_id(body.target_id) is None:
                raise APIError(RESOURCE_NOT_FOUND, "举报目标不存在", 404)
        elif body.target_type == ReportTargetType.CODE_SHARE:
            if await self.code_shares.get_by_id(body.target_id) is None:
                raise APIError(RESOURCE_NOT_FOUND, "举报目标不存在", 404)
        elif body.target_type == ReportTargetType.COMMENT:
            if await self.comments.get_by_id(body.target_id) is None:
                raise APIError(RESOURCE_NOT_FOUND, "举报目标不存在", 404)
        if await self.reports.get_pending_duplicate(user.id, body.target_type, body.target_id):
            raise APIError(RESOURCE_DUPLICATE, "该内容已有待处理的举报", 409)
        await _claim_cooldown("report", user.id, REPORT_CREATE_COOLDOWN_SECONDS)
        await self.reports.create(
            Report(
                reporter_id=user.id,
                target_type=body.target_type,
                target_id=body.target_id,
                reason=body.reason,
            )
        )

    # ---- 代码广场（community.md code_shares）----

    async def _require_code_share(self, share_id: uuid.UUID) -> CodeShare:
        row = await self.code_shares.get_by_id(share_id)
        if row is None:
            raise APIError(RESOURCE_NOT_FOUND, "代码分享不存在", 404)
        return row

    async def _require_code_share_readable(self, row: CodeShare, user: User | None) -> None:
        """published 对所有人可见；removed 仅作者与 admin（404 不泄漏存在性）。"""
        if row.status == CodeShareStatus.PUBLISHED:
            return
        is_owner = user is not None and row.user_id == user.id
        if not is_owner and not await self._is_admin(user):
            raise APIError(RESOURCE_NOT_FOUND, "代码分享不存在", 404)

    async def _require_codes_enabled(self) -> None:
        if not await self._feature_enabled("codes"):
            raise APIError(RESOURCE_STATE_CONFLICT, "代码广场功能未开放", 409)

    async def _code_share_detail_out(self, row: CodeShare, author: AuthorBrief) -> CodeShareDetail:
        return CodeShareDetail(
            id=row.id,
            author=author,
            title=row.title,
            language=row.language,
            description_excerpt=_code_share_excerpt(row),
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
            description=row.description,
            code=row.code,
        )

    async def list_code_shares(
        self,
        user: User | None,
        page: int,
        page_size: int,
        keyword: str | None,
        language: str | None,
        mine: bool,
    ) -> PaginatedResponse[CodeShareSummary]:
        author_id = None
        if mine:
            if user is None:
                raise APIError(AUTH_NOT_LOGGED_IN, "查看我的分享需要登录", 401)
            author_id = user.id
        rows, total = await self.code_shares.list_public(
            page, page_size, keyword, language, author_id
        )
        authors = await self._author_briefs([r.user_id for r in rows])
        items = [
            CodeShareSummary(
                id=row.id,
                author=authors.get(
                    row.user_id, AuthorBrief(id=row.user_id, nickname=_UNKNOWN_AUTHOR_NICKNAME)
                ),
                title=row.title,
                language=row.language,
                description_excerpt=_code_share_excerpt(row),
                status=row.status,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return PaginatedResponse[CodeShareSummary](
            items=items, total=total, page=page, page_size=page_size
        )

    async def get_code_share(self, share_id: uuid.UUID, user: User | None) -> CodeShareDetail:
        row = await self._require_code_share(share_id)
        await self._require_code_share_readable(row, user)
        authors = await self._author_briefs([row.user_id])
        return await self._code_share_detail_out(
            row,
            author=authors.get(
                row.user_id, AuthorBrief(id=row.user_id, nickname=_UNKNOWN_AUTHOR_NICKNAME)
            ),
        )

    async def create_code_share(self, user: User, body: CodeShareCreate) -> CodeShareDetail:
        await self._require_codes_enabled()
        await _claim_cooldown("code", user.id, CODE_SHARE_CREATE_COOLDOWN_SECONDS)
        row = await self.code_shares.create(
            CodeShare(
                user_id=user.id,
                title=body.title,
                description=body.description,
                language=CodeShareLanguage(body.language),
                code=body.code,
            )
        )
        return await self._code_share_detail_out(row, AuthorBrief.model_validate(user))

    async def remove_code_share(self, share_id: uuid.UUID, user: User) -> None:
        """下架（owner / admin；幂等；恢复仅经 admin 端点）。"""
        await self._require_codes_enabled()
        row = await self._require_code_share(share_id)
        is_owner = row.user_id == user.id
        if not is_owner and not await self._is_admin(user):
            raise APIError(AUTH_FORBIDDEN, "无权限操作他人分享", 403)
        if row.status != CodeShareStatus.REMOVED:
            row.status = CodeShareStatus.REMOVED
            row.updated_at = datetime.now()
            await self.db.flush()

    # ---- 管理端（admin）----

    async def admin_list_solutions(
        self,
        page: int,
        page_size: int,
        status: str | None,
        keyword: str | None,
        problem_id: uuid.UUID | None,
    ) -> PaginatedResponse[AdminSolutionOut]:
        rows, total = await self.solutions.list_admin(page, page_size, status, keyword, problem_id)
        counts = await self.solutions.count_comments([r.id for r in rows])
        authors = await self._author_briefs([r.user_id for r in rows])
        titles = await ProblemRepository(self.db).get_titles(list({r.problem_id for r in rows}))
        items = [
            AdminSolutionOut(
                id=row.id,
                problem=ProblemBrief(
                    id=row.problem_id, title=titles.get(row.problem_id, "未知题目")
                ),
                author=authors.get(
                    row.user_id, AuthorBrief(id=row.user_id, nickname=_UNKNOWN_AUTHOR_NICKNAME)
                ),
                title=row.title,
                excerpt=row.content[:EXCERPT_MAX_CHARS],
                status=row.status,
                comment_count=counts.get(row.id, 0),
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return PaginatedResponse[AdminSolutionOut](
            items=items, total=total, page=page, page_size=page_size
        )

    async def admin_get_solution(self, solution_id: uuid.UUID) -> AdminSolutionOut:
        """题解管理详情（举报处理页按 id 直接打开预览，无需先入列表）。"""
        row = await self._require_solution(solution_id)
        counts = await self.solutions.count_comments([row.id])
        authors = await self._author_briefs([row.user_id])
        titles = await ProblemRepository(self.db).get_titles([row.problem_id])
        return AdminSolutionOut(
            id=row.id,
            problem=ProblemBrief(id=row.problem_id, title=titles.get(row.problem_id, "未知题目")),
            author=authors.get(
                row.user_id, AuthorBrief(id=row.user_id, nickname=_UNKNOWN_AUTHOR_NICKNAME)
            ),
            title=row.title,
            excerpt=row.content[:EXCERPT_MAX_CHARS],
            status=row.status,
            comment_count=counts.get(row.id, 0),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def admin_set_solution_status(self, solution_id: uuid.UUID, status: str) -> None:
        """下架 / 恢复（removed ⇄ published）；草稿不经管理端流转（作者自行发布）。"""
        row = await self._require_solution(solution_id)
        if row.status == SolutionStatus.DRAFT:
            raise APIError(RESOURCE_STATE_CONFLICT, "草稿题解仅作者可见，请由作者自行发布", 409)
        if row.status != status:
            row.status = status
            row.updated_at = datetime.now()
            await self.db.flush()

    async def admin_set_comment_status(self, comment_id: uuid.UUID, is_deleted: bool) -> None:
        row = await self.comments.get_by_id(comment_id)
        if row is None:
            raise APIError(RESOURCE_NOT_FOUND, "评论不存在", 404)
        if row.is_deleted != is_deleted:
            row.is_deleted = is_deleted
            row.updated_at = datetime.now()
            await self.db.flush()

    async def admin_get_comment(self, comment_id: uuid.UUID) -> CommentAdminOut:
        """评论管理上下文（举报处理页定位所属题解，community.md）。"""
        row = await self.comments.get_by_id(comment_id)
        if row is None:
            raise APIError(RESOURCE_NOT_FOUND, "评论不存在", 404)
        return CommentAdminOut(
            id=row.id,
            target_type=row.target_type,
            target_id=row.target_id,
            content=row.content,
            is_deleted=row.is_deleted,
            created_at=row.created_at,
        )

    async def admin_list_code_shares(
        self,
        page: int,
        page_size: int,
        status: str | None,
        keyword: str | None,
        language: str | None,
    ) -> PaginatedResponse[AdminCodeShareOut]:
        rows, total = await self.code_shares.list_admin(page, page_size, status, keyword, language)
        authors = await self._author_briefs([r.user_id for r in rows])
        items = [
            AdminCodeShareOut(
                id=row.id,
                author=authors.get(
                    row.user_id, AuthorBrief(id=row.user_id, nickname=_UNKNOWN_AUTHOR_NICKNAME)
                ),
                title=row.title,
                language=row.language,
                excerpt=_code_share_excerpt(row),
                status=row.status,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return PaginatedResponse[AdminCodeShareOut](
            items=items, total=total, page=page, page_size=page_size
        )

    async def admin_get_code_share(self, share_id: uuid.UUID) -> AdminCodeShareOut:
        """代码分享管理详情（举报处理页按 id 直接打开预览）。"""
        row = await self._require_code_share(share_id)
        authors = await self._author_briefs([row.user_id])
        return AdminCodeShareOut(
            id=row.id,
            author=authors.get(
                row.user_id, AuthorBrief(id=row.user_id, nickname=_UNKNOWN_AUTHOR_NICKNAME)
            ),
            title=row.title,
            language=row.language,
            excerpt=_code_share_excerpt(row),
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def admin_set_code_share_status(self, share_id: uuid.UUID, status: str) -> None:
        """下架 / 恢复（removed ⇄ published）。"""
        row = await self._require_code_share(share_id)
        if row.status != status:
            row.status = status
            row.updated_at = datetime.now()
            await self.db.flush()

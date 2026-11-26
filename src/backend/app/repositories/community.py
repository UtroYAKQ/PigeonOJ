"""社区仓储：Solution / Comment / CodeShare 数据访问（纯 CRUD，docs/contracts/community.md）。"""
from __future__ import annotations

import uuid

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.enums import CodeShareStatus, CommentTargetType, SolutionStatus
from app.models.community import CodeShare, Comment, Solution


class SolutionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, solution_id: uuid.UUID) -> Solution | None:
        return await self.db.get(Solution, solution_id)

    async def get_by_ids(self, solution_ids: list[uuid.UUID]) -> list[Solution]:
        """批量读取题解行（举报摘要回填用）。"""
        if not solution_ids:
            return []
        stmt = select(Solution).where(Solution.id.in_(solution_ids))
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(self, solution: Solution) -> Solution:
        self.db.add(solution)
        await self.db.flush()
        return solution

    async def _page(
        self, conditions: list, page: int, page_size: int
    ) -> tuple[list[Solution], int]:
        count_stmt = select(func.count()).select_from(Solution).where(*conditions)
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = (
            select(Solution)
            .where(*conditions)
            .order_by(Solution.updated_at.desc(), Solution.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, int(total)

    async def list_for_problem(
        self,
        problem_id: uuid.UUID,
        page: int,
        page_size: int,
        keyword: str | None,
        author_id: uuid.UUID | None = None,
    ) -> tuple[list[Solution], int]:
        """题解分享列表：缺省仅 published；author_id 非空为「我的题解」（本人全状态）。"""
        conditions: list = [Solution.problem_id == problem_id]
        if author_id is not None:
            conditions.append(Solution.user_id == author_id)
        else:
            conditions.append(Solution.status == SolutionStatus.PUBLISHED)
        if keyword:
            conditions.append(Solution.title.ilike(f"%{keyword}%"))
        return await self._page(conditions, page, page_size)

    async def list_admin(
        self,
        page: int,
        page_size: int,
        status: str | None,
        keyword: str | None,
        problem_id: uuid.UUID | None,
    ) -> tuple[list[Solution], int]:
        conditions: list = []
        if status:
            conditions.append(Solution.status == status)
        if problem_id is not None:
            conditions.append(Solution.problem_id == problem_id)
        if keyword:
            conditions.append(
                or_(Solution.title.ilike(f"%{keyword}%"), Solution.content.ilike(f"%{keyword}%"))
            )
        return await self._page(conditions, page, page_size)

    async def count_comments(self, solution_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """题解未删评论总数（一级 + 回复；docs/contracts/community.md 列表聚合口径）。"""
        if not solution_ids:
            return {}
        stmt = (
            select(Comment.target_id, func.count())
            .where(
                Comment.target_type == CommentTargetType.SOLUTION,
                Comment.target_id.in_(solution_ids),
                Comment.is_deleted.is_(False),
            )
            .group_by(Comment.target_id)
        )
        return {row[0]: int(row[1]) for row in (await self.db.execute(stmt)).all()}


class CommentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, comment_id: uuid.UUID) -> Comment | None:
        return await self.db.get(Comment, comment_id)

    async def get_by_ids(self, comment_ids: list[uuid.UUID]) -> list[Comment]:
        """批量读取评论行（举报摘要回填用）。"""
        if not comment_ids:
            return []
        stmt = select(Comment).where(Comment.id.in_(comment_ids))
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(self, comment: Comment) -> Comment:
        self.db.add(comment)
        await self.db.flush()
        return comment

    @staticmethod
    def _ordered(stmt):
        return stmt.order_by(Comment.created_at.asc(), Comment.id.asc())

    async def list_top(
        self,
        target_type: str,
        target_id: uuid.UUID,
        page: int,
        page_size: int,
        include_deleted: bool = False,
    ) -> tuple[list[Comment], int]:
        """一级评论分页（升序）。

        公开口径：软删行保留为占位（存在未删回复时），否则整行隐藏——
        由「存在未删回复」的相关 exists 子查询表达。
        """
        conditions: list = [
            Comment.target_type == target_type,
            Comment.target_id == target_id,
            Comment.parent_id.is_(None),
        ]
        if not include_deleted:
            reply = aliased(Comment)
            conditions.append(
                or_(
                    Comment.is_deleted.is_(False),
                    exists(
                        select(1).where(
                            reply.parent_id == Comment.id, reply.is_deleted.is_(False)
                        )
                    ),
                )
            )
        count_stmt = select(func.count()).select_from(Comment).where(*conditions)
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = self._ordered(select(Comment).where(*conditions)).offset(
            (page - 1) * page_size
        ).limit(page_size)
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, int(total)

    async def list_replies(
        self,
        parent_id: uuid.UUID,
        page: int,
        page_size: int,
        include_deleted: bool = False,
    ) -> tuple[list[Comment], int]:
        """指定一级评论的回复分页（升序；admin include_deleted 含软删行）。"""
        conditions: list = [Comment.parent_id == parent_id]
        if not include_deleted:
            conditions.append(Comment.is_deleted.is_(False))
        count_stmt = select(func.count()).select_from(Comment).where(*conditions)
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = self._ordered(select(Comment).where(*conditions)).offset(
            (page - 1) * page_size
        ).limit(page_size)
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, int(total)

    async def replies_for_parents(
        self, parent_ids: list[uuid.UUID], include_deleted: bool = False
    ) -> dict[uuid.UUID, list[Comment]]:
        """一级评论页内回复预览：按 parent 分组（升序），service 侧截断前 N 条。"""
        if not parent_ids:
            return {}
        stmt = self._ordered(select(Comment).where(Comment.parent_id.in_(parent_ids)))
        if not include_deleted:
            stmt = stmt.where(Comment.is_deleted.is_(False))
        grouped: dict[uuid.UUID, list[Comment]] = {}
        for row in (await self.db.execute(stmt)).scalars().all():
            grouped.setdefault(row.parent_id, []).append(row)
        return grouped

    async def count_replies(self, parent_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """一级评论的未删回复数（软删占位行的 reply_count 同口径）。"""
        if not parent_ids:
            return {}
        stmt = (
            select(Comment.parent_id, func.count())
            .where(Comment.parent_id.in_(parent_ids), Comment.is_deleted.is_(False))
            .group_by(Comment.parent_id)
        )
        return {row[0]: int(row[1]) for row in (await self.db.execute(stmt)).all()}


class CodeShareRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, share_id: uuid.UUID) -> CodeShare | None:
        return await self.db.get(CodeShare, share_id)

    async def get_by_ids(self, share_ids: list[uuid.UUID]) -> list[CodeShare]:
        """批量读取分享行（举报摘要回填用）。"""
        if not share_ids:
            return []
        stmt = select(CodeShare).where(CodeShare.id.in_(share_ids))
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(self, share: CodeShare) -> CodeShare:
        self.db.add(share)
        await self.db.flush()
        return share

    async def _page(
        self, conditions: list, page: int, page_size: int
    ) -> tuple[list[CodeShare], int]:
        count_stmt = select(func.count()).select_from(CodeShare).where(*conditions)
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = (
            select(CodeShare)
            .where(*conditions)
            .order_by(CodeShare.created_at.desc(), CodeShare.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, int(total)

    async def list_public(
        self,
        page: int,
        page_size: int,
        keyword: str | None,
        language: str | None,
        author_id: uuid.UUID | None = None,
    ) -> tuple[list[CodeShare], int]:
        """广场列表：缺省仅 published + 过滤进行中比赛关联题；
        author_id 非空为「我的分享」（本人全状态，不过滤比赛——作者本人可见）。"""
        conditions: list = []
        if author_id is not None:
            conditions.append(CodeShare.user_id == author_id)
        else:
            conditions.append(CodeShare.status == CodeShareStatus.PUBLISHED)
        if language:
            conditions.append(CodeShare.language == language)
        if keyword:
            conditions.append(
                or_(
                    CodeShare.title.ilike(f"%{keyword}%"),
                    CodeShare.description.ilike(f"%{keyword}%"),
                )
            )
        return await self._page(conditions, page, page_size)

    async def list_admin(
        self,
        page: int,
        page_size: int,
        status: str | None,
        keyword: str | None,
        language: str | None,
    ) -> tuple[list[CodeShare], int]:
        conditions: list = []
        if status:
            conditions.append(CodeShare.status == status)
        if language:
            conditions.append(CodeShare.language == language)
        if keyword:
            conditions.append(
                or_(
                    CodeShare.title.ilike(f"%{keyword}%"),
                    CodeShare.description.ilike(f"%{keyword}%"),
                )
            )
        return await self._page(conditions, page, page_size)

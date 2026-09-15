"""团队域仓储：Team / TeamMember / TeamMemberApplication 数据访问。"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import TeamMemberStatus, TeamStatus, TeamVisibility
from app.models.team import Team, TeamMember, TeamMemberApplication
from app.models.user import User


class TeamRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, team_id: uuid.UUID) -> Team | None:
        return await self.db.get(Team, team_id)

    async def create(self, team: Team) -> Team:
        self.db.add(team)
        await self.db.flush()
        return team

    async def get_active_member(
        self, team_id: uuid.UUID, user_id: uuid.UUID
    ) -> TeamMember | None:
        stmt = select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
            TeamMember.status == TeamMemberStatus.ACTIVE,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def active_member_team_ids(
        self, user_id: uuid.UUID, team_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        """用户在这些团队中在册（team_members.active）的团队 id 集合。

        成员判定唯一口径（与 get_detail 的 get_active_member 一致）；
        user_roles 角色行不作为成员依据（历史脏数据会导致卡片态与详情权限不一致）。
        """
        if not team_ids:
            return set()
        stmt = select(TeamMember.team_id).where(
            TeamMember.team_id.in_(team_ids),
            TeamMember.user_id == user_id,
            TeamMember.status == TeamMemberStatus.ACTIVE,
        )
        return set((await self.db.execute(stmt)).scalars().all())

    async def get_application(self, application_id: uuid.UUID) -> TeamMemberApplication | None:
        return await self.db.get(TeamMemberApplication, application_id)

    async def get_pending_application(
        self, team_id: uuid.UUID, user_id: uuid.UUID
    ) -> TeamMemberApplication | None:
        from app.enums import TeamApplicationStatus

        stmt = select(TeamMemberApplication).where(
            TeamMemberApplication.team_id == team_id,
            TeamMemberApplication.user_id == user_id,
            TeamMemberApplication.status == TeamApplicationStatus.PENDING,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_members(
        self,
        team_id: uuid.UUID,
        status: str | None,
        page: int,
        page_size: int,
        keyword: str | None = None,
    ) -> tuple[list[tuple[TeamMember, User]], int]:
        """成员列表（join 用户，入队时间倒序分页；status 缺省 = 在册成员；
        keyword 模糊匹配昵称，docs/contracts/teams.md）。"""
        conditions = [TeamMember.team_id == team_id]
        if status:
            conditions.append(TeamMember.status == status)
        else:
            conditions.append(TeamMember.status == TeamMemberStatus.ACTIVE)
        if keyword:
            conditions.append(User.nickname.ilike(f"%{keyword}%"))
        total = (
            await self.db.scalar(
                select(func.count())
                .select_from(TeamMember)
                .join(User, User.id == TeamMember.user_id)
                .where(*conditions)
            )
        ) or 0
        rows = (
            await self.db.execute(
                select(TeamMember, User)
                .join(User, User.id == TeamMember.user_id)
                .where(*conditions)
                .order_by(TeamMember.joined_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [(member, user) for member, user in rows], int(total)

    async def list_applications(
        self, team_id: uuid.UUID, status: str | None, page: int, page_size: int
    ) -> tuple[list[tuple[TeamMemberApplication, User]], int]:
        """申请列表（join 申请人，申请时间倒序分页；status 缺省 = pending）。"""
        from app.enums import TeamApplicationStatus

        conditions = [TeamMemberApplication.team_id == team_id]
        if status:
            conditions.append(TeamMemberApplication.status == status)
        else:
            conditions.append(TeamMemberApplication.status == TeamApplicationStatus.PENDING)
        total = (
            await self.db.scalar(
                select(func.count())
                .select_from(TeamMemberApplication)
                .join(User, User.id == TeamMemberApplication.user_id)
                .where(*conditions)
            )
        ) or 0
        rows = (
            await self.db.execute(
                select(TeamMemberApplication, User)
                .join(User, User.id == TeamMemberApplication.user_id)
                .where(*conditions)
                .order_by(TeamMemberApplication.applied_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [(application, user) for application, user in rows], int(total)

    async def count_active_members_by_team(
        self, team_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, int]:
        """批量统计各团队在册成员数（我的团队列表展示用）。"""
        if not team_ids:
            return {}
        stmt = (
            select(TeamMember.team_id, func.count())
            .where(
                TeamMember.team_id.in_(team_ids),
                TeamMember.status == TeamMemberStatus.ACTIVE,
            )
            .group_by(TeamMember.team_id)
        )
        return {tid: int(count) for tid, count in (await self.db.execute(stmt)).all()}

    async def list_teams_of_user(
        self, user_id: uuid.UUID, page: int, page_size: int, keyword: str | None = None
    ) -> tuple[list[Team], int]:
        """我的团队列表（在册成员；按创建时间倒序分页，keyword 模糊匹配团队名称）。"""
        conditions = [
            Team.id == TeamMember.team_id,
            TeamMember.user_id == user_id,
            TeamMember.status == TeamMemberStatus.ACTIVE,
            Team.status == TeamStatus.ACTIVE,
        ]
        if keyword:
            conditions.append(Team.name.ilike(f"%{keyword}%"))
        total = (
            await self.db.scalar(
                select(func.count()).select_from(Team).join(TeamMember, Team.id == TeamMember.team_id).where(*conditions)
            )
        ) or 0
        rows = list(
            (
                await self.db.execute(
                    select(Team)
                    .join(TeamMember, Team.id == TeamMember.team_id)
                    .where(*conditions)
                    .order_by(Team.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        return rows, int(total)

    async def list_public(
        self, page: int, page_size: int, keyword: str | None = None
    ) -> tuple[list[Team], int]:
        """团队中心公开列表：仅 public + active（私有团队不进任何公开列表，
        docs/contracts/teams.md）；创建时间倒序，keyword 模糊匹配团队名称。"""
        conditions = [
            Team.visibility == TeamVisibility.PUBLIC,
            Team.status == TeamStatus.ACTIVE,
        ]
        if keyword:
            conditions.append(Team.name.ilike(f"%{keyword}%"))
        total = (
            await self.db.scalar(select(func.count()).select_from(Team).where(*conditions)) or 0
        )
        rows = list(
            (
                await self.db.execute(
                    select(Team)
                    .where(*conditions)
                    .order_by(Team.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        return rows, int(total)

    async def list_all(
        self,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: TeamStatus | None = None,
    ) -> tuple[list[tuple[Team, str | None]], int]:
        """团队管理列表（admin 全量，创建时间倒序；keyword 模糊团队名称、status 过滤；
        join 创建人带昵称，docs/contracts/teams.md 管理端）。"""
        conditions: list = []
        if keyword:
            conditions.append(Team.name.ilike(f"%{keyword}%"))
        if status:
            conditions.append(Team.status == status)
        total = (
            await self.db.scalar(select(func.count()).select_from(Team).where(*conditions)) or 0
        )
        rows = (
            await self.db.execute(
                select(Team, User.nickname)
                .join(User, User.id == Team.creator_id)
                .where(*conditions)
                .order_by(Team.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [(team, nickname) for team, nickname in rows], int(total)

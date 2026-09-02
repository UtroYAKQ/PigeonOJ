"""团队域仓储：Team / TeamMember / TeamMemberApplication 数据访问。"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import TeamMemberStatus, TeamStatus
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
        self, team_id: uuid.UUID, status: str | None, page: int, page_size: int
    ) -> tuple[list[tuple[TeamMember, User]], int]:
        """成员列表（join 用户，入队时间倒序分页；status 缺省 = 在册成员）。"""
        conditions = [TeamMember.team_id == team_id]
        if status:
            conditions.append(TeamMember.status == status)
        else:
            conditions.append(TeamMember.status == TeamMemberStatus.ACTIVE)
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

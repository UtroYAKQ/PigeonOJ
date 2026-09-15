"""组织域仓储：Organization / OrgMember 数据访问。"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import OrgMemberStatus, OrgStatus, TeamStatus
from app.models.org import Organization, OrgMember
from app.models.team import Team
from app.models.user import User


class OrgRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, org_id: uuid.UUID) -> Organization | None:
        return await self.db.get(Organization, org_id)

    async def get_by_name(self, name: str) -> Organization | None:
        stmt = select(Organization).where(Organization.name == name)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create(self, org: Organization) -> Organization:
        self.db.add(org)
        await self.db.flush()
        return org

    async def get_active_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrgMember | None:
        stmt = select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == user_id,
            OrgMember.status == OrgMemberStatus.ACTIVE,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_members(
        self,
        org_id: uuid.UUID,
        status: str | None,
        page: int,
        page_size: int,
        keyword: str | None = None,
    ) -> tuple[list[tuple[OrgMember, User]], int]:
        """成员列表（join 用户，加入时间倒序分页；status 缺省 = 在册成员；
        keyword 模糊匹配昵称，docs/contracts/orgs.md）。"""
        conditions = [OrgMember.org_id == org_id]
        if status:
            conditions.append(OrgMember.status == status)
        else:
            conditions.append(OrgMember.status == OrgMemberStatus.ACTIVE)
        if keyword:
            conditions.append(User.nickname.ilike(f"%{keyword}%"))
        total = (
            await self.db.scalar(
                select(func.count())
                .select_from(OrgMember)
                .join(User, User.id == OrgMember.user_id)
                .where(*conditions)
            )
        ) or 0
        rows = (
            await self.db.execute(
                select(OrgMember, User)
                .join(User, User.id == OrgMember.user_id)
                .where(*conditions)
                .order_by(OrgMember.joined_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [(member, user) for member, user in rows], int(total)

    async def count_active_members_by_org(
        self, org_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, int]:
        """批量统计各组织在册成员数（组织列表展示用）。"""
        if not org_ids:
            return {}
        stmt = (
            select(OrgMember.org_id, func.count())
            .where(
                OrgMember.org_id.in_(org_ids),
                OrgMember.status == OrgMemberStatus.ACTIVE,
            )
            .group_by(OrgMember.org_id)
        )
        return {oid: int(count) for oid, count in (await self.db.execute(stmt)).all()}

    async def count_active_teams_by_org(
        self, org_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, int]:
        """批量统计各组织名下在册团队数。"""
        if not org_ids:
            return {}
        stmt = (
            select(Team.org_id, func.count())
            .where(
                Team.org_id.in_(org_ids),
                Team.status == TeamStatus.ACTIVE,
            )
            .group_by(Team.org_id)
        )
        return {oid: int(count) for oid, count in (await self.db.execute(stmt)).all()}

    async def list_orgs_of_user(
        self, user_id: uuid.UUID, page: int, page_size: int, keyword: str | None = None
    ) -> tuple[list[Organization], int]:
        """我的组织列表（在册成员；创建时间倒序分页，keyword 模糊匹配组织名称）。"""
        conditions = [
            Organization.id == OrgMember.org_id,
            OrgMember.user_id == user_id,
            OrgMember.status == OrgMemberStatus.ACTIVE,
            Organization.status == OrgStatus.ACTIVE,
        ]
        if keyword:
            conditions.append(Organization.name.ilike(f"%{keyword}%"))
        total = (
            await self.db.scalar(
                select(func.count())
                .select_from(Organization)
                .join(OrgMember, Organization.id == OrgMember.org_id)
                .where(*conditions)
            )
        ) or 0
        rows = list(
            (
                await self.db.execute(
                    select(Organization)
                    .join(OrgMember, Organization.id == OrgMember.org_id)
                    .where(*conditions)
                    .order_by(Organization.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        return rows, int(total)

    async def list_teams_of_org(
        self,
        org_id: uuid.UUID,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Team], int]:
        """组织名下团队列表（创建时间倒序分页，keyword 模糊匹配团队名称）。"""
        conditions = [Team.org_id == org_id]
        if status:
            conditions.append(Team.status == status)
        else:
            conditions.append(Team.status == TeamStatus.ACTIVE)
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
        status: str | None = None,
    ) -> tuple[list[tuple[Organization, str | None]], int]:
        """组织管理列表（admin 全量，创建时间倒序；keyword 模糊组织名称、status 过滤；
        join 创建操作人带昵称，docs/contracts/orgs.md 管理端）。"""
        conditions: list = []
        if keyword:
            conditions.append(Organization.name.ilike(f"%{keyword}%"))
        if status:
            conditions.append(Organization.status == status)
        total = (
            await self.db.scalar(
                select(func.count()).select_from(Organization).where(*conditions)
            )
            or 0
        )
        rows = (
            await self.db.execute(
                select(Organization, User.nickname)
                .join(User, User.id == Organization.created_by)
                .where(*conditions)
                .order_by(Organization.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [(org, nickname) for org, nickname in rows], int(total)

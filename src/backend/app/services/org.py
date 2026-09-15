"""组织域服务：创建 / 编辑 / 解散 / 成员与组织角色授权管理 / 组织内建团。

组织角色经 user_roles（scope='org'、object_id=org_id）授权（docs/contracts/orgs.md）；
组织是内容的所有者——组织题库管理权按组织成员资格判定（见 problem.py 组织分支）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    APIError,
    AUTH_FORBIDDEN,
    ORG_LAST_ADMIN,
    RESOURCE_DUPLICATE,
    RESOURCE_NOT_FOUND,
    RESOURCE_STATE_CONFLICT,
)
from app.enums import (
    OrgMemberStatus,
    OrgStatus,
    ProblemStatus,
    TeamMemberStatus,
    TeamVisibility,
    UserStatus,
)
from app.models.org import Organization, OrgMember
from app.models.problem import Problem
from app.models.team import Team, TeamMember
from app.models.user import Role, User, UserRole
from app.repositories.org import OrgRepository
from app.repositories.team import TeamRepository
from app.repositories.user import RoleRepository
from app.schemas.org import (
    OrgAdminDetail,
    OrgAdminFlag,
    OrgAdminSummary,
    OrgCreate,
    OrgDetail,
    OrgMemberAdd,
    OrgMemberNote,
    OrgMemberOut,
    OrgSummary,
    OrgTeamAssign,
    OrgUpdate,
)
from app.schemas.team import TeamCreate, TeamSummary
from app.services.team import summarize_teams  # 团队列表装配复用，避免同构循环

# 组织角色 code（roles 种子，docs/contracts/orgs.md）
ROLE_ADMIN = "org_admin"
ROLE_MEMBER = "org_member"


class OrgService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.orgs = OrgRepository(db)
        self.roles = RoleRepository(db)
        self.teams = TeamRepository(db)

    # ---------------- 权限辅助 ----------------

    async def _is_site_admin(self, user: User) -> bool:
        from app.core.dependency import get_user_role_codes

        return "admin" in await get_user_role_codes(self.db, user.id)

    async def _org_or_404(self, org_id: uuid.UUID) -> Organization:
        org = await self.orgs.get_by_id(org_id)
        if org is None:
            raise APIError(RESOURCE_NOT_FOUND, "组织不存在", 404)
        return org

    async def _active_org_or_error(self, org_id: uuid.UUID) -> Organization:
        org = await self._org_or_404(org_id)
        if org.status != OrgStatus.ACTIVE:
            raise APIError(RESOURCE_STATE_CONFLICT, "组织已解散", 409)
        return org

    async def _require_org_roles(
        self, user: User, org_id: uuid.UUID, *, level: str = "admin"
    ) -> set[str]:
        """校验组织角色：level='admin' 组织管理员；'member' 任意组织角色。

        站点 admin 视同拥有全部组织管理权（docs/contracts/orgs.md）。
        """
        if await self._is_site_admin(user):
            return {ROLE_ADMIN, ROLE_MEMBER}
        codes = set(await self.roles.get_org_role_codes(user.id, org_id))
        if level == "admin":
            if ROLE_ADMIN not in codes:
                raise APIError(AUTH_FORBIDDEN, "仅组织管理员可执行该操作", 403)
        else:
            if not ({ROLE_ADMIN, ROLE_MEMBER} & codes):
                raise APIError(AUTH_FORBIDDEN, "非组织成员", 403)
        return codes

    async def has_org_roles(
        self, user: User | None, org_id: uuid.UUID, *, level: str = "member"
    ) -> bool:
        """无异常版本的组织角色检查（其他模块判断组织题库可见性 / 管理权用）。"""
        if user is None:
            return False
        try:
            await self._require_org_roles(user, org_id, level=level)
        except APIError:
            return False
        return True

    async def require_roles(
        self, user: User, org_id: uuid.UUID, *, level: str = "member"
    ) -> Organization:
        """路由层组织角色门：校验组织存在（404）+ active（解散 409）+ 角色（2003）。"""
        org = await self._active_org_or_error(org_id)
        await self._require_org_roles(user, org.id, level=level)
        return org

    async def _my_role(self, org: Organization, user_id: uuid.UUID) -> str | None:
        member = await self.orgs.get_active_member(org.id, user_id)
        if member is None:
            return None
        codes = set(await self.roles.get_org_role_codes(user_id, org.id))
        return "admin" if ROLE_ADMIN in codes else "member"

    @staticmethod
    def _summary(org: Organization, member_count: int, team_count: int, my_role: str | None) -> OrgSummary:
        return OrgSummary(
            id=org.id,
            name=org.name,
            description=org.description,
            avatar_url=org.avatar_url,
            created_at=org.created_at,
            member_count=member_count,
            team_count=team_count,
            my_role=my_role,
        )

    # ---------------- 创建 / 编辑 / 详情 / 列表 ----------------

    async def create(self, user: User, body: OrgCreate) -> OrgDetail:
        """创建组织（站点 admin）：创建者自动成为组织管理员；可同时任命其他初始组织管理员。"""
        if not await self._is_site_admin(user):
            raise APIError(AUTH_FORBIDDEN, "仅系统管理员可创建组织", 403)
        if await self.orgs.get_by_name(body.name) is not None:
            raise APIError(RESOURCE_DUPLICATE, "组织名称已存在", 409)
        admin_ids = list(dict.fromkeys(body.admin_user_ids))
        for uid in admin_ids:
            target = await self.db.get(User, uid)
            if target is None or target.status != UserStatus.ACTIVE:
                raise APIError(RESOURCE_NOT_FOUND, "任命的组织管理员不存在或不可用", 404)
        org = await self.orgs.create(
            Organization(
                name=body.name,
                description=body.description,
                avatar_url=body.avatar_url,
                created_by=user.id,
            )
        )
        # 创建者自动成为组织管理员（即使未在 admin_user_ids 中列出）
        all_admin_ids = list(dict.fromkeys([user.id, *admin_ids]))
        for uid in all_admin_ids:
            await self._upsert_member(org.id, uid, added_by=user.id)
            await self.roles.grant_org_role(uid, org.id, ROLE_ADMIN)
        return await self.admin_get_detail(org.id)

    async def get_detail(self, user: User, org_id: uuid.UUID) -> OrgDetail:
        """组织详情（组织成员可见，非成员 2003；站点 admin 免成员校验）。"""
        org = await self._org_or_404(org_id)
        if not await self.has_org_roles(user, org.id, level="member"):
            raise APIError(AUTH_FORBIDDEN, "非组织成员，无权查看", 403)
        member_counts, team_counts = await self._counts([org.id])
        return OrgDetail(
            **self._summary(
                org,
                member_counts.get(org.id, 0),
                team_counts.get(org.id, 0),
                await self._my_role(org, user.id),
            ).model_dump(),
            created_by=org.created_by,
            status=OrgStatus(org.status),
            disbanded_at=org.disbanded_at,
        )

    async def update(self, user: User, org_id: uuid.UUID, patch: OrgUpdate) -> OrgDetail:
        """编辑组织信息（org_admin；缺省不动）。"""
        org = await self._active_org_or_error(org_id)
        await self._require_org_roles(user, org.id, level="admin")
        if patch.name is not None and patch.name != org.name:
            if await self.orgs.get_by_name(patch.name) is not None:
                raise APIError(RESOURCE_DUPLICATE, "组织名称已存在", 409)
            org.name = patch.name
        if patch.description is not None:
            org.description = patch.description
        if patch.avatar_url is not None:
            org.avatar_url = patch.avatar_url
        await self.db.flush()
        return await self.get_detail(user, org.id)

    async def disband(self, user: User, org_id: uuid.UUID) -> None:
        """解散组织（软解散，仅站点 admin）：清理 org 授权与成员状态，题库题目归档。"""
        org = await self._org_or_404(org_id)
        if not await self._is_site_admin(user):
            raise APIError(AUTH_FORBIDDEN, "仅系统管理员可解散组织", 403)
        if org.status != OrgStatus.ACTIVE:
            raise APIError(RESOURCE_STATE_CONFLICT, "组织已解散", 409)
        org.status = OrgStatus.DISBANDED
        org.disbanded_at = datetime.now(timezone.utc)
        await self.roles.revoke_all_org_roles(org.id)
        await self.db.execute(
            update(OrgMember)
            .where(OrgMember.org_id == org.id, OrgMember.status == OrgMemberStatus.ACTIVE)
            .values(status=OrgMemberStatus.REMOVED, left_at=org.disbanded_at)
            .execution_options(synchronize_session=False)
        )
        # 组织题库题目默认归档（对齐团队解散语义）
        await self.db.execute(
            update(Problem)
            .where(
                Problem.org_id == org.id,
                Problem.status != ProblemStatus.ARCHIVED,
            )
            .values(status=ProblemStatus.ARCHIVED)
            .execution_options(synchronize_session=False)
        )
        await self.db.flush()

    async def list_mine(
        self, user: User, page: int, page_size: int, keyword: str | None = None
    ) -> tuple[list[OrgSummary], int]:
        """我的组织列表（在册成员；带成员数 / 团队数 / 我的角色）。"""
        rows, total = await self.orgs.list_orgs_of_user(user.id, page, page_size, keyword)
        member_counts = await self.orgs.count_active_members_by_org([o.id for o in rows])
        team_counts = await self.orgs.count_active_teams_by_org([o.id for o in rows])
        role_map = await self.roles.get_org_roles_for_orgs(user.id, [o.id for o in rows])
        items = []
        for org in rows:
            codes = role_map.get(org.id, set())
            my_role = "admin" if ROLE_ADMIN in codes else "member"
            items.append(
                self._summary(
                    org,
                    member_counts.get(org.id, 0),
                    team_counts.get(org.id, 0),
                    my_role,
                )
            )
        return items, total

    async def _counts(self, org_ids: list[uuid.UUID]) -> tuple[dict, dict]:
        member_counts = await self.orgs.count_active_members_by_org(org_ids)
        team_counts = await self.orgs.count_active_teams_by_org(org_ids)
        return member_counts, team_counts

    # ---------------- 成员管理 ----------------

    async def _upsert_member(self, org_id: uuid.UUID, user_id: uuid.UUID, added_by: uuid.UUID) -> None:
        """写入在册成员行：新成员插入；历史被移出成员复活（status 置回 active）。"""
        member = await self.orgs.get_active_member(org_id, user_id)
        if member is not None:
            return
        from sqlalchemy import select

        removed = (
            await self.db.execute(
                select(OrgMember).where(
                    OrgMember.org_id == org_id,
                    OrgMember.user_id == user_id,
                    OrgMember.status == OrgMemberStatus.REMOVED,
                )
            )
        ).scalar_one_or_none()
        if removed is not None:
            removed.status = OrgMemberStatus.ACTIVE
            removed.left_at = None
            removed.added_by = added_by
            removed.joined_at = datetime.now(timezone.utc)
        else:
            self.db.add(OrgMember(org_id=org_id, user_id=user_id, added_by=added_by))
        await self.db.flush()

    async def list_members(
        self,
        user: User,
        org_id: uuid.UUID,
        status: str | None,
        page: int,
        page_size: int,
        keyword: str | None = None,
    ) -> tuple[list[OrgMemberOut], int]:
        """成员列表（组织任意角色可查；站点 admin 免校验）。"""
        org = await self._org_or_404(org_id)
        await self._require_org_roles(user, org.id, level="member")
        return await self._assemble_members(org, status, page, page_size, keyword)

    async def admin_list_members(
        self,
        org_id: uuid.UUID,
        status: str | None,
        page: int,
        page_size: int,
        keyword: str | None = None,
    ) -> tuple[list[OrgMemberOut], int]:
        """成员列表（admin 管理视图，免成员校验）。"""
        org = await self._org_or_404(org_id)
        return await self._assemble_members(org, status, page, page_size, keyword)

    async def _assemble_members(
        self, org: Organization, status: str | None, page: int, page_size: int, keyword: str | None = None
    ) -> tuple[list[OrgMemberOut], int]:
        rows, total = await self.orgs.list_members(org.id, status, page, page_size, keyword)
        admin_rows = await self.db.execute(
            select(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserRole.scope == "org",
                UserRole.object_id == org.id,
                Role.code == ROLE_ADMIN,
            )
        )
        admin_ids = {row for row in admin_rows.scalars()}
        return [
            OrgMemberOut(
                user_id=member.user_id,
                nickname=member_user.nickname,
                avatar_url=member_user.avatar_url,
                status=OrgMemberStatus(member.status),
                joined_at=member.joined_at,
                is_admin=member.user_id in admin_ids,
                note=member.note,
            )
            for member, member_user in rows
        ], total

    async def add_members(self, user: User, org_id: uuid.UUID, body: OrgMemberAdd) -> None:
        """直接添加成员（org_admin 拉人，可批量；已在册跳过；激活组织成员授权）。"""
        org = await self._active_org_or_error(org_id)
        await self._require_org_roles(user, org.id, level="admin")
        user_ids = list(dict.fromkeys(body.user_ids))
        # 一次性校验目标用户存在且 active（避免逐用户 round-trip）
        rows = (await self.db.execute(select(User.id, User.status).where(User.id.in_(user_ids)))).all()
        active_ids = {uid for uid, status in rows if status == UserStatus.ACTIVE}
        missing = [uid for uid in user_ids if uid not in active_ids]
        if missing:
            raise APIError(RESOURCE_NOT_FOUND, "用户不存在或不可用", 404)
        # 批量 upsert 在册成员行：新成员插入 / 历史移出复活
        members = {
            m.user_id: m
            for m in (
                await self.db.execute(
                    select(OrgMember).where(
                        OrgMember.org_id == org.id,
                        OrgMember.user_id.in_(user_ids),
                    )
                )
            ).scalars()
        }
        now = datetime.now(timezone.utc)
        for uid in user_ids:
            member = members.get(uid)
            if member is not None and member.status != OrgMemberStatus.REMOVED:
                continue  # 已在册
            if member is not None:  # REMOVED：复活
                member.status = OrgMemberStatus.ACTIVE
                member.left_at = None
                member.added_by = user.id
                member.joined_at = now
            else:
                self.db.add(OrgMember(org_id=org.id, user_id=uid, added_by=user.id))
        await self.db.flush()
        await self.roles.grant_org_roles(user_ids, org.id, ROLE_MEMBER)

    async def remove_member(self, user: User, org_id: uuid.UUID, target_uid: uuid.UUID) -> None:
        """移出成员（org_admin；清理成员状态与组织授权；最后一名 org_admin 3004）。"""
        org = await self._org_or_404(org_id)
        await self._require_org_roles(user, org.id, level="admin")
        if target_uid == user.id:
            raise APIError(AUTH_FORBIDDEN, "不能移除自己", 403)
        member = await self.orgs.get_active_member(org.id, target_uid)
        if member is None:
            raise APIError(RESOURCE_NOT_FOUND, "成员不存在", 404)
        codes = set(await self.roles.get_org_role_codes(target_uid, org.id))
        if ROLE_ADMIN in codes and await self.roles.count_org_admins(org.id, exclude_user_id=target_uid) == 0:
            raise APIError(ORG_LAST_ADMIN, "组织至少保留一名管理员", 409)
        member.status = OrgMemberStatus.REMOVED
        member.left_at = datetime.now(timezone.utc)
        await self.roles.revoke_org_roles(target_uid, org.id, {ROLE_ADMIN, ROLE_MEMBER})

    async def set_admin(
        self, user: User, org_id: uuid.UUID, target_uid: uuid.UUID, body: OrgAdminFlag
    ) -> None:
        """授予 / 撤销组织管理员（org_admin 或站点 admin；最后一名 3004）。"""
        org = await self._org_or_404(org_id)
        await self._require_org_roles(user, org.id, level="admin")
        member = await self.orgs.get_active_member(org.id, target_uid)
        if member is None:
            raise APIError(RESOURCE_NOT_FOUND, "成员不存在", 404)
        if body.is_admin:
            await self.roles.grant_org_role(target_uid, org.id, ROLE_ADMIN)
        else:
            if await self.roles.count_org_admins(org.id, exclude_user_id=target_uid) == 0:
                raise APIError(ORG_LAST_ADMIN, "组织至少保留一名管理员", 409)
            await self.roles.revoke_org_roles(target_uid, org.id, {ROLE_ADMIN})

    async def set_member_note(
        self, user: User, org_id: uuid.UUID, target_uid: uuid.UUID, body: OrgMemberNote
    ) -> None:
        """设置成员备注：本人可备注自己；org_admin 可备注任意成员；空串 = 清除。"""
        org = await self._org_or_404(org_id)
        if target_uid != user.id:
            await self._require_org_roles(user, org.id, level="admin")
        member = await self.orgs.get_active_member(org.id, target_uid)
        if member is None:
            raise APIError(RESOURCE_NOT_FOUND, "成员不存在", 404)
        member.note = (body.note or "").strip() or None

    # ---------------- 组织内建团 ----------------

    async def create_team(self, user: User, org_id: uuid.UUID, body: TeamCreate) -> TeamSummary:
        """在组织内创建团队（org_admin；创建者自动 team_creator 并写入成员记录）。"""
        org = await self._active_org_or_error(org_id)
        await self._require_org_roles(user, org.id, level="admin")
        team = await self.teams.create(
            Team(
                name=body.name,
                description=body.description,
                avatar_url=body.avatar_url,
                visibility=body.visibility,
                creator_id=user.id,
                org_id=org.id,
            )
        )
        self.db.add(TeamMember(team_id=team.id, user_id=user.id, status=TeamMemberStatus.ACTIVE))
        await self.roles.grant_team_role(user.id, team.id, "team_creator")
        return TeamSummary(
            id=team.id,
            name=team.name,
            description=team.description,
            avatar_url=team.avatar_url,
            created_at=team.created_at,
            visibility=TeamVisibility(team.visibility),
            member_count=1,
            my_role="creator",
        )

    async def list_teams(
        self,
        user: User,
        org_id: uuid.UUID,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
    ) -> tuple[list[TeamSummary], int]:
        """组织名下团队列表（组织成员可见；带成员数与我的团队角色）。"""
        org = await self._org_or_404(org_id)
        await self._require_org_roles(user, org.id, level="member")
        rows, total = await self.orgs.list_teams_of_org(org.id, page, page_size, keyword, status)
        counts = await self.teams.count_active_members_by_team([t.id for t in rows])
        role_map = await self.roles.get_team_roles_for_teams(user.id, [t.id for t in rows])
        return summarize_teams(rows, counts, role_map, user=user), total

    # ---------------- 管理端视图（admin） ----------------

    async def admin_list(
        self,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
    ) -> tuple[list[OrgAdminSummary], int]:
        """组织管理列表（admin 全量，含已解散）：成员数 / 团队数 / 创建操作人昵称 / 状态。"""
        rows, total = await self.orgs.list_all(page, page_size, keyword=keyword, status=status)
        org_ids = [org.id for org, _ in rows]
        member_counts = await self.orgs.count_active_members_by_org(org_ids)
        team_counts = await self.orgs.count_active_teams_by_org(org_ids)
        return [
            OrgAdminSummary(
                **self._summary(
                    org,
                    member_counts.get(org.id, 0),
                    team_counts.get(org.id, 0),
                    None,
                ).model_dump(),
                status=OrgStatus(org.status),
                creator_nickname=nickname,
            )
            for org, nickname in rows
        ], total

    async def admin_get_detail(self, org_id: uuid.UUID) -> OrgAdminDetail:
        """组织管理详情（admin 免成员校验，含已解散）。"""
        org = await self._org_or_404(org_id)
        creator = await self.db.get(User, org.created_by)
        member_counts, team_counts = await self._counts([org.id])
        return OrgAdminDetail(
            **self._summary(
                org,
                member_counts.get(org.id, 0),
                team_counts.get(org.id, 0),
                None,
            ).model_dump(),
            created_by=org.created_by,
            status=OrgStatus(org.status),
            disbanded_at=org.disbanded_at,
            creator_nickname=creator.nickname if creator else None,
        )

    async def admin_assign_team(self, team_id: uuid.UUID, body: OrgTeamAssign) -> None:
        """存量团队指派组织（admin 迁移用；组织必须 active）。"""
        team = await self.teams.get_by_id(team_id)
        if team is None:
            raise APIError(RESOURCE_NOT_FOUND, "团队不存在", 404)
        org = await self._org_or_404(body.org_id)
        if org.status != OrgStatus.ACTIVE:
            raise APIError(RESOURCE_STATE_CONFLICT, "组织已解散", 409)
        team.org_id = org.id
        await self.db.flush()

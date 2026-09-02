"""团队域服务：创建 / 编辑 / 邀请 / 加入审批 / 成员与团队角色授权管理。

团队角色经 user_roles（scope='team'、object_id=team_id）授权（docs/contracts/teams.md）；
邀请链接存 Redis `team:invite:<token>`（不可撤销、可多人使用、无一次性限制）。
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    APIError,
    AUTH_FORBIDDEN,
    RESOURCE_DUPLICATE,
    RESOURCE_NOT_FOUND,
    RESOURCE_STATE_CONFLICT,
)
from app.core.redis import get_redis, redis_get_json, redis_set_json
from app.enums import TeamApplicationStatus, TeamMemberStatus, TeamStatus
from app.models.team import Team, TeamMember, TeamMemberApplication
from app.models.user import User
from app.repositories.team import TeamRepository
from app.repositories.user import RoleRepository
from app.schemas.team import (
    TeamAdminFlag,
    TeamApplicationOut,
    TeamApplicationReview,
    TeamApplicationSubmit,
    TeamCreate,
    TeamDetail,
    TeamInviteCreated,
    TeamInviteResolved,
    TeamMemberOut,
    TeamSummary,
    TeamUpdate,
)
from app.services.system_config import ConfigService

_INVITE_KEY_PREFIX = "team:invite:"
# 团队角色 code（roles 种子，docs/contracts/teams.md）
ROLE_CREATOR = "team_creator"
ROLE_ADMIN = "team_admin"
ROLE_MEMBER = "team_member"


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class TeamService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.teams = TeamRepository(db)
        self.roles = RoleRepository(db)
        self.config = ConfigService(db)

    # ---------------- 权限辅助 ----------------

    async def _team_or_404(self, team_id: uuid.UUID) -> Team:
        team = await self.teams.get_by_id(team_id)
        if team is None:
            raise APIError(RESOURCE_NOT_FOUND, "团队不存在", 404)
        return team

    async def _active_team_or_error(self, team_id: uuid.UUID) -> Team:
        team = await self._team_or_404(team_id)
        if team.status != TeamStatus.ACTIVE:
            raise APIError(RESOURCE_STATE_CONFLICT, "团队已解散", 409)
        return team

    async def _require_team_roles(
        self, user: User, team_id: uuid.UUID, *, level: str = "admin"
    ) -> set[str]:
        """校验团队角色：level='creator' 仅创建者；'admin' 创建者 / 管理员；
        'member' 任意团队角色（creator ⊇ admin ⊇ member）。"""
        codes = set(await self.roles.get_team_role_codes(user.id, team_id))
        if level == "creator":
            if ROLE_CREATOR not in codes:
                raise APIError(AUTH_FORBIDDEN, "仅团队创建者可执行该操作", 403)
        elif level == "admin":
            if not ({ROLE_CREATOR, ROLE_ADMIN} & codes):
                raise APIError(AUTH_FORBIDDEN, "无权限管理该团队", 403)
        else:
            if not ({ROLE_CREATOR, ROLE_ADMIN, ROLE_MEMBER} & codes):
                raise APIError(AUTH_FORBIDDEN, "非团队成员", 403)
        return codes

    @staticmethod
    def _is_creator(team: Team, user_id: uuid.UUID) -> bool:
        return team.creator_id == user_id

    # ---------------- 创建 / 编辑 / 详情 / 列表 ----------------

    async def create(self, user: User, body: TeamCreate) -> TeamSummary:
        """创建团队（admin/tutor 全局角色）：自动写创建者在册记录并授予 team_creator。"""
        from app.core.dependency import get_user_role_codes

        codes = await get_user_role_codes(self.db, user.id)
        if not ({"admin", "tutor"} & codes):
            raise APIError(AUTH_FORBIDDEN, "无权限创建团队", 403)
        team = await self.teams.create(
            Team(name=body.name, description=body.description, avatar_url=body.avatar_url, creator_id=user.id)
        )
        self.db.add(
            TeamMember(team_id=team.id, user_id=user.id, status=TeamMemberStatus.ACTIVE)
        )
        await self.roles.grant_team_role(user.id, team.id, ROLE_CREATOR)
        return TeamSummary(
            id=team.id,
            name=team.name,
            description=team.description,
            avatar_url=team.avatar_url,
            created_at=team.created_at,
            member_count=1,
            my_role="creator",
        )

    async def get_detail(self, user: User, team_id: uuid.UUID) -> TeamDetail:
        """团队详情（成员可见；非在册成员 2003）。"""
        team = await self._team_or_404(team_id)
        member = await self.teams.get_active_member(team.id, user.id)
        if member is None:
            raise APIError(AUTH_FORBIDDEN, "非团队成员，无权查看", 403)
        codes = set(await self.roles.get_team_role_codes(user.id, team.id))
        my_role = (
            "creator"
            if self._is_creator(team, user.id)
            else "admin" if ROLE_ADMIN in codes else "member"
        )
        count = await self.teams.count_active_members_by_team([team.id])
        return TeamDetail(
            id=team.id,
            name=team.name,
            description=team.description,
            avatar_url=team.avatar_url,
            created_at=team.created_at,
            member_count=count.get(team.id, 0),
            my_role=my_role,
            creator_id=team.creator_id,
            status=TeamStatus(team.status),
            disbanded_at=team.disbanded_at,
        )

    async def update(self, user: User, team_id: uuid.UUID, patch: TeamUpdate) -> TeamDetail:
        """编辑团队信息（team_creator / team_admin；缺省不动）。"""
        team = await self._active_team_or_error(team_id)
        await self._require_team_roles(user, team.id, level="admin")
        if patch.name is not None:
            team.name = patch.name
        if patch.description is not None:
            team.description = patch.description
        if patch.avatar_url is not None:
            team.avatar_url = patch.avatar_url
        await self.db.flush()
        return await self.get_detail(user, team.id)

    async def list_my_teams(
        self, user: User, page: int, page_size: int, keyword: str | None = None
    ) -> tuple[list[TeamSummary], int]:
        """我的团队列表（在册成员，创建时间倒序；带成员数与我的角色；keyword 模糊匹配团队名称）。"""
        rows, total = await self.teams.list_teams_of_user(user.id, page, page_size, keyword)
        counts = await self.teams.count_active_members_by_team([t.id for t in rows])
        role_map = await self.roles.get_team_roles_for_teams(user.id, [t.id for t in rows])
        items = []
        for team in rows:
            codes = role_map.get(team.id, set())
            my_role = (
                "creator"
                if self._is_creator(team, user.id)
                else "admin" if ROLE_ADMIN in codes else "member"
            )
            items.append(
                TeamSummary(
                    id=team.id,
                    name=team.name,
                    description=team.description,
                    avatar_url=team.avatar_url,
                    created_at=team.created_at,
                    member_count=counts.get(team.id, 0),
                    my_role=my_role,
                )
            )
        return items, total

    # ---------------- 邀请链接（Redis，不落库） ----------------

    async def create_invite(self, user: User, team_id: uuid.UUID) -> TeamInviteCreated:
        """生成邀请链接令牌：写 Redis `team:invite:<token>`，TTL 取配置（默认 72h）。"""
        team = await self._active_team_or_error(team_id)
        await self._require_team_roles(user, team.id, level="admin")
        token = secrets.token_hex(32)
        hours = int(await self.config.get_value("team", "invite.expire_hours", 72))
        expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
        await redis_set_json(f"{_INVITE_KEY_PREFIX}{token}", {"team_id": str(team.id)}, max(hours * 3600, 1))
        return TeamInviteCreated(token=token, expires_at=expires_at)

    async def resolve_invite(self, token: str) -> TeamInviteResolved:
        """解析邀请链接（public）：返回团队与有效期；无效 / 过期 3001，团队解散 3002。"""
        payload = await redis_get_json(f"{_INVITE_KEY_PREFIX}{token}")
        if not payload or "team_id" not in payload:
            raise APIError(RESOURCE_NOT_FOUND, "邀请链接无效或已过期", 404)
        team = await self.teams.get_by_id(uuid.UUID(str(payload["team_id"])))
        if team is None or team.status != TeamStatus.ACTIVE:
            raise APIError(RESOURCE_STATE_CONFLICT, "团队已解散", 409)
        ttl = int(await get_redis().ttl(f"{_INVITE_KEY_PREFIX}{token}"))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(ttl, 1))
        return TeamInviteResolved(team_id=team.id, team_name=team.name, expires_at=expires_at)

    # ---------------- 加入申请 / 审批 ----------------

    async def submit_application(self, user: User, team_id: uuid.UUID, body: TeamApplicationSubmit) -> None:
        """提交加入申请：已入队或已有 pending 申请返回 3003；经邀请链接提交记录来源。"""
        team = await self._active_team_or_error(team_id)
        if await self.teams.get_active_member(team.id, user.id) is not None:
            raise APIError(RESOURCE_DUPLICATE, "已是该团队成员", 409)
        if await self.teams.get_pending_application(team.id, user.id) is not None:
            raise APIError(RESOURCE_DUPLICATE, "已有待处理的加入申请", 409)
        invite_token = body.invite_token
        if invite_token:
            payload = await redis_get_json(f"{_INVITE_KEY_PREFIX}{invite_token}")
            if not payload or str(payload.get("team_id")) != str(team.id):
                raise APIError(RESOURCE_NOT_FOUND, "邀请链接无效或已过期", 404)
        self.db.add(
            TeamMemberApplication(team_id=team.id, user_id=user.id, invite_token=invite_token)
        )
        await self.db.flush()

    async def list_applications(
        self, user: User, team_id: uuid.UUID, status: str | None, page: int, page_size: int
    ) -> tuple[list[TeamApplicationOut], int]:
        """申请列表（team_creator / team_admin；status 缺省 = pending）。"""
        team = await self._team_or_404(team_id)
        await self._require_team_roles(user, team.id, level="admin")
        rows, total = await self.teams.list_applications(team.id, status, page, page_size)
        return [
            TeamApplicationOut(
                id=application.id,
                team_id=application.team_id,
                user_id=application.user_id,
                nickname=applicant.nickname,
                invite_token=application.invite_token,
                status=TeamApplicationStatus(application.status),
                applied_at=application.applied_at,
                reviewed_by=application.reviewed_by,
                reviewed_at=application.reviewed_at,
            )
            for application, applicant in rows
        ], total

    async def review_application(
        self, user: User, team_id: uuid.UUID, application_id: uuid.UUID, body: TeamApplicationReview
    ) -> None:
        """审批申请：通过 → 写在册成员 + team_member 授权；拒绝 → 仅记录状态（流程 3）。"""
        team = await self._team_or_404(team_id)
        await self._require_team_roles(user, team.id, level="admin")
        application = await self.teams.get_application(application_id)
        if application is None or application.team_id != team.id:
            raise APIError(RESOURCE_NOT_FOUND, "申请不存在", 404)
        if application.status != TeamApplicationStatus.PENDING:
            raise APIError(RESOURCE_STATE_CONFLICT, "该申请已处理", 409)
        application.status = (
            TeamApplicationStatus.APPROVED if body.approve else TeamApplicationStatus.REJECTED
        )
        application.reviewed_by = user.id
        application.reviewed_at = datetime.now(timezone.utc)
        if body.approve:
            if await self.teams.get_active_member(team.id, application.user_id) is None:
                self.db.add(
                    TeamMember(team_id=team.id, user_id=application.user_id, status=TeamMemberStatus.ACTIVE)
                )
            await self.roles.grant_team_role(application.user_id, team.id, ROLE_MEMBER)
        await self.db.flush()

    # ---------------- 成员管理 ----------------

    async def list_members(
        self, user: User, team_id: uuid.UUID, status: str | None, page: int, page_size: int
    ) -> tuple[list[TeamMemberOut], int]:
        """成员列表（团队任意角色可查，docs/contracts/teams.md；带创建者 / 管理员标记）。"""
        team = await self._team_or_404(team_id)
        await self._require_team_roles(user, team.id, level="member")
        rows, total = await self.teams.list_members(team.id, status, page, page_size)
        admin_ids = await self._team_admin_ids(team.id)
        return [
            TeamMemberOut(
                user_id=member.user_id,
                nickname=member_user.nickname,
                avatar_url=member_user.avatar_url,
                status=TeamMemberStatus(member.status),
                joined_at=member.joined_at,
                is_creator=self._is_creator(team, member.user_id),
                is_admin=member.user_id in admin_ids,
            )
            for member, member_user in rows
        ], total

    async def _team_admin_ids(self, team_id: uuid.UUID) -> set[uuid.UUID]:
        """拥有 team_admin 授权的用户 id 集合。"""
        from sqlalchemy import select

        from app.models.user import Role, UserRole

        stmt = (
            select(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserRole.scope == "team",
                UserRole.object_id == team_id,
                Role.code == ROLE_ADMIN,
            )
        )
        return {row for row in (await self.db.execute(stmt)).scalars()}

    async def set_admin(self, user: User, team_id: uuid.UUID, target_uid: uuid.UUID, body: TeamAdminFlag) -> None:
        """分配 / 取消团队管理员（仅创建者；流程 4：分配即写授权，取消即删除）。"""
        team = await self._team_or_404(team_id)
        await self._require_team_roles(user, team.id, level="creator")
        if target_uid == team.creator_id:
            raise APIError(AUTH_FORBIDDEN, "创建者无需分配管理员", 403)
        member = await self.teams.get_active_member(team.id, target_uid)
        if member is None:
            raise APIError(RESOURCE_NOT_FOUND, "成员不存在", 404)
        if body.is_admin:
            await self.roles.grant_team_role(target_uid, team.id, ROLE_ADMIN)
        else:
            await self.roles.revoke_team_roles(target_uid, team.id, {ROLE_ADMIN})

    async def kick(self, user: User, team_id: uuid.UUID, target_uid: uuid.UUID) -> None:
        """踢出成员（team_creator / team_admin；清理成员状态与团队授权）。"""
        team = await self._team_or_404(team_id)
        await self._require_team_roles(user, team.id, level="admin")
        if target_uid == team.creator_id:
            raise APIError(AUTH_FORBIDDEN, "不能移除团队创建者", 403)
        member = await self.teams.get_active_member(team.id, target_uid)
        if member is None:
            raise APIError(RESOURCE_NOT_FOUND, "成员不存在", 404)
        member.status = TeamMemberStatus.KICKED
        member.left_at = datetime.now(timezone.utc)
        await self.roles.revoke_team_roles(target_uid, team.id, {ROLE_ADMIN, ROLE_MEMBER})

    async def exit(self, user: User, team_id: uuid.UUID) -> None:
        """主动退出（成员本人；创建者不可退出，只能解散）。"""
        team = await self._team_or_404(team_id)
        if self._is_creator(team, user.id):
            raise APIError(AUTH_FORBIDDEN, "创建者不可退出团队，请解散团队", 403)
        member = await self.teams.get_active_member(team.id, user.id)
        if member is None:
            raise APIError(AUTH_FORBIDDEN, "非团队成员", 403)
        member.status = TeamMemberStatus.EXITED
        member.left_at = datetime.now(timezone.utc)
        await self.roles.revoke_team_roles(user.id, team.id, {ROLE_ADMIN, ROLE_MEMBER})

    async def disband(self, user: User, team_id: uuid.UUID) -> None:
        """解散团队（软解散，仅创建者）：清理全部团队授权与成员状态（数据所有权节）。"""
        team = await self._team_or_404(team_id)
        await self._require_team_roles(user, team.id, level="creator")
        if team.status != TeamStatus.ACTIVE:
            raise APIError(RESOURCE_STATE_CONFLICT, "团队已解散", 409)
        team.status = TeamStatus.DISBANDED
        team.disbanded_at = datetime.now(timezone.utc)
        await self.roles.revoke_all_team_roles(team.id)
        from sqlalchemy import select

        members = list(
            (
                await self.db.execute(
                    select(TeamMember).where(
                        TeamMember.team_id == team.id,
                        TeamMember.status == TeamMemberStatus.ACTIVE,
                    )
                )
            ).scalars()
        )
        for member in members:
            member.status = TeamMemberStatus.EXITED
            member.left_at = team.disbanded_at
        await self.db.flush()

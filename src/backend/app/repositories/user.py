"""用户域仓储：User / Session / Role 数据访问。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import UserRoleScope
from app.models.user import Role, User, UserRole, UserSession


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.db.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create(self, email: str, password_hash: str, nickname: str) -> User:
        user = User(email=email, password=password_hash, nickname=nickname, email_verified=True)
        self.db.add(user)
        await self.db.flush()
        return user

    async def touch_last_login(self, user: User, now: datetime) -> None:
        """更新最近登录时间：直接赋值 ORM 属性（避免批量 UPDATE 使属性过期触发异步懒加载）。"""
        user.last_login_at = now

    async def list_page(
        self,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
    ) -> tuple[list[User], int]:
        """管理端用户列表：关键字（昵称 / 邮箱）+ 状态过滤，按注册时间倒序分页。"""
        conditions = []
        if keyword:
            kw = f"%{keyword}%"
            conditions.append(User.email.ilike(kw) | User.nickname.ilike(kw))
        if status:
            conditions.append(User.status == status)
        count_stmt = select(func.count()).select_from(User)
        stmt = select(User)
        if conditions:
            count_stmt = count_stmt.where(*conditions)
            stmt = stmt.where(*conditions)
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list((await self.db.execute(stmt)).scalars().all())
        return items, int(total)

    async def get_nicknames(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        """批量读取昵称（管理列表展示用；缺失用户不出现在结果中）。"""
        if not user_ids:
            return {}
        stmt = select(User.id, User.nickname).where(User.id.in_(user_ids))
        return {uid: nickname for uid, nickname in (await self.db.execute(stmt)).all()}


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        device_info: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> UserSession:
        session = UserSession(
            user_id=user_id,
            token=token_hash,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent,
            last_active_at=datetime.now(),
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_valid_by_token(self, token_hash: str, now: datetime) -> UserSession | None:
        stmt = select(UserSession).where(
            UserSession.token == token_hash,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, session_id: uuid.UUID) -> UserSession | None:
        return await self.db.get(UserSession, session_id)

    async def list_active_by_user(self, user_id: uuid.UUID) -> list[UserSession]:
        stmt = (
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > datetime.now(),
            )
            .order_by(UserSession.created_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def revoke(self, session: UserSession, now: datetime) -> None:
        session.revoked_at = now
        await self.db.flush()

    async def delete(self, session: UserSession) -> None:
        """物理删除会话记录（退出登录时调用，不留存记录）。"""
        await self.db.delete(session)
        await self.db.flush()

    async def revoke_all_by_user(self, user_id: uuid.UUID, now: datetime) -> None:
        await self.db.execute(
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now)
            .execution_options(synchronize_session=False)
        )


class RoleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_code(self, code: str) -> Role | None:
        stmt = select(Role).where(Role.code == code)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_global_role_codes(self, user_id: uuid.UUID) -> list[str]:
        """读取用户全局角色 code 列表（scope='global'、object_id IS NULL）。"""
        stmt = (
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, UserRole.scope == UserRoleScope.GLOBAL, UserRole.object_id.is_(None))
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_global_role_codes_for_users(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
        """批量读取多个用户的全局角色（管理列表一次查询，避免 N+1）。"""
        if not user_ids:
            return {}
        stmt = (
            select(UserRole.user_id, Role.code)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserRole.user_id.in_(user_ids),
                UserRole.scope == UserRoleScope.GLOBAL,
                UserRole.object_id.is_(None),
            )
        )
        result: dict[uuid.UUID, list[str]] = {uid: [] for uid in user_ids}
        for user_id, code in (await self.db.execute(stmt)).all():
            result[user_id].append(code)
        return result

    async def replace_global_roles(self, user_id: uuid.UUID, role_ids: list[uuid.UUID]) -> None:
        """替换用户全局角色：先删后插（唯一索引兜底防重复，docs/contracts/admin.md）。"""
        await self.db.execute(
            delete(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.scope == UserRoleScope.GLOBAL,
                UserRole.object_id.is_(None),
            )
        )
        for role_id in role_ids:
            self.db.add(UserRole(user_id=user_id, role_id=role_id, scope=UserRoleScope.GLOBAL, object_id=None))
        await self.db.flush()

    # ---- 团队作用域授权（scope='team'、object_id=team_id，docs/contracts/teams.md） ----

    async def get_team_role_codes(self, user_id: uuid.UUID, team_id: uuid.UUID) -> list[str]:
        """读取用户在指定团队的角色 code 列表。"""
        stmt = (
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                UserRole.scope == UserRoleScope.TEAM,
                UserRole.object_id == team_id,
            )
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_team_roles_for_teams(
        self, user_id: uuid.UUID, team_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, set[str]]:
        """批量读取用户在多个团队的角色（我的团队列表一次查询，避免 N+1）。"""
        if not team_ids:
            return {}
        stmt = (
            select(UserRole.object_id, Role.code)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserRole.user_id == user_id,
                UserRole.scope == UserRoleScope.TEAM,
                UserRole.object_id.in_(team_ids),
            )
        )
        result: dict[uuid.UUID, set[str]] = {tid: set() for tid in team_ids}
        for team_id, code in (await self.db.execute(stmt)).all():
            if team_id in result:
                result[team_id].add(code)
        return result

    async def grant_team_role(self, user_id: uuid.UUID, team_id: uuid.UUID, code: str) -> None:
        """授予团队角色（幂等：已存在则跳过，唯一约束兜底）。"""
        role = await self.get_by_code(code)
        if role is None:
            return
        exists = (
            await self.db.execute(
                select(UserRole.id).where(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role.id,
                    UserRole.scope == UserRoleScope.TEAM,
                    UserRole.object_id == team_id,
                )
            )
        ).scalar_one_or_none()
        if exists is not None:
            return
        self.db.add(
            UserRole(
                user_id=user_id, role_id=role.id, scope=UserRoleScope.TEAM, object_id=team_id
            )
        )
        await self.db.flush()

    async def revoke_team_roles(
        self, user_id: uuid.UUID, team_id: uuid.UUID, codes: set[str]
    ) -> None:
        """撤销用户在指定团队的角色（按角色 code 集合）。"""
        if not codes:
            return
        role_ids = (
            await self.db.execute(select(Role.id).where(Role.code.in_(codes)))
        ).scalars().all()
        if not role_ids:
            return
        await self.db.execute(
            delete(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.scope == UserRoleScope.TEAM,
                UserRole.object_id == team_id,
                UserRole.role_id.in_(role_ids),
            )
        )
        await self.db.flush()

    async def revoke_all_team_roles(self, team_id: uuid.UUID) -> None:
        """撤销团队全部角色授权（解散时调用）。"""
        await self.db.execute(
            delete(UserRole).where(
                UserRole.scope == UserRoleScope.TEAM,
                UserRole.object_id == team_id,
            )
        )
        await self.db.flush()

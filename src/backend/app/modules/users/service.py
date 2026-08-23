"""用户模块业务逻辑（Service 层）。

职责：用户中心（资料 / 注销 / 会话）与用户管理（角色 / 封禁 / 冻结 / Token 用量）。
用户管理端点挂在 /admin 前缀下（见 admin.md），由 admin.routes 调用本 Service。
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.users.repository import RoleRepository, SessionRepository, UserRepository
from app.modules.users.schemas import ProfileUpdate, UserPage, UserPublic
from app.shared.common.errors import (
    AUTH_INVALID_CREDENTIAL,
    PARAM_FORMAT_INVALID,
    RESOURCE_NOT_FOUND,
    RESOURCE_STATE_CONFLICT,
    APIError,
)
from app.shared.infra.redis import redis_delete
from app.shared.auth.security import verify_password
from app.shared.common.validation import validate_nickname

logger = logging.getLogger(__name__)

_VALID_THEMES = {"light", "dark"}
_VALID_STATUS = {"active", "frozen", "banned", "deleted"}


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.sessions = SessionRepository(db)
        self.roles = RoleRepository(db)

    # ---------------- 序列化 ----------------

    async def to_public(self, user: User) -> UserPublic:
        roles = await self.roles.get_global_role_codes(user.id)
        return UserPublic(
            id=user.id,
            email=user.email,
            email_verified=user.email_verified,
            nickname=user.nickname,
            avatar_url=user.avatar_url,
            signature=user.signature,
            theme=user.theme,
            status=user.status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=roles,
        )

    # ---------------- 用户中心 ----------------

    async def get_me(self, user: User) -> UserPublic:
        return await self.to_public(user)

    async def update_profile(self, user: User, patch: ProfileUpdate) -> UserPublic:
        if patch.nickname is not None:
            validate_nickname(patch.nickname)
            user.nickname = patch.nickname.strip()
        if patch.signature is not None:
            if len(patch.signature) > 255:
                raise APIError(PARAM_FORMAT_INVALID, "个性签名过长（≤255）", 400)
            user.signature = patch.signature
        if "avatar_url" in patch.model_fields_set:
            if patch.avatar_url is not None:
                expected_prefix = f"users/{user.id}/avatar/"
                if not (patch.avatar_url.startswith(expected_prefix) or patch.avatar_url.startswith(("http://", "https://"))):
                    raise APIError(PARAM_FORMAT_INVALID, "头像必须使用当前用户上传的 MinIO 文件或可信外链", 400)
                if len(patch.avatar_url) > 512:
                    raise APIError(PARAM_FORMAT_INVALID, "头像地址过长（≤512）", 400)
            user.avatar_url = patch.avatar_url
        if patch.theme is not None:
            if patch.theme not in _VALID_THEMES:
                raise APIError(PARAM_FORMAT_INVALID, "主题仅支持 light / dark", 400)
            user.theme = patch.theme
        await self.db.flush()
        await self.db.refresh(user)  # onupdate 生成 updated_at，需显式刷新（async 不支持隐式懒加载）
        return await self.to_public(user)

    async def soft_delete(self, user: User, password: str) -> None:
        """软注销（docs/contracts/users.md）：status='deleted'，邮箱脱敏释放唯一约束。"""
        if not verify_password(password, user.password):
            raise APIError(AUTH_INVALID_CREDENTIAL, "密码错误", 401)
        user.status = "deleted"
        user.email = f"u{user.id}@invalid.local"
        user.email_verified = False
        # 撤销全部会话并清理 Redis 缓存
        sessions = await self.sessions.list_active_by_user(user.id)
        await self.sessions.revoke_all_by_user(user.id, datetime.now())
        for s in sessions:
            await redis_delete(f"session:{s.token}")
        await self.db.flush()

    async def list_sessions(self, user: User, current_token_hash: str) -> list[dict]:
        sessions = await self.sessions.list_active_by_user(user.id)
        return [
            {
                "id": str(s.id),
                "device_info": s.device_info,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent,
                "expires_at": s.expires_at.isoformat(),
                "revoked_at": s.revoked_at.isoformat() if s.revoked_at else None,
                "last_active_at": s.last_active_at.isoformat() if s.last_active_at else None,
                "created_at": s.created_at.isoformat(),
                "current": s.token == current_token_hash,
            }
            for s in sessions
        ]

    async def revoke_session(self, user: User, session_id: uuid.UUID, current_token_hash: str) -> None:
        session = await self.sessions.get_by_id(session_id)
        if session is None or session.user_id != user.id:
            raise APIError(RESOURCE_NOT_FOUND, "会话不存在", 404)
        if session.token == current_token_hash:
            raise APIError(RESOURCE_STATE_CONFLICT, "不能撤销当前会话", 409)
        await self.sessions.revoke(session, datetime.now())
        await redis_delete(f"session:{session.token}")

    # ---------------- 用户管理（admin 调用） ----------------

    async def admin_list_users(
        self, page: int, page_size: int, keyword: str | None, status: str | None
    ) -> dict:
        if status and status not in _VALID_STATUS:
            raise APIError(PARAM_FORMAT_INVALID, "状态取值不合法", 400)
        items, total = await self.users.list_page(page, page_size, keyword, status)
        roles_map = await self.roles.get_global_role_codes_for_users([u.id for u in items])
        user_list = []
        for u in items:
            public = UserPublic(
                id=u.id, email=u.email, email_verified=u.email_verified, nickname=u.nickname,
                avatar_url=u.avatar_url, signature=u.signature, theme=u.theme, status=u.status,
                last_login_at=u.last_login_at, created_at=u.created_at, updated_at=u.updated_at,
                roles=roles_map.get(u.id, []),
            )
            user_list.append(public)
        return UserPage(items=user_list, total=total, page=page, page_size=page_size).model_dump(mode="json")

    async def admin_set_roles(self, user_id: uuid.UUID, role_codes: list[str]) -> None:
        """全局角色授权：写 user_roles（scope='global'、object_id=NULL），见 docs/contracts/admin.md。"""
        target = await self.users.get_by_id(user_id)
        if target is None:
            raise APIError(RESOURCE_NOT_FOUND, "用户不存在", 404)
        if not role_codes:
            raise APIError(PARAM_FORMAT_INVALID, "角色列表不能为空", 400)
        role_ids = []
        for code in role_codes:
            role = await self.roles.get_by_code(code)
            if role is None:
                raise APIError(PARAM_FORMAT_INVALID, f"角色不存在：{code}", 400)
            role_ids.append(role.id)
        await self.roles.replace_global_roles(user_id, role_ids)

    async def _set_status(self, user_id: uuid.UUID, status: str, action_label: str) -> None:
        target = await self.users.get_by_id(user_id)
        if target is None:
            raise APIError(RESOURCE_NOT_FOUND, "用户不存在", 404)
        if target.status == "deleted":
            raise APIError(RESOURCE_STATE_CONFLICT, f"已注销账号不可{action_label}", 409)
        target.status = status
        await self.db.flush()
        logger.info("admin %s user=%s -> %s", action_label, user_id, status)

    async def admin_ban(self, user_id: uuid.UUID, _reason: str | None) -> None:
        await self._set_status(user_id, "banned", "封禁")

    async def admin_unban(self, user_id: uuid.UUID) -> None:
        await self._set_status(user_id, "active", "解封")

    async def admin_freeze(self, user_id: uuid.UUID, _reason: str | None) -> None:
        await self._set_status(user_id, "frozen", "冻结")

    async def admin_unfreeze(self, user_id: uuid.UUID) -> None:
        await self._set_status(user_id, "active", "解冻")

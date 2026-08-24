"""用户模块业务逻辑（Service 层）。

职责：认证（注册 / 登录 / 会话 / 找回密码）、用户中心（资料 / 注销 / 会话管理）
与用户管理（角色 / 封禁 / 冻结；端点挂 /admin 前缀，由 admin.routes 调用）。
原 auth 模块已并入本模块（docs/decisions/2026-08-24-backend-module-packaging.md）。
"""
from __future__ import annotations

import asyncio
import logging
import secrets
import smtplib
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User, UserRole
from app.modules.users.repository import RoleRepository, SessionRepository, UserRepository
from app.modules.users.schemas import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    EmailCodeRequest,
    LoginRequest,
    ProfileUpdate,
    RegisterRequest,
    ResetPasswordRequest,
    UserPage,
    UserPublic,
)
from app.shared.common.errors import (
    AUTH_INVALID_CREDENTIAL,
    PARAM_FORMAT_INVALID,
    PARAM_MISSING_REQUIRED,
    RATE_LIMITED,
    RATE_SEND_TOO_FREQUENT,
    REGISTER_DISABLED,
    RESOURCE_NOT_FOUND,
    RESOURCE_STATE_CONFLICT,
    SYSTEM_UPSTREAM_FAILURE,
    APIError,
)
from app.shared.infra.audit import write_login_log
from app.shared.infra.redis import redis_delete, redis_get_json, redis_incr, redis_set, redis_set_json
from app.shared.auth.security import generate_token, hash_password, hash_token, verify_password
from app.shared.common.validation import validate_email, validate_nickname, validate_password
from app.shared.infra.system_config import ConfigService

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


# ---------------- 认证（原 auth 模块） ----------------

SESSION_TTL_DAYS = 30  # 会话有效期（天）
LOGIN_FAIL_WINDOW_SECONDS = 900  # 登录失败计数窗口（15 分钟）
LOGIN_FAIL_MAX = 5  # 触发冻结的失败次数


def _smtp_send(cfg: dict, message: EmailMessage) -> None:
    """同步 SMTP 发送（在线程池中执行，避免阻塞事件循环）。"""
    if cfg["use_ssl"]:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=10) as server:
            if cfg["username"]:
                server.login(cfg["username"], cfg["password"])
            server.send_message(message)
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
            server.starttls()
            if cfg["username"]:
                server.login(cfg["username"], cfg["password"])
            server.send_message(message)


def _build_code_email(cfg: dict, email: str, purpose: str, code: str) -> EmailMessage:
    subject = "PigeonOJ 邮箱验证码"
    body = f"你的验证码是 {code}（purpose={purpose}），请勿泄露给他人。"
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = cfg["sender"] or cfg["username"]
    message["To"] = email
    message.set_content(body)
    return message


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.sessions = SessionRepository(db)
        self.roles = RoleRepository(db)
        self.config = ConfigService(db)

    # ---------------- 验证码 ----------------

    async def _send_email_code(self, email: str, purpose: str, code: str) -> None:
        """发送邮箱验证码：SMTP 已配置走真实发信，未配置（host 空）打印到后端日志（本地开发兜底）。"""
        cfg = await self.config.get_email_smtp_config()
        if not cfg["host"]:
            logger.info("[email-code] purpose=%s email=%s code=%s（SMTP 未配置，开发期打印）", purpose, email, code)
            return
        message = _build_code_email(cfg, email, purpose, code)
        try:
            await asyncio.to_thread(_smtp_send, cfg, message)
        except Exception as exc:  # noqa: BLE001 - 发信失败统一转为上游错误
            logger.exception("SMTP 邮件发送失败: host=%s port=%s", cfg["host"], cfg["port"])
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "邮件发送失败，请稍后重试", 502) from exc

    async def send_email_code(self, req: EmailCodeRequest, ip: str | None, user_agent: str | None) -> None:
        validate_email(req.email)
        policy = await self.config.get_email_code_policy()
        resend_key = f"email:resend:{req.email}:{req.purpose}"
        if await redis_get_json(resend_key) is not None:
            raise APIError(RATE_SEND_TOO_FREQUENT, "发送过于频繁，请稍后再试", 429)

        code = f"{secrets.randbelow(1_000_000):06d}"
        code_key = f"email:code:{req.email}:{req.purpose}"
        await redis_set_json(code_key, {"code": code, "attempts": 0}, policy["expire_seconds"])
        await redis_set(resend_key, "1", policy["resend_seconds"])
        await self._send_email_code(req.email, req.purpose, code)

    async def _verify_code(self, email: str, purpose: str, code: str, max_attempts: int) -> None:
        """校验验证码：一次性使用；错误超次删除并触发频控（users.md 安全策略）。"""
        code_key = f"email:code:{email}:{purpose}"
        data = await redis_get_json(code_key)
        if data is None:
            raise APIError(AUTH_INVALID_CREDENTIAL, "验证码已过期，请重新获取", 401)
        attempts = int(data.get("attempts", 0))
        if attempts >= max_attempts:
            await redis_delete(code_key)
            raise APIError(RATE_LIMITED, "验证码错误次数过多，请重新获取", 429)
        if data.get("code") != code:
            data["attempts"] = attempts + 1
            await redis_set_json(code_key, data, None)  # 保持原 TTL
            raise APIError(AUTH_INVALID_CREDENTIAL, "验证码错误", 401)
        await redis_delete(code_key)  # 一次性使用

    # ---------------- 注册 ----------------

    async def register(self, req: RegisterRequest, ip: str | None, user_agent: str | None) -> None:
        # 站点注册开关（system_configs site.register_enabled）：关闭时直接拒绝，不消耗验证码
        if not await self.config.get_value("site", "site.register_enabled", True):
            raise APIError(REGISTER_DISABLED, "当前站点未开放注册", 403)
        validate_email(req.email)
        validate_password(req.password)
        validate_nickname(req.nickname)
        # 邮箱验证开关（email.verify_enabled）：开启时校验验证码，关闭时跳过
        if await self.config.get_email_verify_enabled():
            if not req.code:
                raise APIError(PARAM_MISSING_REQUIRED, "请输入邮箱验证码", 400)
            policy = await self.config.get_email_code_policy()
            await self._verify_code(req.email, "register", req.code, policy["max_attempts"])

        if await self.users.get_by_email(req.email) is not None:
            await write_login_log(self.db, "register", False, email=req.email, ip_address=ip,
                                  user_agent=user_agent, reason="邮箱已注册")
            raise APIError(RESOURCE_STATE_CONFLICT, "邮箱已注册", 409)

        user = await self.users.create(req.email, hash_password(req.password), req.nickname.strip())
        # 默认角色 user
        user_role = await self.roles.get_by_code("user")
        if user_role is not None:
            self.db.add(UserRole(user_id=user.id, role_id=user_role.id, scope="global", object_id=None))
        await self.db.flush()
        await write_login_log(self.db, "register", True, user_id=user.id, email=req.email,
                              ip_address=ip, user_agent=user_agent)

    # ---------------- 登录 / 登出 ----------------

    async def login(self, req: LoginRequest, ip: str | None, user_agent: str | None) -> dict:
        user = await self.users.get_by_email(req.email)
        fail_key = f"login:fail:{req.email}"

        if user is None or not verify_password(req.password, user.password):
            fails = await redis_incr(fail_key, LOGIN_FAIL_WINDOW_SECONDS)
            reason = None
            if user is not None and fails >= LOGIN_FAIL_MAX:
                # 安全策略：登录失败超次 → frozen（可人工解冻，users.md 账号状态语义）
                user.status = "frozen"
                reason = "登录失败超次，触发冻结"
            await write_login_log(self.db, "login", False, user_id=user.id if user else None,
                                  email=req.email, ip_address=ip, user_agent=user_agent,
                                  reason=reason or "密码错误")
            # 失败路径显式提交：冻结状态与审计日志必须持久化（随后抛业务错误，get_db 会回滚）
            await self.db.commit()
            raise APIError(AUTH_INVALID_CREDENTIAL, "邮箱或密码错误", 401)

        if user.status == "frozen":
            await write_login_log(self.db, "login", False, user_id=user.id, email=req.email,
                                  ip_address=ip, user_agent=user_agent, reason="账号已冻结")
            raise APIError(RESOURCE_STATE_CONFLICT, "账号已冻结，请联系管理员", 409)
        if user.status == "banned":
            await write_login_log(self.db, "login", False, user_id=user.id, email=req.email,
                                  ip_address=ip, user_agent=user_agent, reason="账号已封禁")
            raise APIError(RESOURCE_STATE_CONFLICT, "账号已封禁，请联系管理员", 409)
        if user.status == "deleted":
            await write_login_log(self.db, "login", False, user_id=user.id, email=req.email,
                                  ip_address=ip, user_agent=user_agent, reason="账号已注销")
            raise APIError(RESOURCE_STATE_CONFLICT, "账号已注销，请联系管理员", 409)

        await redis_delete(fail_key)  # 登录成功清零失败计数

        # 创建会话：token 哈希入库，原始 token 返回客户端
        raw_token = generate_token()
        token_hash = hash_token(raw_token)
        now = datetime.now()
        expires_at = now + timedelta(days=SESSION_TTL_DAYS)
        await self.sessions.create(
            user_id=user.id, token_hash=token_hash, expires_at=expires_at,
            device_info=None, ip_address=ip, user_agent=user_agent,
        )
        # Redis 热点缓存（deps.py 校验使用）
        ttl = int((expires_at - now).total_seconds())
        await redis_set(f"session:{token_hash}", str(user.id), ttl)
        await self.users.touch_last_login(user, now)
        await write_login_log(self.db, "login", True, user_id=user.id, email=req.email,
                              ip_address=ip, user_agent=user_agent)
        await self.db.flush()

        # 组装返回（含角色）
        public = await UserService(self.db).to_public(user)
        return {"token": raw_token, "user": public.model_dump(mode="json")}

    async def logout(self, raw_token: str | None, user: User, ip: str | None, user_agent: str | None) -> None:
        if raw_token:
            token_hash = hash_token(raw_token)
            session = await self.sessions.get_valid_by_token(token_hash, datetime.now())
            if session is not None and session.user_id == user.id:
                await self.sessions.revoke(session, datetime.now())
                await redis_delete(f"session:{token_hash}")
        await write_login_log(self.db, "logout", True, user_id=user.id, email=user.email,
                              ip_address=ip, user_agent=user_agent)

    # ---------------- 找回密码 ----------------

    async def reset_password(self, req: ResetPasswordRequest, ip: str | None, user_agent: str | None) -> None:
        validate_email(req.email)
        validate_password(req.new_password)
        policy = await self.config.get_email_code_policy()
        await self._verify_code(req.email, "reset_password", req.code, policy["max_attempts"])

        user = await self.users.get_by_email(req.email)
        if user is None or user.status == "deleted":
            raise APIError(RESOURCE_NOT_FOUND, "用户不存在", 404)
        user.password = hash_password(req.new_password)
        await self.db.flush()
        await write_login_log(self.db, "reset_password", True, user_id=user.id, email=req.email,
                              ip_address=ip, user_agent=user_agent)

    # ---------------- 修改密码 / 换绑邮箱（登录态） ----------------

    async def change_password(self, user: User, req: ChangePasswordRequest) -> None:
        if not verify_password(req.old_password, user.password):
            raise APIError(AUTH_INVALID_CREDENTIAL, "原密码错误", 401)
        validate_password(req.new_password)
        user.password = hash_password(req.new_password)
        await self.db.flush()

    async def change_email(self, user: User, req: ChangeEmailRequest, ip: str | None, user_agent: str | None) -> None:
        validate_email(req.new_email)
        policy = await self.config.get_email_code_policy()
        await self._verify_code(req.new_email, "change_email", req.code, policy["max_attempts"])
        existing = await self.users.get_by_email(req.new_email)
        if existing is not None and existing.id != user.id:
            raise APIError(RESOURCE_STATE_CONFLICT, "该邮箱已被使用", 409)
        user.email = req.new_email
        user.email_verified = True
        await self.db.flush()
        await write_login_log(self.db, "change_email", True, user_id=user.id, email=req.new_email,
                              ip_address=ip, user_agent=user_agent)

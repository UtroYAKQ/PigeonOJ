"""认证模块业务逻辑（Service 层）：注册 / 登录 / 登出 / 找回密码 / 改密 / 换绑邮箱。

- 邮箱验证码存 Redis（email:code / email:resend，不落库），一次性使用
- 登录失败超次触发 status='frozen'（docs/contracts/users.md 4002 语义）
- 会话 Token 哈希入库 + Redis 热点缓存（shared/security.py、shared/deps.py）
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.audit import write_login_log
from app.modules.auth.schemas import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    EmailCodeRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.modules.users.models import User
from app.modules.users.repository import RoleRepository, SessionRepository, UserRepository
from app.shared.common.audit import write_login_log
from app.shared.common.config import ConfigService
from app.shared.common.errors import (
    AUTH_INVALID_CREDENTIAL,
    RATE_LIMITED,
    RATE_SEND_TOO_FREQUENT,
    RESOURCE_NOT_FOUND,
    RESOURCE_STATE_CONFLICT,
    APIError,
)
from app.shared.infra.redis import redis_delete, redis_get_json, redis_incr, redis_set, redis_set_json
from app.shared.auth.security import generate_token, hash_password, hash_token, verify_password
from app.shared.common.validation import validate_email, validate_nickname, validate_password

logger = logging.getLogger(__name__)

SESSION_TTL_DAYS = 30  # 会话有效期（天）
LOGIN_FAIL_WINDOW_SECONDS = 900  # 登录失败计数窗口（15 分钟）
LOGIN_FAIL_MAX = 5  # 触发冻结的失败次数


def _send_email_code(email: str, purpose: str, code: str) -> None:
    """发送邮箱验证码。

    当前为开发期实现：SMTP 未配置，验证码打印到后端日志（见 docs/operations.md 说明）。
    后续接入邮件服务时替换本函数实现，接口签名不变。
    """
    logger.info("[email-code] purpose=%s email=%s code=%s（开发期打印，未接入 SMTP）", purpose, email, code)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.sessions = SessionRepository(db)
        self.roles = RoleRepository(db)
        self.config = ConfigService(db)

    # ---------------- 验证码 ----------------

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
        _send_email_code(req.email, req.purpose, code)

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
        validate_email(req.email)
        validate_password(req.password)
        validate_nickname(req.nickname)
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
            from app.modules.users.models import UserRole
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
            raise APIError(RESOURCE_STATE_CONFLICT, "账号已注销", 409)

        await redis_delete(fail_key)  # 登录成功清零失败计数

        # 创建会话：token 哈希入库，原始 token 返回客户端
        raw_token = generate_token()
        token_hash = hash_token(raw_token)
        now = datetime.now()
        expires_at = now + timedelta(days=SESSION_TTL_DAYS)
        session = await self.sessions.create(
            user_id=user.id, token_hash=token_hash, expires_at=expires_at,
            device_info=None, ip_address=ip, user_agent=user_agent,
        )
        # Redis 热点缓存（shared/deps.py 校验使用）
        ttl = int((expires_at - now).total_seconds())
        await redis_set(f"session:{token_hash}", str(user.id), ttl)
        await self.users.touch_last_login(user, now)
        await write_login_log(self.db, "login", True, user_id=user.id, email=req.email,
                              ip_address=ip, user_agent=user_agent)
        await self.db.flush()

        # 组装返回（含角色）
        from app.modules.users.service import UserService
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

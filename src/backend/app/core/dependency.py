"""认证授权依赖与权限检查（RBAC 应用层分支判定，docs/architecture.md）。

- 会话 Token 从 Authorization: Bearer <token> 提取，哈希后查 user_sessions（有效 / 未过期 / 未撤销）
- 会话热点缓存：Redis `session:<token_hash>` → user_id，TTL 与会话过期时间一致
- 账号状态：frozen / banned / deleted 拦截接口访问
- 题目管理角色检查（docs/decisions/2026-08-15-rbac-simplification.md）
"""
from __future__ import annotations

import ipaddress
import uuid
from datetime import datetime

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.controllers.user import RoleRepository, SessionRepository, UserRepository
from app.core.database import get_db
from app.core.exceptions import (
    AUTH_FORBIDDEN,
    AUTH_NOT_LOGGED_IN,
    AUTH_SESSION_EXPIRED,
    APIError,
)
from app.core.redis import redis_get, redis_set
from app.utils.security import hash_token

_SESSION_CACHE_TTL_BUFFER = 60  # 秒；缓存 TTL 略长于数据库过期时间，避免边界竞态

# 题目管理角色集合（docs/contracts/problems.md 端点表）
# admin: 系统管理员
# tutor: 导师
# team_creator: 团队创建者（teams 模块接入后生效）
MANAGER_ROLE_CODES: set[str] = {"admin", "tutor", "team_creator"}


def parse_client_ip(host: str | None) -> str | None:
    """INET 列只接受合法 IP；解析失败（如测试客户端 hostname）返回 None。"""
    if not host:
        return None
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        return None


def get_bearer_token(request: Request) -> str | None:
    """从 Authorization 头提取 Bearer Token。"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):].strip()
    return None


async def _load_user(db: AsyncSession, raw_token: str) -> User:
    """加载并验证用户会话（Redis 热点缓存 → 数据库回源）。"""
    token_hash = hash_token(raw_token)

    # 1) Redis 热点缓存命中
    cache_key = f"session:{token_hash}"
    cached_user_id = await redis_get(cache_key)
    if cached_user_id:
        user_id = uuid.UUID(cached_user_id)
    else:
        # 2) 回源数据库校验会话
        session = await SessionRepository(db).get_valid_by_token(token_hash, datetime.now())
        if session is None:
            raise APIError(AUTH_SESSION_EXPIRED, "会话已过期或失效，请重新登录", 401)
        user_id = session.user_id
        # 写入热点缓存（TTL 与会话剩余有效期对齐）
        ttl = int((session.expires_at - datetime.now()).total_seconds()) + _SESSION_CACHE_TTL_BUFFER
        await redis_set(cache_key, str(user_id), max(ttl, 1))

    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise APIError(AUTH_NOT_LOGGED_IN, "用户不存在", 401)

    # 账号状态拦截（frozen / banned / deleted 语义见 docs/contracts/users.md「账号状态语义」）
    if user.status != "active":
        raise APIError(AUTH_FORBIDDEN, "账号状态异常，请联系管理员", 403)

    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """认证依赖：返回当前登录用户；未登录 / 会话失效 / 账号状态异常时抛 20xx。"""
    raw_token = get_bearer_token(request)
    if not raw_token:
        raise APIError(AUTH_NOT_LOGGED_IN, "未登录", 401)
    return await _load_user(db, raw_token)


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """可选认证：匿名返回 None；携带了 Token 则必须有效（过期 / 无效仍抛 20xx）。"""
    raw_token = get_bearer_token(request)
    if not raw_token:
        return None
    return await _load_user(db, raw_token)


async def get_current_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """管理员依赖：非 admin 访问管理端点抛 2003（docs/contracts/admin.md）。"""
    roles = await RoleRepository(db).get_global_role_codes(current_user.id)
    if "admin" not in roles:
        raise APIError(AUTH_FORBIDDEN, "无权限：需要管理员角色", 403)
    return current_user


async def get_user_role_codes(db: AsyncSession, user_id) -> set[str]:
    """获取用户的全局角色码集合。"""
    return set(await RoleRepository(db).get_global_role_codes(user_id))


async def is_manager(db: AsyncSession, user: User) -> bool:
    """检查用户是否为题目管理角色。"""
    codes = await get_user_role_codes(db, user.id)
    return bool(MANAGER_ROLE_CODES.intersection(codes))


async def require_manager_role(db: AsyncSession, user: User) -> None:
    """要求用户为管理角色，否则抛出权限错误。"""
    if not await is_manager(db, user):
        raise APIError(AUTH_FORBIDDEN, "无权限：需要管理角色", 403)

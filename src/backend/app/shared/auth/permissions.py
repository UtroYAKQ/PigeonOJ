"""统一权限检查工具：角色常量定义 + 权限检查辅助函数。

使用方式：
    from app.shared.auth.permissions import MANAGER_ROLE_CODES, require_manager_role

    # 方式1：直接检查
    if await require_manager_role(db, user):
        ...

    # 方式2：检查角色集合
    codes = await RoleRepository(db).get_global_role_codes(user.id)
    if MANAGER_ROLE_CODES.intersection(codes):
        ...
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.users.repository import RoleRepository

# 题目管理角色集合（docs/contracts/problems.md 端点表）
# admin: 系统管理员
# tutor: 导师
# team_creator: 团队创建者（teams 模块接入后生效）
MANAGER_ROLE_CODES: set[str] = {"admin", "tutor", "team_creator"}


async def get_user_role_codes(db: AsyncSession, user_id) -> set[str]:
    """获取用户的全局角色码集合。"""
    return await RoleRepository(db).get_global_role_codes(user_id)


async def is_manager(db: AsyncSession, user: User) -> bool:
    """检查用户是否为题目管理角色。"""
    codes = await get_user_role_codes(db, user.id)
    return bool(MANAGER_ROLE_CODES.intersection(codes))


async def require_manager_role(db: AsyncSession, user: User) -> None:
    """要求用户为管理角色，否则抛出权限错误。"""
    from app.shared.common.errors import APIError, AUTH_FORBIDDEN

    if not await is_manager(db, user):
        raise APIError(AUTH_FORBIDDEN, "无权限：需要管理角色", 403)

"""题目管理角色权限检查（RBAC 应用层分支判定，docs/decisions/2026-08-15-rbac-simplification.md）。

原位于 shared/auth/permissions.py；因依赖 users 模型与仓储（业务逻辑），
已迁入本模块，shared 层不再反向依赖业务模块。
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.users.repository import RoleRepository
from app.shared.common.errors import APIError, AUTH_FORBIDDEN

# 题目管理角色集合（docs/contracts/problems.md 端点表）
# admin: 系统管理员
# tutor: 导师
# team_creator: 团队创建者（teams 模块接入后生效）
MANAGER_ROLE_CODES: set[str] = {"admin", "tutor", "team_creator"}


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

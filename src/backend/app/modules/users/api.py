"""users 模块对外门面（唯一出口）。

其他模块只允许 `from app.modules.users.api import ...`；
模块内 service / repository / models / deps / permissions 均为私有实现
（由 scripts/check_import_rules.py 机械检查，见 docs/architecture.md 分层架构）。
"""
from app.modules.users.deps import (
    get_bearer_token,
    get_current_admin,
    get_current_user,
    get_optional_user,
    parse_client_ip,
)
from app.modules.users.models import User
from app.modules.users.permissions import (
    MANAGER_ROLE_CODES,
    get_user_role_codes,
    is_manager,
    require_manager_role,
)
from app.modules.users.repository import RoleRepository, UserRepository
from app.modules.users.service import AuthService, UserService


async def get_nicknames(db, user_ids) -> dict:
    """批量读取用户昵称（管理列表展示用；缺失用户不出现在结果中）。"""
    return await UserRepository(db).get_nicknames(user_ids)


__all__ = [
    "User",
    "AuthService",
    "UserService",
    "RoleRepository",
    "UserRepository",
    "MANAGER_ROLE_CODES",
    "get_bearer_token",
    "get_current_admin",
    "get_current_user",
    "get_optional_user",
    "get_nicknames",
    "get_user_role_codes",
    "is_manager",
    "parse_client_ip",
    "require_manager_role",
]

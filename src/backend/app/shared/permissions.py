"""统一权限检查工具（兼容层，已迁移至 shared/auth/permissions.py）。

保留此文件以兼容旧有导入：
    from app.shared.permissions import MANAGER_ROLE_CODES, is_manager, require_manager_role

新代码请直接使用：
    from app.shared.auth.permissions import MANAGER_ROLE_CODES, is_manager, require_manager_role
"""
from app.shared.auth.permissions import (  # noqa: F401
    MANAGER_ROLE_CODES,
    get_user_role_codes,
    is_manager,
    require_manager_role,
)

__all__ = ["MANAGER_ROLE_CODES", "get_user_role_codes", "is_manager", "require_manager_role"]

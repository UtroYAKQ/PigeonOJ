"""依赖注入（兼容层，已迁移至 shared/auth/deps.py → users/deps.py）。

保留此文件以兼容旧有导入：
    from app.shared.deps import get_current_user, get_current_admin, parse_client_ip

新代码请直接使用：
    from app.modules.users.deps import get_current_user, get_current_admin, parse_client_ip
"""
from app.modules.users.deps import (  # noqa: F401 - re-export for backward compatibility
    get_bearer_token,
    get_current_admin,
    get_current_user,
    get_optional_user,
    parse_client_ip,
)

__all__ = [
    "parse_client_ip",
    "get_bearer_token",
    "get_current_user",
    "get_optional_user",
    "get_current_admin",
]

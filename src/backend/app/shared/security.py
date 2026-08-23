"""安全工具（兼容层，已迁移至 shared/auth/security.py）。

保留此文件以兼容旧有导入：
    from app.shared.security import hash_password, verify_password, generate_token, hash_token

新代码请直接使用：
    from app.shared.auth.security import hash_password, verify_password, generate_token, hash_token
"""
from app.shared.auth.security import (  # noqa: F401
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)

__all__ = ["hash_password", "verify_password", "generate_token", "hash_token"]

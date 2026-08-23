"""共享参数校验（兼容层，已迁移至 shared/common/validation.py）。

保留此文件以兼容旧有导入：
    from app.shared.validation import validate_email, validate_password, validate_nickname

新代码请直接使用：
    from app.shared.common.validation import validate_email, validate_password, validate_nickname
"""
from app.shared.common.validation import (  # noqa: F401
    validate_email,
    validate_nickname,
    validate_password,
)

__all__ = ["validate_email", "validate_password", "validate_nickname"]

"""统一响应信封（兼容层，已迁移至 shared/common/response.py）。

保留此文件以兼容旧有导入：
    from app.shared.response import ok, error

新代码请直接使用：
    from app.shared.common.response import ok, error
"""
from app.shared.common.response import error, ok  # noqa: F401

__all__ = ["ok", "error"]

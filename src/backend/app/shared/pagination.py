"""通用分页工具（兼容层，已迁移至 shared/common/pagination.py）。

保留此文件以兼容旧有导入：
    from app.shared.pagination import PaginationParams, PaginatedResponse, paginate

新代码请直接使用：
    from app.shared.common.pagination import PaginationParams, PaginatedResponse, paginate
"""
from app.shared.common.pagination import PaginatedResponse, PaginationParams, paginate  # noqa: F401

__all__ = ["PaginationParams", "PaginatedResponse", "paginate"]

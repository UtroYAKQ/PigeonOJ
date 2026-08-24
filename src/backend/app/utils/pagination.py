"""通用分页响应格式（docs/contracts/common.md 分页契约：{ items, total, page, page_size }）。

分页参数与查询由各模块 Repository 按需实现（列表语义差异大，不做统一查询封装）。
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """统一分页响应格式。"""

    items: list[T]
    total: int
    page: int
    page_size: int

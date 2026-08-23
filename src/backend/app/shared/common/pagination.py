"""通用分页工具：统一分页参数定义、查询辅助函数和响应格式。

使用方式：
    from app.shared.common.pagination import PaginationParams, PaginatedResponse, paginate

    @router.get("/items")
    async def list_items(pagination: PaginationParams = Depends(), db = Depends(get_db)):
        rows, total = await paginate(db, Item, [], Item.created_at, pagination)
        return ok(PaginatedResponse(items=rows, total=total, page=pagination.page, page_size=pagination.page_size))
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Sequence, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


@dataclass
class PaginationParams:
    """分页查询参数（FastAPI Depends 注入）。"""

    page: int = Query(default=1, ge=1, description="页码")
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """统一分页响应格式。"""

    items: list[T]
    total: int
    page: int
    page_size: int


async def paginate(
    db: AsyncSession,
    model: Any,
    conditions: list[Any],
    order_col: Any,
    pagination: PaginationParams,
) -> tuple[Sequence[Any], int]:
    """通用分页查询：构建条件 → count → offset/limit 查询。

    Args:
        db: 数据库会话
        model: SQLAlchemy 模型类
        conditions: WHERE 条件列表
        order_col: 排序字段（通常为 Model.created_at）
        pagination: 分页参数

    Returns:
        (rows, total) 元组
    """
    # 计算总数
    count_stmt = select(func.count()).select_from(model)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = (await db.execute(count_stmt)).scalar_one()

    # 查询数据
    stmt = select(model)
    if conditions:
        stmt = stmt.where(*conditions)
    stmt = stmt.order_by(order_col.desc()).offset(pagination.offset).limit(pagination.limit)
    rows = list((await db.execute(stmt)).scalars().all())

    return rows, int(total)

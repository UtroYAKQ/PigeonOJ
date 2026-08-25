"""通用响应 Schema（统一信封 {code, message, data}）。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一 API 响应信封（docs/contracts/common.md）。"""

    code: int = 0
    message: str = "ok"
    data: Any = None


class PaginatedData(BaseModel):
    """分页数据信封。"""

    items: list[Any]
    total: int
    page: int
    page_size: int


class HealthStatus(BaseModel):
    """健康检查数据（GET /health）。"""

    status: Literal["ok"]

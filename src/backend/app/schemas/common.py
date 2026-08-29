"""通用响应 Schema（统一信封 {code, message, data}）。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthStatus(BaseModel):
    """健康检查数据（GET /health）。"""

    status: Literal["ok"]

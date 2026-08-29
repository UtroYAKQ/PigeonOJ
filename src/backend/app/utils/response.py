"""统一响应信封 {code, message, data}（docs/contracts/common.md）。

社区通行做法：信封定义为泛型 Pydantic 模型 ``ApiResponse[T]``，路由以
``response_model=ApiResponse[Xxx]`` 声明响应类型并直接返回 ``ok(...)`` 信封
实例，序列化与 OpenAPI 文档由 FastAPI 统一完成；业务代码不手工拼装字典、
不调用 ``model_dump``。

- code=0 表示成功，非 0 为错误码（错误码段见 docs/contracts/common.md）
- 错误信封仅由全局异常处理器经 ``error(...)`` 产生（app/core/exceptions.py）
"""
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应信封（docs/contracts/common.md）。"""

    code: int = 0
    message: str = "ok"
    data: T | None = None


def ok(data: T | None = None, message: str = "ok") -> ApiResponse[T]:
    """成功信封（code=0）：路由返回值的唯一出口。"""
    return ApiResponse(data=data, message=message)


def error(code: int, message: str) -> ApiResponse[None]:
    """错误信封（code≠0）：仅供全局异常处理器使用。"""
    return ApiResponse(code=code, message=message, data=None)

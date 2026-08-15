"""统一响应信封 {code, message, data}。

约定见 docs/contracts/common.md：code=0 表示成功，非 0 为错误码。
"""
from typing import Any


def ok(data: Any = None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


def error(code: int, message: str, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}

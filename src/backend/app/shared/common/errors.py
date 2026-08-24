"""错误码常量与业务异常。

错误码段约定见 docs/contracts/common.md：
10xx 参数校验 · 20xx 认证 / 授权 · 30xx 资源 · 40xx 频控 · 50xx 系统。
新增错误码必须先登记到 docs/contracts/common.md。
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException, RequestValidationError

from app.shared.common.response import error

# ---- 10xx 参数校验 ----
PARAM_FORMAT_INVALID = 1001  # 参数格式错误
PARAM_MISSING_REQUIRED = 1002  # 缺少必填参数

# ---- 20xx 认证 / 授权 ----
AUTH_NOT_LOGGED_IN = 2001  # 未登录
AUTH_SESSION_EXPIRED = 2002  # 会话过期
AUTH_FORBIDDEN = 2003  # 无权限
AUTH_INVALID_CREDENTIAL = 2004  # 账号或密码错误
REGISTER_DISABLED = 2005  # 站点未开放注册（docs/contracts/users.md）

# ---- 30xx 资源 ----
RESOURCE_NOT_FOUND = 3001  # 资源不存在
RESOURCE_STATE_CONFLICT = 3002  # 状态冲突
RESOURCE_DUPLICATE = 3003  # 资源已存在（重复）

# ---- 40xx 频控 ----
RATE_SEND_TOO_FREQUENT = 4001  # 发送太频繁
RATE_LIMITED = 4002  # 访问过频，请稍后再试

# ---- 50xx 系统 ----
SYSTEM_INTERNAL_ERROR = 5000  # 系统内部错误
SYSTEM_UPSTREAM_FAILURE = 5001  # AI / 沙箱等上游服务失败


class APIError(Exception):
    """业务错误：携带错误码与消息，由全局异常处理器转成统一信封。"""

    def __init__(self, code: int, message: str, http_status: int = 400) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """注册统一异常处理器，保证所有错误响应都是 {code, message, data} 信封。"""

    @app.exception_handler(APIError)
    async def _handle_api_error(_request, exc: APIError):
        return JSONResponse(
            status_code=exc.http_status,
            content=error(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_request, exc: RequestValidationError):
        # 路由函数执行前的参数校验失败（Query / Path / Body）统一转 1001 信封
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = ".".join(str(part) for part in first.get("loc", ()) if part not in ("body", "query"))
            detail = first.get("msg") or "参数不合法"
            message = f"{loc}: {detail}" if loc else detail
        else:
            message = "参数不合法"
        return JSONResponse(
            status_code=400,
            content=error(PARAM_FORMAT_INVALID, message),
        )

    @app.exception_handler(HTTPException)
    async def _handle_http_error(_request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.status_code, str(exc.detail)),
        )

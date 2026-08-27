"""错误码常量与业务异常。

错误码段约定见 docs/contracts/common.md：
10xx 参数校验 · 20xx 认证 / 授权 · 30xx 资源 · 40xx 频控 · 50xx 系统。
新增错误码必须先登记到 docs/contracts/common.md。
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException, RequestValidationError

from app.core.i18n import EN_US, resolve_locale, translate_message
from app.utils.response import error

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


# Pydantic 常见校验失败类型 → (中文文案, 英文文案；占位 {value} 取自 ctx 对应键)；
# 未命中类型回退通用文案。消息语言随请求 Accept-Language 协商（app/core/i18n.py）。
_VALIDATION_TYPE_MESSAGES: dict[str, tuple[str, str, str | None]] = {
    "missing": ("缺少必填字段", "Missing required field", None),
    "string_too_short": ("长度不能少于 {value} 字符", "Must be at least {value} character(s)", "min_length"),
    "string_too_long": ("长度不能超过 {value} 字符", "Must be at most {value} character(s)", "max_length"),
    "greater_than_equal": ("不能小于 {value}", "Must be at least {value}", "ge"),
    "greater_than": ("必须大于 {value}", "Must be greater than {value}", "gt"),
    "less_than_equal": ("不能大于 {value}", "Must be at most {value}", "le"),
    "less_than": ("必须小于 {value}", "Must be less than {value}", "lt"),
    "enum": ("取值不合法", "Invalid value", None),
    "literal_error": ("取值不合法", "Invalid value", None),
    "int_parsing": ("应为整数", "Expected an integer", None),
    "uuid_parsing": ("应为 UUID", "Expected a UUID", None),
    "string_type": ("应为字符串", "Expected a string", None),
    "json_invalid": ("JSON 格式不正确", "Invalid JSON", None),
}


def _validation_detail(first: dict, locale: str) -> str:
    """把单条 Pydantic 校验错误转为当前语言短语。

    自定义校验器（value_error）按项目约定抛中文消息，剥掉 pydantic 的
    "Value error, " 前缀后经 i18n 目录翻译；框架类型按映射表取双语模板。
    """
    err_type = str(first.get("type") or "")
    if err_type.startswith("value_error"):
        raw = str(first.get("msg") or "参数不合法").removeprefix("Value error, ").strip()
        return translate_message(raw, locale)
    entry = _VALIDATION_TYPE_MESSAGES.get(err_type)
    if entry:
        zh_template, en_template, ctx_key = entry
        template = en_template if locale == EN_US else zh_template
        ctx = first.get("ctx") or {}
        if ctx_key is None:
            return template
        if isinstance(ctx, dict) and ctx_key in ctx:
            return template.format(value=ctx[ctx_key])
    return "Invalid parameter format" if locale == EN_US else "参数格式不正确"


def register_exception_handlers(app: FastAPI) -> None:
    """注册统一异常处理器，保证所有错误响应都是 {code, message, data} 信封。

    message 语言随请求 Accept-Language 协商（zh-CN 默认 / en-US），
    翻译发生在异常处理出口，业务代码只抛中文消息（app/core/i18n.py）。
    """

    @app.exception_handler(APIError)
    async def _handle_api_error(request: Request, exc: APIError):
        locale = resolve_locale(request.headers.get("accept-language"))
        return JSONResponse(
            status_code=exc.http_status,
            content=error(exc.code, translate_message(exc.message, locale)),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError):
        # 路由函数执行前的参数校验失败（Query / Path / Body）统一转 1001 信封；
        # 消息为「字段名: 当前语言原因」，框架英文校验文案映射为双语短语
        locale = resolve_locale(request.headers.get("accept-language"))
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = ".".join(str(part) for part in first.get("loc", ()) if part not in ("body", "query"))
            detail = _validation_detail(first, locale)
            message = f"{loc}: {detail}" if loc else detail
        else:
            message = "Invalid parameter" if locale == EN_US else "参数不合法"
        return JSONResponse(
            status_code=400,
            content=error(PARAM_FORMAT_INVALID, message),
        )

    @app.exception_handler(HTTPException)
    async def _handle_http_error(request: Request, exc: HTTPException):
        locale = resolve_locale(request.headers.get("accept-language"))
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.status_code, translate_message(str(exc.detail), locale)),
        )

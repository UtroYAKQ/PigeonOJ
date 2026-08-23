"""错误码常量与业务异常（兼容层，已迁移至 shared/common/errors.py）。

保留此文件以兼容旧有导入：
    from app.shared.errors import APIError, register_exception_handlers

新代码请直接使用：
    from app.shared.common.errors import APIError, register_exception_handlers
"""
from app.shared.common.errors import (  # noqa: F401
    APIError,
    AUTH_FORBIDDEN,
    AUTH_INVALID_CREDENTIAL,
    AUTH_NOT_LOGGED_IN,
    AUTH_SESSION_EXPIRED,
    PARAM_FORMAT_INVALID,
    PARAM_MISSING_REQUIRED,
    RATE_LIMITED,
    RATE_SEND_TOO_FREQUENT,
    RESOURCE_DUPLICATE,
    RESOURCE_NOT_FOUND,
    RESOURCE_STATE_CONFLICT,
    SYSTEM_INTERNAL_ERROR,
    SYSTEM_UPSTREAM_FAILURE,
    register_exception_handlers,
)

__all__ = [
    "APIError",
    "PARAM_FORMAT_INVALID",
    "PARAM_MISSING_REQUIRED",
    "AUTH_NOT_LOGGED_IN",
    "AUTH_SESSION_EXPIRED",
    "AUTH_FORBIDDEN",
    "AUTH_INVALID_CREDENTIAL",
    "RESOURCE_NOT_FOUND",
    "RESOURCE_STATE_CONFLICT",
    "RESOURCE_DUPLICATE",
    "RATE_SEND_TOO_FREQUENT",
    "RATE_LIMITED",
    "SYSTEM_INTERNAL_ERROR",
    "SYSTEM_UPSTREAM_FAILURE",
    "register_exception_handlers",
]

"""审计域枚举：登录动作与日志级别。"""
from __future__ import annotations

from enum import StrEnum


class LoginAction(StrEnum):
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"
    RESET_PASSWORD = "reset_password"
    CHANGE_EMAIL = "change_email"


class LogLevel(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    FATAL = "fatal"

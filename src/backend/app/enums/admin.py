"""管理域枚举。"""
from __future__ import annotations

from enum import StrEnum


class ReportStatus(StrEnum):
    PENDING = "pending"
    HANDLED = "handled"
    IGNORED = "ignored"


class ReportAction(StrEnum):
    HANDLED = "handled"
    IGNORED = "ignored"


class ReportTargetType(StrEnum):
    PROBLEM = "problem"
    SOLUTION = "solution"
    POST = "post"
    COMMENT = "comment"
    USER = "user"

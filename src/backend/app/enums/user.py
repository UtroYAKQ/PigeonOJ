"""用户域枚举。"""
from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    FROZEN = "frozen"
    BANNED = "banned"
    DELETED = "deleted"


class Theme(StrEnum):
    LIGHT = "light"
    DARK = "dark"


class UserRoleScope(StrEnum):
    GLOBAL = "global"
    TEAM = "team"

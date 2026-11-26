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


class EditorFontFamily(StrEnum):
    """代码编辑器字体白名单（前端 @fontsource 打包或系统等宽栈，docs/contracts/users.md）。"""

    JETBRAINS_MONO = "jetbrains-mono"
    FIRA_CODE = "fira-code"
    SOURCE_CODE_PRO = "source-code-pro"
    IBM_PLEX_MONO = "ibm-plex-mono"
    CASCADIA_CODE = "cascadia-code"
    SYSTEM = "system"


class UserRoleScope(StrEnum):
    GLOBAL = "global"
    TEAM = "team"
    ORG = "org"


class RoleCode(StrEnum):
    """roles.code 种子值（docs/contracts/users.md；tutor 已随组织化改造下线）。"""

    ADMIN = "admin"
    USER = "user"
    TEAM_CREATOR = "team_creator"
    TEAM_ADMIN = "team_admin"
    TEAM_MEMBER = "team_member"
    ORG_ADMIN = "org_admin"
    ORG_MEMBER = "org_member"


class RoleLevel(StrEnum):
    """角色检查层级 / my_role 输出词汇（creator ⊇ admin ⊇ member，docs/contracts/teams.md）。"""

    CREATOR = "creator"
    ADMIN = "admin"
    MEMBER = "member"

"""团队域枚举。"""
from __future__ import annotations

from enum import StrEnum


class TeamStatus(StrEnum):
    ACTIVE = "active"
    DISBANDED = "disbanded"


class TeamVisibility(StrEnum):
    """团队可见性（docs/contracts/teams.md）：公开在团队中心可见、可直接申请加入；
    私有不进团队中心，仅经邀请链接申请加入。"""

    PRIVATE = "private"
    PUBLIC = "public"


class TeamMemberStatus(StrEnum):
    ACTIVE = "active"
    EXITED = "exited"
    KICKED = "kicked"


class TeamApplicationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

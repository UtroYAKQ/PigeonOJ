"""团队域枚举。"""
from __future__ import annotations

from enum import StrEnum


class TeamStatus(StrEnum):
    ACTIVE = "active"
    DISBANDED = "disbanded"


class TeamMemberStatus(StrEnum):
    ACTIVE = "active"
    EXITED = "exited"
    KICKED = "kicked"


class TeamApplicationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

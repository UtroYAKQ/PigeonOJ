"""组织域枚举。"""
from __future__ import annotations

from enum import StrEnum


class OrgStatus(StrEnum):
    ACTIVE = "active"
    DISBANDED = "disbanded"


class OrgMemberStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"

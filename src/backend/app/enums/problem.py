"""题库域枚举。"""
from __future__ import annotations

from enum import StrEnum


class ProblemStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ProblemVisibility(StrEnum):
    PRIVATE = "private"
    PUBLIC = "public"


class ProblemScope(StrEnum):
    ALL = "all"
    MINE = "mine"


class TagStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"

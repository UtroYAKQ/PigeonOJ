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


class CaseStatus(StrEnum):
    """测试点集合状态（problems.case_status 缓存列）。

    由 active_case_ids / pending_case_ids / pending_verified 推导
    。
    """

    EMPTY = "empty"
    TO_VERIFY = "to_verify"
    TO_REVERIFY = "to_reverify"
    VERIFIED = "verified"  # 已通过验题、待显式应用
    OK = "ok"


class ProblemSetStatus(StrEnum):
    """题单生命周期（docs/contracts/problem-sets.md）：不做物理删除，下线即归档。"""

    ACTIVE = "active"
    ARCHIVED = "archived"


class ProblemSetVisibility(StrEnum):
    """题单可见性：全站题单 public/private，团队题单 team（随 teams 模块开放）。"""

    PUBLIC = "public"
    PRIVATE = "private"
    TEAM = "team"

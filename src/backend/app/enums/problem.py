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
    （docs/decisions/2026-08-26-test-case-staged-promotion.md）。
    """

    EMPTY = "empty"
    TO_VERIFY = "to_verify"
    TO_REVERIFY = "to_reverify"
    VERIFIED = "verified"  # 已通过验题、待显式应用
    OK = "ok"

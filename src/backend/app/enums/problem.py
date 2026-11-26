"""题库域枚举。"""
from __future__ import annotations

from enum import StrEnum


class ProblemStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ProblemVisibility(StrEnum):
    """题目可见性（docs/contracts/problems.md 可见性三分支）：

    全站题目（org_id / team_id 均 NULL）：private / public；
    组织题目（org_id 非空）：org_visible（组织成员全员可见可编辑，团队管理者只读）；
    团队题目（team_id 非空）：admin_visible（仅团队创建者 / 管理员）/ team_visible（全队成员）。
    """

    PRIVATE = "private"
    PUBLIC = "public"
    ORG_VISIBLE = "org_visible"
    ADMIN_VISIBLE = "admin_visible"
    TEAM_VISIBLE = "team_visible"


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


class ImportStatus(StrEnum):
    """FPS 批量导入单题结果（schemas/problem.py FpsImportItemOut.status，
    docs/contracts/problems.md「FPS 题库导入」）。"""

    PUBLISHED = "published"
    DRAFT = "draft"
    DRAFT_SPJ = "draft_spj"
    DUPLICATE = "duplicate"
    SKIPPED_SPJ = "skipped_spj"
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
    """题单可见性：

    全站题单 public / private；团队题单恒 team_visible（全队成员可见；
    迁移 0043 起团队题单不再有 admin_visible 分支，存量回填为 team_visible）。
    """

    PUBLIC = "public"
    PRIVATE = "private"
    TEAM_VISIBLE = "team_visible"

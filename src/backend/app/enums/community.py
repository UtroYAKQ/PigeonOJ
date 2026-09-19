"""社区域枚举。"""
from __future__ import annotations

from enum import StrEnum


class SolutionStatus(StrEnum):
    """用户题解状态（docs/contracts/community.md solutions）：

    draft 仅作者可见；published 公开；removed 下架（作者删除或 admin 下架，
    作者与 admin 仍可读详情，恢复仅经 admin 端点）。
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    REMOVED = "removed"


class CommentTargetType(StrEnum):
    """评论目标类型（docs/contracts/community.md comments）；一期开放 solution / code_share。"""

    PROBLEM = "problem"
    SOLUTION = "solution"
    CODE_SHARE = "code_share"
    POST = "post"
    SUBMISSION = "submission"


class CodeShareStatus(StrEnum):
    """代码广场分享状态：无草稿态，直接发布；下架后仅作者与 admin 可读。"""

    PUBLISHED = "published"
    REMOVED = "removed"


class CodeShareLanguage(StrEnum):
    """代码广场语言白名单（首批与判题语言一致，docs/contracts/community.md code_shares）。"""

    CPP17 = "cpp17"
    PYTHON312 = "python3.12"
    JAVA21 = "java21"

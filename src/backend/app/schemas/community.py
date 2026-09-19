"""社区模块请求 / 响应 Schema（docs/contracts/community.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import CommentTargetType, SolutionStatus

# 评论目标白名单（community.md comments：一期仅 solution 开放；代码广场不设评论）
CommentTargetTypeLiteral = Literal["solution"]

CODE_SHARE_LANGUAGES = ("cpp17", "python3.12", "java21")
CodeShareLanguageLiteral = Literal["cpp17", "python3.12", "java21"]

SOLUTION_CONTENT_MAX_BYTES = 65536  # 题解正文上限（与提交代码 64KB 对齐）
COMMENT_CONTENT_MAX_CHARS = 2000


def _validate_content_size(value: str) -> str:
    """题解正文 ≤64KB（UTF-8 字节口径，与提交代码上限一致）。"""
    if len(value.encode("utf-8")) > SOLUTION_CONTENT_MAX_BYTES:
        raise ValueError("题解正文不能超过 64KB")
    return value


class AuthorBrief(BaseModel):
    """作者摘要（题解 / 评论列表与详情公共）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nickname: str
    avatar_url: str | None = None


class ProblemBrief(BaseModel):
    """题目摘要（管理列表定位用）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str


class EditorialOut(BaseModel):
    """官方题解浏览视图（problems.solution 的展示端点，community.md「官方题解」）。"""

    solution: str | None
    can_manage: bool


class SolutionCreate(BaseModel):
    """创建题解：无草稿态，创建即发布（community.md）。"""

    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("标题不能为空白")
        return title

    @field_validator("content")
    @classmethod
    def content_size(cls, value: str) -> str:
        return _validate_content_size(value)


class SolutionUpdate(BaseModel):
    """编辑题解（owner）：仅标题 / 正文；removed 态由服务层拒绝。"""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        title = value.strip()
        if not title:
            raise ValueError("标题不能为空白")
        return title

    @field_validator("content")
    @classmethod
    def content_size(cls, value: str | None) -> str | None:
        return None if value is None else _validate_content_size(value)


class SolutionSummary(BaseModel):
    """题解列表项（列表不回传正文全文，excerpt 供卡片预览）。"""

    id: uuid.UUID
    problem_id: uuid.UUID
    author: AuthorBrief
    title: str
    excerpt: str
    status: SolutionStatus
    comment_count: int = 0
    created_at: datetime
    updated_at: datetime


class SolutionDetail(SolutionSummary):
    """题解详情（含正文全文）。"""

    content: str


class CommentCreate(BaseModel):
    """发表评论 / 回复：parent_id 仅允许挂一级评论（服务层校验）。"""

    target_type: CommentTargetTypeLiteral
    target_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    content: str = Field(min_length=1, max_length=COMMENT_CONTENT_MAX_CHARS)

    @field_validator("target_type")
    @classmethod
    def supported_target(cls, value: str) -> str:
        if value != CommentTargetType.SOLUTION:
            raise ValueError("暂不支持该评论目标")
        return value


class CommentOut(BaseModel):
    """评论输出（软删占位：content / author 置空，行保留）。"""

    id: uuid.UUID
    parent_id: uuid.UUID | None
    content: str | None
    author: AuthorBrief | None
    is_deleted: bool
    created_at: datetime
    # 仅一级评论携带：未删回复数与前 2 条预览（详情回复接口返回空）
    reply_count: int = 0
    replies: list["CommentOut"] = []


class ReportCreate(BaseModel):
    """举报创建（community.md reports；target 存在性校验在服务层）。"""

    target_type: Literal["problem", "solution", "code_share", "post", "comment", "user"]
    target_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=1000)


class AdminSolutionStatusUpdate(BaseModel):
    """管理端题解下架 / 恢复（草稿不在此端点语义内）。"""

    status: Literal["published", "removed"]


class AdminCommentStatusUpdate(BaseModel):
    """管理端评论软删 / 恢复。"""

    is_deleted: bool


class CommentAdminOut(BaseModel):
    """评论管理上下文（举报定位：评论 → 所属题解 target_id）。"""

    id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    content: str | None
    is_deleted: bool
    created_at: datetime


# ---- 代码广场（community.md code_shares）----


class CodeShareCreate(BaseModel):
    """发布代码分享：无草稿态，直接发布；关联题目可选。"""

    title: str = Field(min_length=1, max_length=255)
    language: CodeShareLanguageLiteral
    code: str = Field(min_length=1)
    description: str | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("标题不能为空白")
        return title

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("代码内容不能为空白")
        if len(value.encode("utf-8")) > SOLUTION_CONTENT_MAX_BYTES:
            raise ValueError("代码内容不能超过 64KB")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value.encode("utf-8")) > SOLUTION_CONTENT_MAX_BYTES:
            raise ValueError("说明不能超过 64KB")
        return value


class CodeShareSummary(BaseModel):
    """分享列表项（说明截断摘要；关联题目摘要随行）。"""

    id: uuid.UUID
    author: AuthorBrief
    title: str
    language: str
    description_excerpt: str
    status: str
    created_at: datetime
    updated_at: datetime


class CodeShareDetail(CodeShareSummary):
    """分享详情（含代码原文与完整说明）。"""

    description: str | None
    code: str


class AdminCodeShareStatusUpdate(BaseModel):
    """管理端分享下架 / 恢复。"""

    status: Literal["published", "removed"]


class AdminCodeShareOut(BaseModel):
    """代码分享管理列表项（code 不回传，预览走详情端点）。"""

    id: uuid.UUID
    author: AuthorBrief
    title: str
    language: str
    excerpt: str
    status: str
    created_at: datetime
    updated_at: datetime


class AdminSolutionOut(BaseModel):
    """题解管理列表项（全状态；content 不回传，预览走详情端点）。"""

    id: uuid.UUID
    problem: ProblemBrief
    author: AuthorBrief
    title: str
    excerpt: str
    status: SolutionStatus
    comment_count: int = 0
    created_at: datetime
    updated_at: datetime

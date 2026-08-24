"""题库模块请求 / 响应 Schema（docs/contracts/problems.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProblemCreate(BaseModel):
    """创建题目：生命周期只允许从 draft 起步，发布走 POST /problems/{id}/publish。"""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    input_description: str | None = None
    output_description: str | None = None
    solution: str | None = None
    difficulty: str = Field(default="easy", pattern="^(easy|medium|hard)$")
    visibility: str = Field(default="public", pattern="^(private|public)$")
    time_limit_ms: int = Field(default=1000, ge=1, le=60000)
    memory_limit_mb: int = Field(default=256, ge=16, le=4096)


class ProblemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    input_description: str | None = None
    output_description: str | None = None
    solution: str | None = None
    difficulty: str | None = Field(default=None, pattern="^(easy|medium|hard)$")
    visibility: str | None = Field(default=None, pattern="^(private|public)$")
    time_limit_ms: int | None = Field(default=None, ge=1, le=60000)
    memory_limit_mb: int | None = Field(default=None, ge=16, le=4096)


class ProblemQuery(BaseModel):
    """题库列表查询（docs/contracts/common.md 分页契约）。

    scope=all：题库中心，仅 published + public；
    scope=mine：我的题目管理视图（须登录）——创建者看自己的全部题目，
    管理角色（admin/tutor/team_creator）可管理范围内全量；可叠加 status 过滤。
    """

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    difficulty: str | None = Field(default=None, pattern="^(easy|medium|hard)$")
    keyword: str | None = Field(default=None, max_length=128)
    tag: str | None = Field(default=None, max_length=64)
    scope: str = Field(default="all", pattern="^(all|mine)$")
    status: str | None = Field(default=None, pattern="^(draft|published|archived)$")


class TestCaseItem(BaseModel):
    id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=64)
    is_sample: bool = False
    input: str = Field(default="", max_length=2 * 1024 * 1024)
    expected_output: str = Field(default="", max_length=2 * 1024 * 1024)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("input", "expected_output")
    @classmethod
    def content_bytes_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 2 * 1024 * 1024:
            raise ValueError("test case content exceeds 2MB")
        return value


class TestCasesUpdate(BaseModel):
    cases: list[TestCaseItem] = Field(min_length=1, max_length=1000)


# ---- Response Schemas（统一 ORM 序列化） ----


class ProblemSummary(BaseModel):
    """题目列表项摘要（不含详情字段）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    difficulty: str
    time_limit_ms: int
    memory_limit_mb: int
    status: str
    visibility: str
    is_verified: bool
    created_at: datetime


class ProblemDetail(BaseModel):
    """题目详情（含描述、样例、标签等）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    input_description: str | None
    output_description: str | None
    solution: str | None
    difficulty: str
    time_limit_ms: int
    memory_limit_mb: int
    status: str
    visibility: str
    is_verified: bool
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    owner_id: uuid.UUID
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

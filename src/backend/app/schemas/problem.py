"""题库模块请求 / 响应 Schema（docs/contracts/problems.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean_tag_names(names: list[str]) -> list[str]:
    """去空白、去重、保序；空白项剔除（docs/contracts/problems.md 标签节）。"""
    cleaned: list[str] = []
    for raw in names:
        name = raw.strip()
        if name and name not in cleaned:
            cleaned.append(name)
    return cleaned


class ProblemCreate(BaseModel):
    """创建题目：生命周期只允许从 draft 起步，发布走 POST /problems/{id}/publish。

    题面四要素（题面 / 输入说明 / 输出说明）均为必填；tags 为激活标签名（≤8）。
    """

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    input_description: str = Field(min_length=1)
    output_description: str = Field(min_length=1)
    solution: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=8)
    visibility: str = Field(default="public", pattern="^(private|public)$")
    time_limit_ms: int = Field(default=1000, ge=1, le=60000)
    memory_limit_mb: int = Field(default=256, ge=16, le=4096)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return _clean_tag_names(value)


class ProblemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    input_description: str | None = None
    output_description: str | None = None
    solution: str | None = None
    # None = 不改动标签关联；空数组 = 清空
    tags: list[str] | None = Field(default=None, max_length=8)
    visibility: str | None = Field(default=None, pattern="^(private|public)$")
    time_limit_ms: int | None = Field(default=None, ge=1, le=60000)
    memory_limit_mb: int | None = Field(default=None, ge=16, le=4096)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_tag_names(value)


class ProblemQuery(BaseModel):
    """题库列表查询（docs/contracts/common.md 分页契约）。

    scope=all：题库中心，仅 published + public；
    scope=mine：我的题目管理视图（须登录）——创建者看自己的全部题目，
    管理角色（admin/tutor/team_creator）可管理范围内全量；可叠加 status 过滤。
    """

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    keyword: str | None = Field(default=None, max_length=128)
    tag: str | None = Field(default=None, max_length=64)
    scope: str = Field(default="all", pattern="^(all|mine)$")
    status: str | None = Field(default=None, pattern="^(draft|published|archived)$")


class TestCaseItem(BaseModel):
    id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=64)
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


class SampleItem(BaseModel):
    """展示样例（存 problems.samples JSONB；仅展示与自测，不参与判题）。"""

    input: str = Field(default="")
    output: str = Field(default="")

    @field_validator("input", "output")
    @classmethod
    def content_bytes_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 64 * 1024:
            raise ValueError("sample content exceeds 64KB")
        return value


class SamplesUpdate(BaseModel):
    samples: list[SampleItem] = Field(default_factory=list, max_length=10)


# ---- 标签管理（admin，docs/contracts/problems.md 标签节） ----


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=16)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=16)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()


class TagOut(BaseModel):
    """标签（管理端含 status；公开列表仅返回激活标签）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: str | None
    status: str
    created_at: datetime


# ---- Response Schemas（统一 ORM 序列化） ----


class ProblemSummary(BaseModel):
    """题目列表项摘要（不含详情字段）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
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

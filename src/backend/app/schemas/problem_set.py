"""题单模块请求 / 响应 Schema（docs/contracts/problem-sets.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums import ProblemSetStatus, ProblemSetVisibility


class ProblemSetCreate(BaseModel):
    """创建题单：全站题单 public/private（admin/tutor）；团队题单随 teams 模块开放。"""

    title: str = Field(min_length=1, max_length=128)
    description: str | None = None
    visibility: ProblemSetVisibility = ProblemSetVisibility.PUBLIC

    @model_validator(mode="after")
    def check_visibility(self) -> ProblemSetCreate:
        if self.visibility == ProblemSetVisibility.TEAM:
            raise ValueError("团队题单随 teams 模块开放")
        return self


class ProblemSetUpdate(BaseModel):
    """编辑题单元信息（title / description / visibility 全量语义：传即改，缺省不动）。"""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    visibility: ProblemSetVisibility | None = None

    @model_validator(mode="after")
    def check_visibility(self) -> ProblemSetUpdate:
        if self.visibility == ProblemSetVisibility.TEAM:
            raise ValueError("团队题单随 teams 模块开放")
        return self


class ProblemSetItemsUpdate(BaseModel):
    """编排题目：全量替换题单内列表；同一题单内 problem_id 不得重复。"""

    model_config = ConfigDict(extra="forbid")

    items: list["ProblemSetItemIn"] = Field(default_factory=list, max_length=200)


class ProblemSetItemIn(BaseModel):
    problem_id: uuid.UUID
    sort_order: int = Field(default=0, ge=0)


class ProblemSetItemOut(BaseModel):
    """题单内题目项（题目元信息随行返回，供详情页直接渲染）。"""

    model_config = ConfigDict(from_attributes=True)

    problem_id: uuid.UUID
    title: str
    difficulty: int | None = None
    sort_order: int


class ProblemSetSummary(BaseModel):
    """题单列表项（题单中心 / 管理视图共用）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None = None
    visibility: ProblemSetVisibility
    status: ProblemSetStatus
    owner_id: uuid.UUID
    item_count: int = 0
    created_at: datetime
    updated_at: datetime


class ProblemSetDetail(ProblemSetSummary):
    """题单详情：题目按 sort_order 展示（刷题不强制按序完成）。"""

    items: list[ProblemSetItemOut] = Field(default_factory=list)
    can_manage: bool = False


class ProblemSetSubmissionCreate(BaseModel):
    """题单内交题（POST /problem-sets/{id}/problems/{pid}/submissions）。

    problem_id 由路径提供（且必须属于该题单）；代码上限与练习提交一致（64KB UTF-8 字节）。
    """

    language: str = Field(max_length=32)
    code: str = Field(min_length=1, max_length=65536)

    @field_validator("code")
    @classmethod
    def code_bytes_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 64 * 1024:
            raise ValueError("代码不能超过 64KB")
        return value

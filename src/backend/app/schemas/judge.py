"""判题模块请求模型（docs/contracts/judge.md）。题库 Schema 在 problems 模块。"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class VerifyRequest(BaseModel):
    """POST /problems/{id}/verify 的双模式请求体：

    - 发起验题（题目管理角色）：invite_expires_hours 传值则生成链接邀请；
      不传则创建空白 pending 记录（出题人 / 管理角色自行验题）
    - 提交验题代码：code + language（+ invite_token，凭邀请链接时）
    """

    invite_expires_hours: int | None = Field(default=None, ge=1, le=24 * 30)
    invite_token: str | None = Field(default=None, max_length=64)
    code: str | None = Field(default=None, min_length=1, max_length=65536)
    language: str | None = Field(default=None, max_length=32)

    @field_validator("code")
    @classmethod
    def code_bytes_limit(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > 64 * 1024:
            raise ValueError("code exceeds 64KB")
        return value

    @model_validator(mode="after")
    def check_mode(self) -> "VerifyRequest":
        if self.code is not None:
            if not self.language:
                raise ValueError("language is required when submitting verification code")
            return self
        return self


class SubmissionCreate(BaseModel):
    """练习提交；比赛 / 验题提交的上下文均由服务端推导，不信任客户端传入。"""

    problem_id: uuid.UUID
    language: str
    code: str = Field(min_length=1, max_length=65536)

    @field_validator("code")
    @classmethod
    def code_bytes_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 64 * 1024:
            raise ValueError("code exceeds 64KB")
        return value


class SubmissionQuery(BaseModel):
    """提交历史查询（本人数据，WHERE user_id = ?）。"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    problem_id: uuid.UUID | None = None
    status: str | None = Field(
        default=None,
        pattern="^(pending|judging|accepted|wrong_answer|time_limit_exceeded|memory_limit_exceeded|output_limit_exceeded|runtime_error|compile_error|system_error)$",
    )


# ---- Response Schemas（统一 ORM 序列化） ----


class SubmissionSummary(BaseModel):
    """提交列表项摘要。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problem_id: uuid.UUID
    language: str
    submit_type: str
    status: str
    score: int | None
    time_used_ms: int | None
    memory_used_kb: int | None
    created_at: datetime


class SubmissionDetail(BaseModel):
    """提交详情（含代码和测试点结果）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problem_id: uuid.UUID
    language: str
    submit_type: str
    code: str
    status: str
    score: int | None
    time_used_ms: int | None
    memory_used_kb: int | None
    error_message: str | None
    created_at: datetime


class TestCaseResult(BaseModel):
    """单个测试点结果。"""

    id: uuid.UUID
    case_name: str
    status: str
    time_used_ms: int | None
    memory_used_kb: int | None
    score: int | None
    output: str | None

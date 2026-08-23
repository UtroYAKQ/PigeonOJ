"""判题 / 题库模块请求模型（docs/contracts/problems.md、judge.md）。"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    spj: bool = False
    spj_code: str | None = Field(default=None, max_length=512)


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
    spj: bool | None = None
    spj_code: str | None = Field(default=None, max_length=512)


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
    score: int = Field(default=0, ge=0)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("input", "expected_output")
    @classmethod
    def content_bytes_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 2 * 1024 * 1024:
            raise ValueError("test case content exceeds 2MB")
        return value


class TestCasesUpdate(BaseModel):
    cases: list[TestCaseItem] = Field(min_length=1, max_length=1000)


class VerifyRequest(BaseModel):
    """POST /problems/{id}/verify 的双模式请求体：

    - 发起验题（题目管理角色）：verifier_id 与 invite_expires_hours 二选一
    - 提交验题代码（受邀验题人）：code + language（+ invite_token，凭邀请链接时）
    """

    verifier_id: uuid.UUID | None = None
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
        if self.verifier_id is not None and self.invite_expires_hours is not None:
            raise ValueError("choose either verifier_id or invite_expires_hours")
        if self.verifier_id is None and self.invite_expires_hours is None:
            raise ValueError("verifier_id or invite_expires_hours is required to start a verification")
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


class ProblemSummary(BaseModel):
    """题目列表项摘要（不含详情字段）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    difficulty: str
    time_limit_ms: int
    memory_limit_mb: int
    spj: bool
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
    spj: bool
    spj_code: str | None
    status: str
    visibility: str
    is_verified: bool
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    owner_id: uuid.UUID
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


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


# 导入 datetime 用于类型注解
from datetime import datetime

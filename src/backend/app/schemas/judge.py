"""判题模块请求模型（docs/contracts/judge.md）。题库 Schema 在 problems 模块。"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums import SubmissionStatus, SubmitType
from app.schemas.admin import SandboxNodeOut


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
            raise ValueError("代码不能超过 64KB")
        return value

    @model_validator(mode="after")
    def check_mode(self) -> "VerifyRequest":
        if self.code is not None:
            if not self.language:
                raise ValueError("提交验题代码时必须指定语言")
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
            raise ValueError("代码不能超过 64KB")
        return value


class SubmissionQuery(BaseModel):
    """提交历史查询（本人数据，WHERE user_id = ?）。"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    problem_id: uuid.UUID | None = None
    status: SubmissionStatus | None = None


# ---- Response Schemas（统一 ORM 序列化） ----


class SubmissionSummary(BaseModel):
    """提交列表项摘要。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problem_id: uuid.UUID
    language: str
    submit_type: SubmitType
    status: SubmissionStatus
    # 赛制计分（docs/contracts/judge.md「赛制计分」）：ACM 二值（AC=满分否则 0）；
    # IOI / 练习 / 验题 = 通过测试点比例部分计分
    score: int
    time_used_ms: int | None
    memory_used_kb: int | None
    created_at: datetime


class SubmissionDetail(BaseModel):
    """提交详情（含代码和测试点结果）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problem_id: uuid.UUID
    language: str
    submit_type: SubmitType
    code: str
    status: SubmissionStatus
    score: int
    time_used_ms: int | None
    memory_used_kb: int | None
    error_message: str | None
    created_at: datetime


class TestCaseResult(BaseModel):
    """单个测试点结果。"""

    id: uuid.UUID
    case_name: str | None
    status: SubmissionStatus
    time_used_ms: int | None
    memory_used_kb: int | None
    score: int | None
    output: str | None


class SubmissionDetailOut(SubmissionDetail):
    """提交详情响应：详情字段 + 逐测试点明细。"""

    cases: list[TestCaseResult] = []


class SubmissionCreatedResponse(BaseModel):
    """提交创建响应。"""

    submission_id: str
    status: SubmissionStatus


class SelfTestRequest(BaseModel):
    """用户自测请求（POST /problems/{id}/run-code；单次运行，无测试点管理）。

    input 为自定义 stdin（可空）；代码上限与提交一致（64KB UTF-8 字节）。
    """

    language: str = Field(max_length=32)
    code: str = Field(min_length=1, max_length=65536)
    input: str | None = Field(default=None, max_length=65536)

    @field_validator("code")
    @classmethod
    def code_bytes_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 64 * 1024:
            raise ValueError("代码不能超过 64KB")
        return value

    @field_validator("input")
    @classmethod
    def input_bytes_limit(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > 64 * 1024:
            raise ValueError("输入不能超过 64KB")
        return value


class SelfTestResultOut(BaseModel):
    """用户自测结果：程序 stdout 与运行元信息（无比对、不计分、不落库）。"""

    status: str
    output: str
    error_message: str | None = None
    time_used_ms: int
    memory_used_kb: int | None = None


class SandboxHealthOut(BaseModel):
    """沙箱节点健康（GET /sandbox/health；节点状态来自网关注册表）。"""

    nodes: list[SandboxNodeOut] = []

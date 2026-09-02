"""题库模块请求 / 响应 Schema（docs/contracts/problems.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums import ProblemScope, ProblemStatus, ProblemVisibility, TagStatus


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

    题面要素（题目背景 / 题面 / 输入说明 / 输出说明）均为必填；tags 为激活标签名（≤8）。
    """

    title: str = Field(min_length=1, max_length=255)
    background: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_description: str = Field(min_length=1)
    output_description: str = Field(min_length=1)
    # 题面说明（可选，Markdown，详情页渲染于题面最后）
    note: str | None = None
    solution: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=8)
    visibility: ProblemVisibility = ProblemVisibility.PUBLIC
    time_limit_ms: int = Field(default=1000, ge=1, le=60000)
    memory_limit_mb: int = Field(default=256, ge=16, le=4096)
    # 难度分（手动填写；NULL=未评分；仅约束非负，不设上限）
    difficulty: int | None = Field(default=None, ge=0)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return _clean_tag_names(value)


class ProblemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    background: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    input_description: str | None = None
    output_description: str | None = None
    # None = 不改动；"" = 清空
    note: str | None = None
    solution: str | None = None
    # None = 不改动标签关联；空数组 = 清空
    tags: list[str] | None = Field(default=None, max_length=8)
    visibility: ProblemVisibility | None = None
    time_limit_ms: int | None = Field(default=None, ge=1, le=60000)
    memory_limit_mb: int | None = Field(default=None, ge=16, le=4096)
    # None = 不改动（沿用本 Schema 既有约定，暂不支持清空为未评分）
    difficulty: int | None = Field(default=None, ge=0)

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
    scope: ProblemScope = ProblemScope.ALL
    status: ProblemStatus | None = None
    # 难度分闭区间筛选（未评分题目不落在任何区间内）
    difficulty_min: int | None = Field(default=None, ge=0)
    difficulty_max: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check_difficulty_range(self) -> ProblemQuery:
        if (
            self.difficulty_min is not None and self.difficulty_max is not None
            and self.difficulty_min > self.difficulty_max
        ):
            raise ValueError("difficulty_min 不能大于 difficulty_max")
        return self


class TestCaseItem(BaseModel):
    id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=64)
    # PATCH 增量语义：None（字段缺省或显式 null）= 内容不变；字符串（含 ""）= 设置为该内容
    input: str | None = Field(default=None, max_length=5 * 1024 * 1024)
    expected_output: str | None = Field(default=None, max_length=5 * 1024 * 1024)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("input", "expected_output")
    @classmethod
    def content_bytes_limit(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > 5 * 1024 * 1024:
            raise ValueError("测试点内容不能超过 5MB")
        return value


class TestCasesUpdate(BaseModel):
    cases: list[TestCaseItem] = Field(min_length=1, max_length=1000)


class TestCasesPatch(BaseModel):
    """增量更新暂存集（行不可变版本化，生效集在晋升前不受影响）：

    - upserts：带 id 为修改既有测试点（input / expected_output 缺省或 null = 内容不变，
      可仅改名或调序；传字符串则整体替换该侧内容，空字符串 = 显式清空——写入空对象；
      有效变更生成新版本行，origin_id 指回原行；两侧同时置空返回 1001）；
      不带 id 为新增（输入输出不能全空）
    - delete_ids：目标状态中不含该点（旧行退役留档）；目标状态不允许为空
    - delete_ids 与 upserts 的 id 均须存在于当前目标视图（未知 id 返回 3001）
    """

    upserts: list[TestCaseItem] = Field(default_factory=list, max_length=1000)
    delete_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)


class SampleItem(BaseModel):
    """展示样例（存 problems.samples JSONB；仅展示与自测，不参与判题）。

    explanation 为选填样例解释（Markdown，≤64KB；空 = 该组样例无解释）。
    """

    input: str = Field(default="")
    output: str = Field(default="")
    explanation: str | None = None

    @field_validator("input", "output")
    @classmethod
    def content_bytes_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 64 * 1024:
            raise ValueError("样例内容不能超过 64KB")
        return value

    @field_validator("explanation")
    @classmethod
    def explanation_bytes_limit(cls, value: str | None) -> str | None:
        if value is not None and value != "" and len(value.encode("utf-8")) > 64 * 1024:
            raise ValueError("样例解释不能超过 64KB")
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
    status: TagStatus
    created_at: datetime


class TagPublic(BaseModel):
    """公开标签（仅 id/name/color，用于打标选择器与题库筛选）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: str | None


# ---- Response Schemas（统一 ORM 序列化） ----


class SampleOut(BaseModel):
    """展示样例输出（name 按序派生，不暴露内部 id）。

    explanation 为样例解释（空字符串 = 无解释，前端不渲染解释区块）。
    """

    name: str
    input: str
    output: str
    explanation: str = ""


class ProblemSummary(BaseModel):
    """题目列表项摘要（不含详情字段）。

    needs_reverification 仅 scope=mine 视图有意义（其他场景恒为 False）。
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    time_limit_ms: int
    memory_limit_mb: int
    status: ProblemStatus
    visibility: ProblemVisibility
    is_verified: bool
    created_at: datetime
    needs_reverification: bool = False
    # 难度分（NULL=未评分）；计数来自 problem_counters（API 层回填，无记录按 0）
    difficulty: int | None = None
    submission_count: int = 0
    accepted_count: int = 0


class TestCaseOut(BaseModel):
    """测试点输出（管理角色可见）。

    staged=true 表示当前返回的是暂存目标状态（存在未验证改动或尚未首验）；
    验题通过晋升后全部转为 staged=false。
    """

    id: str
    name: str | None
    sort_order: int
    input: str | None
    expected_output: str | None
    staged: bool = False


class TestCasesOut(BaseModel):
    """增量更新测试点响应：目标状态合并视图（PATCH /problems/{id}/test-cases）。"""

    cases: list[TestCaseOut]


class ProblemDetail(BaseModel):
    """题目详情（含描述、样例、标签等）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    background: str
    description: str
    input_description: str | None
    output_description: str | None
    note: str | None = None
    solution: str | None = None
    time_limit_ms: int
    memory_limit_mb: int
    status: ProblemStatus
    visibility: ProblemVisibility
    is_verified: bool
    verified_by: uuid.UUID | None = None
    verified_at: datetime | None = None
    owner_id: uuid.UUID
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    difficulty: int | None = None
    submission_count: int = 0
    accepted_count: int = 0
    samples: list[SampleOut] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    can_manage: bool = False
    needs_reverification: bool = False
    case_status: str | None = None
    test_cases: list[TestCaseOut] | None = None
    cases_updated_at: datetime | None = None
    samples_updated_at: datetime | None = None


# ---- 验题相关 Response Schemas ----


class VerificationInviteLink(BaseModel):
    """验题邀请链接（token + 由 Redis TTL 推算的过期时间）。"""

    token: str
    expires_at: datetime


class VerificationInviteOut(BaseModel):
    """验题邀请详情。"""

    problem_id: str
    problem_title: str
    expires_at: datetime | None
    background: str
    description: str
    input_description: str | None
    output_description: str | None
    note: str | None = None
    tags: list[str]
    time_limit_ms: int
    memory_limit_mb: int
    samples: list[SampleOut]


class VerificationInitOut(BaseModel):
    """发起验题响应（邀请模式下附邀请链接；无邀请时 invite 为 None）。"""

    verification_id: str
    invite: VerificationInviteLink | None = None


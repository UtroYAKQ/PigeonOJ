"""比赛模块请求 / 响应 Schema（docs/contracts/contests.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import ContestStatus, ContestType, RegistrationStatus, RuleType, SubmissionStatus


class ContestProblemIn(BaseModel):
    """比赛题目编排项（letter 按顺序自动分配；score 为 IOI 单题分值）。"""

    problem_id: uuid.UUID
    score: int = Field(default=0, ge=0)


class ContestCreate(BaseModel):
    """创建比赛（全站公开赛；团队赛随 teams 模块开放）。"""

    title: str = Field(min_length=1, max_length=128)
    description: str | None = None
    # 比赛头像 URL（经 /files/upload/image 上传后的公开地址；≤512）
    logo: str | None = Field(default=None, max_length=512)
    rule_type: RuleType
    start_time: datetime
    end_time: datetime
    register_start_time: datetime
    register_end_time: datetime
    freeze_offset_seconds: int = Field(default=0, ge=0)
    problems: list[ContestProblemIn] = Field(default_factory=list, max_length=26)

    @model_validator(mode="after")
    def check_times(self) -> ContestCreate:
        if self.start_time >= self.end_time:
            raise ValueError("结束时间必须晚于开始时间")
        if self.register_start_time > self.register_end_time:
            raise ValueError("报名开始时间不能晚于报名截止时间")
        if self.register_end_time > self.end_time:
            raise ValueError("报名截止不能晚于比赛结束")
        return self


class ContestUpdate(BaseModel):
    """编辑比赛（缺省不动；problems 传即全量重排；时间合法性在服务层对合并值校验）。"""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    logo: str | None = Field(default=None, max_length=512)
    rule_type: RuleType | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    register_start_time: datetime | None = None
    register_end_time: datetime | None = None
    freeze_offset_seconds: int | None = Field(default=None, ge=0)
    problems: list[ContestProblemIn] | None = Field(default=None, max_length=26)


class ContestProblemItemOut(BaseModel):
    """比赛题目列表项（letter 为榜单元信息；详情另经统一入口端点获取）。"""

    model_config = ConfigDict(from_attributes=True)

    problem_id: uuid.UUID
    letter: str | None = None
    score: int
    sort_order: int
    title: str
    difficulty: int | None = None


class ContestSummary(BaseModel):
    """比赛列表项（中心 / 我的比赛 / 管理视图共用）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None = None
    logo: str | None = None
    contest_type: ContestType
    rule_type: RuleType
    start_time: datetime
    end_time: datetime
    register_start_time: datetime
    register_end_time: datetime
    freeze_offset_seconds: int
    board_frozen: bool
    status: ContestStatus
    problem_count: int = 0
    registered_count: int = 0
    created_at: datetime
    updated_at: datetime


class ContestDetail(ContestSummary):
    """比赛详情：报名状态与时间窗口能力位；题目仅在看题窗口内携带。"""

    my_registration: RegistrationStatus | None = None
    can_register: bool = False
    can_view_problems: bool = False
    can_submit: bool = False
    can_manage: bool = False
    problems: list[ContestProblemItemOut] = Field(default_factory=list)


class BoardCell(BaseModel):
    """榜单单题格子（is_frozen=true 表示封榜快照，非实时数据）。"""

    problem_id: uuid.UUID
    letter: str | None = None
    problem_score: int = 0
    accepted: bool = False
    attempts: int = 0
    penalty: int = 0
    score: int = 0
    is_frozen: bool = False
    accepted_at: datetime | None = None


class BoardRow(BaseModel):
    """榜单行（rank 由服务端按赛制排序后写入）。"""

    rank: int
    user_id: uuid.UUID
    nickname: str
    solved: int
    total_penalty: int
    total_score: int
    cells: list[BoardCell] = Field(default_factory=list)


class BoardOut(BaseModel):
    """榜单（封榜时按冻结快照展示；board_frozen=true 时前端提示等待解冻）。"""

    contest_id: uuid.UUID
    rule_type: RuleType
    board_frozen: bool
    rows: list[BoardRow] = Field(default_factory=list)


class ContestSubmissionItem(BaseModel):
    """比赛提交记录列表项（比赛期间对所有人隐藏，赛后开放；docs/contracts/contests.md 第 7 条）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problem_id: uuid.UUID
    letter: str | None = None
    language: str
    status: SubmissionStatus
    score: int | None = None
    time_used_ms: int | None = None
    memory_used_kb: int | None = None
    nickname: str
    created_at: datetime


class MyContestItem(ContestSummary):
    """我的比赛项（我报名的比赛 + 报名状态）。"""

    my_registration: RegistrationStatus = RegistrationStatus.REGISTERED

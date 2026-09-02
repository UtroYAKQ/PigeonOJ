"""比赛模块请求 / 响应 Schema（docs/contracts/contests.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import ContestStatus, ContestType, RegistrationStatus, RuleType, SubmissionStatus


def _aware(value: datetime) -> datetime:
    """naive 输入按 UTC 归一（与 service 层口径一致）。"""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


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
    # 封榜时间（绝对时刻；NULL = 不封榜；服务层校验 start < freeze_time <= end）
    freeze_time: datetime | None = None
    problems: list[ContestProblemIn] = Field(default_factory=list, max_length=26)

    @model_validator(mode="after")
    def check_times(self) -> ContestCreate:
        if self.start_time >= self.end_time:
            raise ValueError("结束时间必须晚于开始时间")
        if self.register_start_time > self.register_end_time:
            raise ValueError("报名开始时间不能晚于报名截止时间")
        if self.register_end_time > self.end_time:
            raise ValueError("报名截止不能晚于比赛结束")
        if self.freeze_time is not None and not (
            self.start_time < _aware(self.freeze_time) <= self.end_time
        ):
            raise ValueError("封榜时间必须晚于开始时间且不晚于结束时间")
        return self


class ContestUpdate(BaseModel):
    """编辑比赛（缺省不动；problems 传即全量重排；时间合法性在服务层对合并值校验）。

    赛时守卫：比赛开始后（status != scheduled）结构性字段被服务层拒绝（3002）——
    赛中调整走受控端点（公告 PUT /announcement；延时与封榜策略后续迭代）。
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    logo: str | None = Field(default=None, max_length=512)
    rule_type: RuleType | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    register_start_time: datetime | None = None
    register_end_time: datetime | None = None
    # 封榜时间（绝对时刻；缺省 = 不改动，显式 null = 取消封榜）
    freeze_time: datetime | None = Field(default=None)
    problems: list[ContestProblemIn] | None = Field(default=None, max_length=26)


class AnnouncementUpdate(BaseModel):
    """比赛公告更新（PUT /contests/{id}/announcement；空字符串 = 清空公告）。"""

    announcement: str = Field(default="", max_length=64 * 1024)


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
    # 封榜时间（绝对时刻；NULL = 不封榜）
    freeze_time: datetime | None = None
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
    # 比赛公告（Markdown，赛时可改；主页 tab 公告条展示，空 = 未发布公告）
    announcement: str | None = None
    announcement_updated_at: datetime | None = None
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


# ---- 滚榜（赛后大屏工具；数据只读，不改变榜单状态） ----


class RevealStep(BaseModel):
    """滚榜单步：揭晓一条封榜期提交（队伍行随之重排动画）。"""

    user_id: uuid.UUID
    nickname: str
    problem_id: uuid.UUID
    letter: str | None = None
    submission_id: uuid.UUID
    created_at: datetime
    accepted: bool
    # IOI：该步后该格分数（ACM 恒 0，格子展示用 accepted / 罚时）
    score: int = 0
    # ACM：该步后该格罚时（分钟，含历史罚时系数）
    penalty: int = 0
    # 该步后该格尝试次数（ACM 展示 WA 药丸用）
    attempts: int = 0


class ScoreboardShowOut(BaseModel):
    """滚榜数据包：冻结快照榜（起点）+ 最终榜（终点）+ 揭晓序列（动画步骤）。

    队伍揭晓顺序由服务端按「最终名次从差到好」生成，保证动画中
    每支队伍结算后不再移动（domjudge 式滚榜，docs/contracts/contests.md）。
    """

    contest_id: uuid.UUID
    title: str
    rule_type: RuleType
    board_frozen: bool
    frozen_at: datetime | None = None
    problems: list[ContestProblemItemOut] = Field(default_factory=list)
    base_rows: list[BoardRow] = Field(default_factory=list)
    final_rows: list[BoardRow] = Field(default_factory=list)
    steps: list[RevealStep] = Field(default_factory=list)

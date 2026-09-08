"""团队模块请求 / 响应模型（docs/contracts/teams.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums import (
    ProblemSetVisibility,
    ProblemVisibility,
    TeamApplicationStatus,
    TeamMemberStatus,
    TeamStatus,
    TeamVisibility,
)
from app.schemas.contest import ContestCreate
from app.utils.validation import validate_nickname


class TeamCreate(BaseModel):
    """创建团队（admin/tutor；创建人自动成为成员并获 team_creator 授权）。

    visibility：public 团队中心可见可直接申请加入；private 仅经邀请链接申请（默认）。
    """

    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    avatar_url: str | None = Field(default=None, max_length=512)
    visibility: TeamVisibility = TeamVisibility.PRIVATE

    @field_validator("name")
    @classmethod
    def name_valid(cls, value: str) -> str:
        # 复用昵称规则：1-64 可见字符、去首尾空白
        validate_nickname(value)
        return value.strip()


class TeamUpdate(BaseModel):
    """编辑团队信息（缺省不动；avatar_url 由前端经图片上传获得外链后传入）。"""

    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    avatar_url: str | None = Field(default=None, max_length=512)
    visibility: TeamVisibility | None = None

    @field_validator("name")
    @classmethod
    def name_valid(cls, value: str | None) -> str | None:
        if value is not None:
            validate_nickname(value)
        return value.strip() if value is not None else None


class TeamSummary(BaseModel):
    """团队列表项 / 摘要。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    avatar_url: str | None
    created_at: datetime
    member_count: int = 0
    # 可见性：public 团队中心可见；private 仅邀请链接申请
    visibility: TeamVisibility = TeamVisibility.PRIVATE
    # 当前用户在该团队的角色：creator / admin / member；非成员视图为 None
    my_role: str | None = None


class TeamDetail(TeamSummary):
    """团队详情（成员可见；含创建人与状态）。"""

    creator_id: uuid.UUID
    status: TeamStatus
    disbanded_at: datetime | None


class TeamAdminSummary(TeamSummary):
    """团队管理列表项（admin 视图，docs/contracts/teams.md 管理端）：
    带团队状态与创建人昵称；my_role 恒为 None（管理视图不代表成员身份）。"""

    status: TeamStatus
    creator_nickname: str | None = None
    # 团队空间资源计数（题库非归档 / 题单未下线 / 比赛全部状态）
    problem_count: int = 0
    problem_set_count: int = 0
    contest_count: int = 0


class TeamAdminDetail(TeamDetail):
    """团队管理详情（admin 视图，免团队成员校验）：在成员详情上追加创建人昵称
    与团队空间资源计数（题库 / 题单 / 比赛，全部状态）。"""

    creator_nickname: str | None = None
    problem_count: int = 0
    problem_set_count: int = 0
    contest_count: int = 0


class TeamMemberOut(BaseModel):
    """成员列表项。"""

    user_id: uuid.UUID
    nickname: str
    avatar_url: str | None
    status: TeamMemberStatus
    joined_at: datetime
    is_creator: bool = False
    is_admin: bool = False


class TeamApplicationOut(BaseModel):
    """加入申请列表项。"""

    id: uuid.UUID
    team_id: uuid.UUID
    user_id: uuid.UUID
    nickname: str
    invite_token: str | None
    status: TeamApplicationStatus
    applied_at: datetime
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None


class TeamInviteCreated(BaseModel):
    """邀请链接创建响应（token 存 Redis，链接不可撤销、可多人使用）。"""

    token: str
    expires_at: datetime


class TeamInviteResolved(BaseModel):
    """邀请链接解析响应（public：落地页展示团队与有效期）。"""

    team_id: uuid.UUID
    team_name: str
    expires_at: datetime


class TeamApplicationSubmit(BaseModel):
    """提交加入申请（invite_token 可选：经邀请链接提交时记录来源）。"""

    invite_token: str | None = Field(default=None, max_length=64)


class TeamApplicationReview(BaseModel):
    """审批加入申请（approve=true 通过并授权 team_member；false 拒绝）。"""

    approve: bool


class TeamAdminFlag(BaseModel):
    """分配 / 取消团队管理员（仅创建者）。"""

    is_admin: bool


# ==================== 团队空间（题库 / 题单 / 比赛，docs/contracts/teams.md 团队空间节） ====================


class TeamProblemReferenceCreate(BaseModel):
    """引用本人全站题目进入团队题库（team_creator / team_admin）。

    题目须为全站题目（team_id IS NULL）且为本人创建（admin 同权全站）；
    引用后归属该团队、可见性切换为团队分支（单向，不设移出通道）。
    """

    problem_id: uuid.UUID
    # 团队内可见性：team_visible（全队成员）/ admin_visible（仅创建者与管理员）
    visibility: ProblemVisibility = ProblemVisibility.TEAM_VISIBLE

    @model_validator(mode="after")
    def check_visibility(self) -> TeamProblemReferenceCreate:
        if self.visibility not in (ProblemVisibility.TEAM_VISIBLE, ProblemVisibility.ADMIN_VISIBLE):
            raise ValueError("团队题目可见性仅支持 team_visible / admin_visible")
        return self


class TeamProblemSetCreate(BaseModel):
    """创建团队题单（team_creator / team_admin；team_id 由路径给定）。

    copy_items_from 非空 = 复制本人全站题单的题目条目（快照复制，源题单保留在全站）；
    visibility 与团队题目对齐（team_visible 全队可见，缺省 / admin_visible 仅团队管理）。
    """

    title: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    copy_items_from: uuid.UUID | None = None
    visibility: ProblemSetVisibility = ProblemSetVisibility.TEAM_VISIBLE

    @model_validator(mode="after")
    def check_visibility(self) -> TeamProblemSetCreate:
        if self.visibility not in (ProblemSetVisibility.TEAM_VISIBLE, ProblemSetVisibility.ADMIN_VISIBLE):
            raise ValueError("团队题单可见性仅支持 team_visible / admin_visible")
        return self


class TeamContestCreate(ContestCreate):
    """创建团队比赛（team_creator / team_admin；contest_type='team'、team_id 由路径给定）。

    编排候选在 ContestCreate 规则（已发布公开 / 本人私有）之上放开本团队题目。
    """

    pass

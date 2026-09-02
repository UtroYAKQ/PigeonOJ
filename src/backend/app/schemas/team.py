"""团队模块请求 / 响应模型（docs/contracts/teams.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import TeamApplicationStatus, TeamMemberStatus, TeamStatus
from app.utils.validation import validate_nickname


class TeamCreate(BaseModel):
    """创建团队（admin/tutor；创建人自动成为成员并获 team_creator 授权）。"""

    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    avatar_url: str | None = Field(default=None, max_length=512)

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
    # 当前用户在该团队的角色：creator / admin / member；非成员视图为 None
    my_role: str | None = None


class TeamDetail(TeamSummary):
    """团队详情（成员可见；含创建人与状态）。"""

    creator_id: uuid.UUID
    status: TeamStatus
    disbanded_at: datetime | None


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

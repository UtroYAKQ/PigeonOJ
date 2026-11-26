"""组织模块请求 / 响应模型（docs/contracts/orgs.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import OrgMemberStatus, OrgStatus
from app.utils.validation import validate_nickname


class OrgCreate(BaseModel):
    """创建组织（站点 admin；可同时任命初始组织管理员）。"""

    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    avatar_url: str | None = Field(default=None, max_length=512)
    # 初始组织管理员用户 id 列表（写入 org_members 并授予 org_admin）
    admin_user_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_valid(cls, value: str) -> str:
        # 复用昵称规则：1-64 可见字符、去首尾空白
        validate_nickname(value)
        return value.strip()


class OrgUpdate(BaseModel):
    """编辑组织信息（org_admin；缺省不动；avatar_url 由前端经图片上传获得外链后传入）。"""

    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    avatar_url: str | None = Field(default=None, max_length=512)

    @field_validator("name")
    @classmethod
    def name_valid(cls, value: str | None) -> str | None:
        if value is not None:
            validate_nickname(value)
        return value.strip() if value is not None else None


class OrgSummary(BaseModel):
    """组织列表项 / 摘要。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    avatar_url: str | None
    created_at: datetime
    member_count: int = 0
    team_count: int = 0
    # 当前用户在该组织的角色：admin / member；非成员视图为 None
    my_role: str | None = None


class OrgDetail(OrgSummary):
    """组织详情（成员可见；含状态与创建操作人）。"""

    created_by: uuid.UUID
    status: OrgStatus
    disbanded_at: datetime | None


class OrgAdminSummary(OrgSummary):
    """组织管理列表项（admin 视图）：带组织状态与创建操作人昵称；my_role 恒为 None。"""

    status: OrgStatus
    creator_nickname: str | None = None


class OrgAdminDetail(OrgDetail):
    """组织管理详情（admin 视图，免成员校验）：追加创建操作人昵称。"""

    creator_nickname: str | None = None


class OrgMemberOut(BaseModel):
    """组织成员列表项。"""

    user_id: uuid.UUID
    nickname: str
    avatar_url: str | None
    status: OrgMemberStatus
    joined_at: datetime
    is_admin: bool = False
    # 成员备注：本人 / org_admin 可设置；展示于昵称之后
    note: str | None = None


class OrgMemberAdd(BaseModel):
    """直接添加成员（org_admin 拉人，可批量；已在册跳过）。"""

    user_ids: list[uuid.UUID] = Field(min_length=1)


class OrgMemberNote(BaseModel):
    """设置成员备注（本人可备注自己；org_admin 可备注任意成员；空串 = 清除）。"""

    note: str | None = Field(default=None, max_length=64)


class OrgAdminFlag(BaseModel):
    """授予 / 撤销组织管理员。"""

    is_admin: bool


class OrgTeamAssign(BaseModel):
    """存量团队指派组织（admin 迁移用）。"""

    org_id: uuid.UUID

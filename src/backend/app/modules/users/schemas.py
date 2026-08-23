"""用户模块请求 / 响应 Schema（pydantic v2）。

数据形状与 docs/contracts/users.md 对齐；返回用户对象一律排除 password 字段。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class UserPublic(BaseModel):
    """对外用户对象（无 password；roles 由 user_roles 聚合，见 docs/architecture.md）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    email_verified: bool
    nickname: str
    avatar_url: str | None
    signature: str | None
    theme: str
    status: str
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    roles: list[str] = []


class ProfileUpdate(BaseModel):
    nickname: str | None = None
    signature: str | None = None
    avatar_url: str | None = None
    theme: Literal["light", "dark"] | None = None


class PasswordConfirm(BaseModel):
    password: str


class UserPage(BaseModel):
    items: list[UserPublic]
    total: int
    page: int
    page_size: int

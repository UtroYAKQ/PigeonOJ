"""用户模块请求 / 响应 Schema（pydantic v2，docs/contracts/users.md）。

包含认证（注册 / 登录 / 找回密码等）与用户中心两组契约；
数据形状与 docs/contracts/users.md 对齐；返回用户对象一律排除 password 字段。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


# ---- 认证（原 auth 模块，docs/contracts/users.md /auth* 端点） ----


class EmailCodeRequest(BaseModel):
    email: str
    purpose: Literal["register", "reset_password", "change_email"]


class RegisterRequest(BaseModel):
    email: str
    # 邮箱验证开启（email.verify_enabled）时必填；关闭时可缺省（docs/contracts/users.md）
    code: str = ""
    password: str
    nickname: str = Field(max_length=64)


class LoginRequest(BaseModel):
    email: str
    password: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class ChangeEmailRequest(BaseModel):
    new_email: str
    code: str

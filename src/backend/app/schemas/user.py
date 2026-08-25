"""用户模块请求 / 响应 Schema（pydantic v2，docs/contracts/users.md）。

包含认证（注册 / 登录 / 找回密码等）与用户中心两组契约；
数据形状与 docs/contracts/users.md 对齐；返回用户对象一律排除 password 字段。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import Theme, UserStatus, UserRoleScope


class UserPublic(BaseModel):
    """对外用户对象（无 password；roles 由 user_roles 聚合，见 docs/architecture.md）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    email_verified: bool
    nickname: str
    avatar_url: str | None
    signature: str | None
    theme: Theme
    status: UserStatus
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    roles: list[str] = []


class LoginResult(BaseModel):
    """登录成功响应：会话 token + 用户公开信息。"""

    token: str
    user: UserPublic


class ProfileUpdate(BaseModel):
    nickname: str | None = None
    signature: str | None = None
    avatar_url: str | None = None
    theme: Theme | None = None


class PasswordConfirm(BaseModel):
    password: str


class UserPage(BaseModel):
    items: list[UserPublic]
    total: int
    page: int
    page_size: int


class SessionOut(BaseModel):
    """登录会话输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    device_info: str | None
    ip_address: str | None = None
    user_agent: str | None
    expires_at: str
    revoked_at: str | None
    last_active_at: str | None
    created_at: str
    current: bool

    @field_validator("ip_address", mode="before")
    @classmethod
    def coerce_ip(cls, v):
        return str(v) if v is not None else None


class LoginResponse(BaseModel):
    """登录成功响应。"""

    token: str
    user: UserPublic


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

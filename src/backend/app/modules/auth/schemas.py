"""认证模块请求 / 响应 Schema（docs/contracts/users.md）。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EmailCodeRequest(BaseModel):
    email: str
    purpose: Literal["register", "reset_password", "change_email"]


class RegisterRequest(BaseModel):
    email: str
    code: str
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

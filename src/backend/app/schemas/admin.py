"""管理 / 运维模块请求 Schema（pydantic v2）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import ConfigCategory, LogLevel, LoginAction, ReportAction, ReportStatus, ReportTargetType


class ConfigUpdateItem(BaseModel):
    id: uuid.UUID
    config_value: Any


class ConfigUpdateRequest(BaseModel):
    items: list[ConfigUpdateItem] = Field(min_length=1)


class RoleUpdateRequest(BaseModel):
    """全局角色授权（单一角色模型：一个用户恰好持有一个全局角色）。"""

    role_id: str


class StatusReasonRequest(BaseModel):
    reason: str | None = None


class ReportHandleRequest(BaseModel):
    action: ReportAction


# ---- Response Schemas ----


class ConfigItemOut(BaseModel):
    """管理配置项输出。"""

    id: str
    category: str
    config_key: str
    config_value: Any
    description: str | None
    updated_by: str | None
    updated_at: str


class RequestLogOut(BaseModel):
    """请求日志输出（user_agent 原文 / location / device 为 extra 内 UA 解析结果）。"""

    id: str
    request_id: str
    user_id: str | None
    nickname: str | None = None
    method: str
    path: str
    status_code: int
    ip_address: str | None
    location: str | None = None
    user_agent: str | None = None
    device: dict | None = None
    duration_ms: int | None
    created_at: str

    @field_validator("ip_address", mode="before")
    @classmethod
    def coerce_ip(cls, v):
        return str(v) if v is not None else None


class LoginLogOut(BaseModel):
    """登录日志输出。"""

    id: str
    user_id: str | None
    nickname: str | None = None
    email: str | None
    action: LoginAction
    ip_address: str | None
    location: str | None = None
    user_agent: str | None = None
    success: bool
    reason: str | None
    created_at: str

    @field_validator("ip_address", mode="before")
    @classmethod
    def coerce_ip(cls, v):
        return str(v) if v is not None else None


class ExceptionLogOut(BaseModel):
    """异常日志输出。"""

    id: str
    level: LogLevel
    message: str
    traceback: str | None
    request_id: str | None
    user_id: str | None
    created_at: str


class ReportOut(BaseModel):
    """举报输出。"""

    id: str
    target_type: ReportTargetType
    target_id: str
    target_summary: str | None
    reporter_nickname: str
    reason: str
    status: ReportStatus
    handled_by: str | None
    handled_at: str | None
    created_at: str


class SandboxNodeOut(BaseModel):
    """沙箱节点状态输出。"""

    id: str
    name: str
    status: str
    channel: str
    load: float
    cpu_usage: int
    memory_usage: int
    running_tasks: int
    capacity: int
    version: str
    last_heartbeat_at: str


class SitePublicConfig(BaseModel):
    """公开站点配置（GET /site-config）。"""

    name: str
    logo: str
    icp: str
    default_theme: str
    register_enabled: bool
    email_verify_enabled: bool


class EmailCodePolicy(BaseModel):
    """邮箱验证码安全策略。"""

    expire_seconds: int
    resend_seconds: int
    max_attempts: int


class SMTPConfig(BaseModel):
    """SMTP 发信配置。

    smtp_mode:
      - "ssl": 隐式 TLS（SMTP_SSL，常见端口 465）
      - "starttls": 明文连接后 STARTTLS 升级（常见端口 587）
      - "plain": 明文连接，不加密（仅内网可信场景）
    """

    host: str
    port: int
    username: str
    password: str
    sender: str
    smtp_mode: Literal["ssl", "starttls", "plain"]

"""管理 / 运维模块请求 Schema（pydantic v2）。"""
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConfigUpdateItem(BaseModel):
    id: uuid.UUID
    config_value: Any


class ConfigUpdateRequest(BaseModel):
    items: list[ConfigUpdateItem] = Field(min_length=1)


class RoleUpdateRequest(BaseModel):
    role_ids: list[str] = Field(min_length=1)


class StatusReasonRequest(BaseModel):
    reason: str | None = None


class ReportHandleRequest(BaseModel):
    action: Literal["handled", "ignored"]

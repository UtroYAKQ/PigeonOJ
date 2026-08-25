"""系统配置域枚举。"""
from __future__ import annotations

from enum import StrEnum


class ConfigCategory(StrEnum):
    SITE = "site"
    AUTH_EMAIL = "auth_email"
    TEAM = "team"
    CONTEST = "contest"
    MODEL = "model"
    TOKEN = "token"
    SANDBOX = "sandbox"
    LOG = "log"
    COMMUNITY = "community"

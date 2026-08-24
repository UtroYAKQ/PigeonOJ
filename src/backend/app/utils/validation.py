"""共享参数校验（10xx 错误码，docs/contracts/common.md）。"""
from __future__ import annotations

import re

from app.core.exceptions import PARAM_FORMAT_INVALID, APIError

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def validate_email(email: str) -> None:
    if not _EMAIL_RE.match(email):
        raise APIError(PARAM_FORMAT_INVALID, "邮箱格式错误", 400)


def validate_password(password: str) -> None:
    if not (6 <= len(password) <= 72):
        raise APIError(PARAM_FORMAT_INVALID, "密码长度需为 6~72 位", 400)


def validate_nickname(nickname: str) -> None:
    if not (1 <= len(nickname.strip()) <= 64):
        raise APIError(PARAM_FORMAT_INVALID, "昵称长度需为 1~64 字符", 400)

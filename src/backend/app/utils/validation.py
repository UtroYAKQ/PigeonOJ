"""共享参数校验（10xx 错误码，docs/contracts/common.md）。"""
from __future__ import annotations

import re

from app.core.exceptions import PARAM_FORMAT_INVALID, APIError

# 邮箱按 RFC 5321/5322 的实用子集校验：local 为点分 atom（不允许连续点 / 首尾点），
# domain 为点分 DNS 标签（不允许首尾连字符 / 空标签），TLD 限定 2-63 位字母。
# 不接受 IP 字面量、引号地址、控制字符等非常规写法，避免脏地址进入落库 / 发信链路。
EMAIL_MAX_LENGTH = 254
_LOCAL_MAX_LENGTH = 64
_DOMAIN_MAX_LENGTH = 253

_LOCAL_PART_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$")
_DOMAIN_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_TOP_LEVEL_LABEL_RE = re.compile(r"^[A-Za-z]{2,63}$")


def normalize_email(email: str) -> str:
    """邮箱大小写不敏感：查重 / 落库 / 验证码 Key 统一使用去空白后的小写形式。"""
    return email.strip().lower()


def validate_email(email: str) -> str:
    """校验并返回规范化后的邮箱；非法格式抛 1001（docs/contracts/users.md）。"""
    normalized = normalize_email(email)
    if not normalized or len(normalized) > EMAIL_MAX_LENGTH:
        raise APIError(PARAM_FORMAT_INVALID, "邮箱格式错误", 400)
    local, sep, domain = normalized.rpartition("@")
    if not sep or not local or not domain:
        raise APIError(PARAM_FORMAT_INVALID, "邮箱格式错误", 400)
    if (
        len(local) > _LOCAL_MAX_LENGTH
        or len(domain) > _DOMAIN_MAX_LENGTH
        or not _LOCAL_PART_RE.fullmatch(local)
    ):
        raise APIError(PARAM_FORMAT_INVALID, "邮箱格式错误", 400)
    labels = domain.split(".")
    if len(labels) < 2:
        raise APIError(PARAM_FORMAT_INVALID, "邮箱格式错误", 400)
    if any(not _DOMAIN_LABEL_RE.fullmatch(label) for label in labels) or not _TOP_LEVEL_LABEL_RE.fullmatch(labels[-1]):
        raise APIError(PARAM_FORMAT_INVALID, "邮箱格式错误", 400)
    return normalized


def validate_password(password: str) -> None:
    if not (6 <= len(password) <= 72):
        raise APIError(PARAM_FORMAT_INVALID, "密码长度需为 6~72 位", 400)


def validate_nickname(nickname: str) -> None:
    if not (1 <= len(nickname.strip()) <= 64):
        raise APIError(PARAM_FORMAT_INVALID, "昵称长度需为 1~64 字符", 400)
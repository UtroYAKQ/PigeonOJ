"""utils/validation 单元测试：邮箱格式校验与规范化（docs/contracts/users.md）。"""
from __future__ import annotations

import pytest

from app.core.exceptions import PARAM_FORMAT_INVALID, APIError
from app.utils.validation import EMAIL_MAX_LENGTH, normalize_email, validate_email

pytestmark = pytest.mark.no_db


def test_normalize_email_strips_and_lowercases() -> None:
    assert normalize_email("  User@Example.COM  ") == "user@example.com"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("user@pigeonoj.dev", "user@pigeonoj.dev"),
        ("User@Example.COM", "user@example.com"),
        ("  user@pigeonoj.dev  ", "user@pigeonoj.dev"),
        ("first.last+tag@sub.example.co", "first.last+tag@sub.example.co"),
        ("a_b-c@example.io", "a_b-c@example.io"),
    ],
)
def test_validate_email_accepts_valid_addresses(raw: str, expected: str) -> None:
    assert validate_email(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "plainaddress",
        "a@b",
        "a@b.c",
        "a@b.123",
        "a@@b.com",
        "a@b..com",
        ".a@b.com",
        "a.@b.com",
        "a..b@c.com",
        "a b@c.com",
        "a@-b.com",
        "a@b-.com",
        "a@b.com.",
        "a@_b.com",
        "a@[192.168.1.1]",
        "a\n@b.com",
        "a@b.com\r\nBcc: x@y.com",
        "用户@例子.中国",
    ],
)
def test_validate_email_rejects_invalid_addresses(raw: str) -> None:
    with pytest.raises(APIError) as exc_info:
        validate_email(raw)
    assert exc_info.value.code == PARAM_FORMAT_INVALID


def test_validate_email_length_boundaries() -> None:
    local = "a" * 64
    domain = f"{'b' * 63}.{'c' * 63}.{'d' * 57}.com"
    address = f"{local}@{domain}"
    assert len(address) == EMAIL_MAX_LENGTH
    assert validate_email(address) == address

    with pytest.raises(APIError) as exc_info:
        validate_email(f"{local}@{domain[:-3]}xxxx")
    assert exc_info.value.code == PARAM_FORMAT_INVALID

    with pytest.raises(APIError) as exc_info:
        validate_email(f"{'a' * 65}@example.com")
    assert exc_info.value.code == PARAM_FORMAT_INVALID

    with pytest.raises(APIError) as exc_info:
        validate_email(f"{'a' * 64}@{'b' * 64}.com")
    assert exc_info.value.code == PARAM_FORMAT_INVALID
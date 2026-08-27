"""后端错误消息 i18n：语言协商 + 目录翻译 + 信封消息随 Accept-Language 切换。

约定见 docs/contracts/common.md：code 不变，message 默认中文，
请求 Accept-Language 偏好英文时返回英文（未命中目录回退中文）。
"""
from __future__ import annotations

import pytest

from app.core.i18n import EN_US, ZH_CN, resolve_locale, translate_message


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, ZH_CN),
        ("", ZH_CN),
        ("zh-CN,zh;q=0.9", ZH_CN),
        ("en-US,en;q=0.9", EN_US),
        ("en", EN_US),
        ("fr-FR,fr;q=0.9,en;q=0.8", EN_US),  # 第一个受支持语言按 q 降序生效
        ("fr-FR", ZH_CN),  # 无受支持语言回退中文
        ("zh-CN,en-US;q=0.9", ZH_CN),  # q 高者优先
        ("*", ZH_CN),  # 通配不匹配具体语言
        ("en-US,;q=0.9", EN_US),  # 容忍空标签
    ],
)
def test_resolve_locale(header: str | None, expected: str) -> None:
    assert resolve_locale(header) == expected


def test_translate_message_exact_and_fallback() -> None:
    # 中文语言下原样返回
    assert translate_message("题目不存在", ZH_CN) == "题目不存在"
    # 英文语言：目录精确命中
    assert translate_message("题目不存在", EN_US) == "Problem not found"
    # 参数化前缀规则：动态段（UUID / 名称）原样保留
    assert translate_message("角色不存在：admin", EN_US) == "Role does not exist: admin"
    # 未命中目录回退中文原文
    assert translate_message("某种尚未登记的错误", EN_US) == "某种尚未登记的错误"


@pytest.mark.asyncio
async def test_envelope_message_follows_accept_language(client, admin_headers) -> None:
    """同一校验错误：默认中文，Accept-Language: en-US 时英文；错误码不变。"""
    resp_zh = await client.get("/api/v1/problems?page=0", headers=admin_headers)
    assert resp_zh.status_code == 400
    zh_body = resp_zh.json()
    assert zh_body["code"] == 1001
    assert zh_body["message"] == "page: 不能小于 1"

    resp_en = await client.get(
        "/api/v1/problems?page=0",
        headers={**admin_headers, "Accept-Language": "en-US,en;q=0.9"},
    )
    assert resp_en.status_code == 400
    en_body = resp_en.json()
    assert en_body["code"] == 1001
    assert en_body["message"] == "page: Must be at least 1"


@pytest.mark.asyncio
async def test_api_error_message_translated(client, user_headers) -> None:
    """业务异常（APIError）消息同样随 Accept-Language 翻译。"""
    resp = await client.get(
        "/api/v1/admin/users",
        headers={**user_headers, "Accept-Language": "en-US"},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["code"] == 2003
    assert body["message"] == "Forbidden: administrator role required"

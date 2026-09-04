"""utils/request_meta 单元测试：真实 IP 解析（XFF / X-Real-IP / 直连）与 UA 解析。"""
from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.utils.request_meta import parse_user_agent, resolve_client_ip


def _app_with_ip() -> FastAPI:
    app = FastAPI()

    @app.get("/ip")
    async def ip(request: Request) -> dict:
        return {"ip": resolve_client_ip(request)}

    return app


def _client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ---- resolve_client_ip ----


def test_ip_direct_connection() -> None:
    """无代理头：直连 peer IP 即真实 IP；peer 非法（TestClient hostname）回退 None。"""
    client = _client(_app_with_ip())
    resp = client.get("/ip", headers={"user-agent": "x"})
    assert resp.json()["ip"] in (None, "testclient")


def test_ip_xff_public_first() -> None:
    """XFF 多段：取左起第一个公网地址（客户端在最前）。"""
    client = _client(_app_with_ip())
    resp = client.get(
        "/ip",
        headers={"X-Forwarded-For": "8.8.8.8, 10.0.0.2, 1.1.1.1"},
    )
    assert resp.json()["ip"] == "8.8.8.8"


def test_ip_xff_private_fallback_leftmost_valid() -> None:
    """XFF 全私有段（纯内网部署）：回退最左侧合法地址。"""
    client = _client(_app_with_ip())
    resp = client.get("/ip", headers={"X-Forwarded-For": "10.0.0.5, 192.168.1.3"})
    assert resp.json()["ip"] == "10.0.0.5"


def test_ip_xff_garbage_ignored() -> None:
    """XFF 全非法值：丢弃，回退 X-Real-IP。"""
    client = _client(_app_with_ip())
    resp = client.get(
        "/ip",
        headers={"X-Forwarded-For": "not-an-ip, ;;", "X-Real-IP": "8.8.4.4"},
    )
    assert resp.json()["ip"] == "8.8.4.4"


def test_ip_xff_takes_precedence_over_real_ip() -> None:
    client = _client(_app_with_ip())
    resp = client.get(
        "/ip",
        headers={"X-Forwarded-For": "8.8.8.8", "X-Real-IP": "8.8.4.4"},
    )
    assert resp.json()["ip"] == "8.8.8.8"


def test_ip_xff_spoofed_private_pollution_skipped() -> None:
    """客户端伪造私有段污染 XFF 左侧：可信代理追加的公网段仍被正确选中。"""
    client = _client(_app_with_ip())
    resp = client.get(
        "/ip",
        headers={"X-Forwarded-For": "192.168.1.1, 8.8.8.8"},
    )
    assert resp.json()["ip"] == "8.8.8.8"


# ---- parse_user_agent ----


@pytest.mark.parametrize(
    ("ua", "browser", "os_name", "device"),
    [
        # Windows Chrome
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36",
            "Chrome 126",
            "Windows 10",
            "desktop",
        ),
        # Edge（Edg 必须先于 Chrome 命中）
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
            "Edge 126",
            "Windows 10",
            "desktop",
        ),
        # Firefox
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
            "Firefox 127",
            "Windows 10",
            "desktop",
        ),
        # macOS Safari
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
            "Safari 17",
            "macOS 10",
            "desktop",
        ),
        # Android 微信
        (
            "Mozilla/5.0 (Linux; Android 14; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.47",
            "WeChat 8",
            "Android 14",
            "mobile",
        ),
        # iPhone Safari
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
            "Safari 17",
            "iOS 17",
            "mobile",
        ),
        # 爬虫
        (
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            None,
            None,
            "bot",
        ),
        # 完全未知
        ("weird-thing/1.0", None, None, None),
        # 空
        ("", None, None, None),
        (None, None, None, None),
    ],
)
def test_parse_user_agent(
    ua: str | None, browser: str | None, os_name: str | None, device: str | None
) -> None:
    parsed = parse_user_agent(ua)
    assert parsed["browser"] == browser
    assert parsed["os"] == os_name
    assert parsed["device"] == device

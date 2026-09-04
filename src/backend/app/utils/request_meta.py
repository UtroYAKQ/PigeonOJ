"""请求元信息提取：真实客户端 IP（X-Forwarded-For 优先）与 User-Agent 轻量解析。

IP 信任模型（docs/security.md）：应用部署在 nginx 反代之后，XFF 由可信代理追加；
取 XFF 左起第一个非私有 / 保留段地址为客户端 IP（伪造值只能污染最左侧序列，
真实客户端在可信代理追加段之前），全部为私有段（纯内网部署）时取最左侧合法值；
无 XFF / 全非法时回退直连 peer，IP 合法性最终由 parse_client_ip 兜底。

UA 解析为纯手写轻量实现（不引入第三方库）：识别主流浏览器 / 引擎、
操作系统与设备形态，未识别项返回 None（前端显示「--」）。
"""
from __future__ import annotations

import ipaddress
import re

from fastapi import Request

from app.core.dependency import parse_client_ip


def _is_global(ip: str) -> bool:
    """公网地址（非私有 / 回环 / 链路本地 / 保留段）。"""
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


def resolve_client_ip(request: Request) -> str | None:
    """解析真实客户端 IP：X-Forwarded-For（首个公网段，否则最左合法值）→ X-Real-IP → 直连 peer。"""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        candidates = [part.strip() for part in xff.split(",") if part.strip()]
        for candidate in candidates:
            if _is_global(candidate):
                return candidate
        for candidate in candidates:
            # 纯内网部署（如本地直连容器网络）：取最左侧合法地址
            if parse_client_ip(candidate):
                return candidate
    real_ip = request.headers.get("x-real-ip")
    if real_ip and parse_client_ip(real_ip.strip()):
        return real_ip.strip()
    return parse_client_ip(request.client.host if request.client else None)


# ---- User-Agent 轻量解析（顺序敏感：先专后通，避免 Chrome 被归入 Edg / 通用引擎） ----

_BROWSER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Edge", re.compile(r"Edg(?:e|A|iOS)?/([\d.]+)")),
    ("WeChat", re.compile(r"MicroMessenger/([\d.]+)")),
    ("QQBrowser", re.compile(r"QQBrowser/([\d.]+)")),
    ("Firefox", re.compile(r"(?:Firefox|FxiOS)/([\d.]+)")),
    ("Safari", re.compile(r"Version/([\d.]+).*Safari")),
    ("Chrome", re.compile(r"(?:Chrome|CriOS)/([\d.]+)")),
]

_OS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Windows", re.compile(r"Windows NT ([\d.]+)")),
    ("macOS", re.compile(r"Mac OS X ([\d_.]+)")),
    ("Android", re.compile(r"Android ([\d.]+)")),
    ("iOS", re.compile(r"(?:iPhone|iPad).*OS ([\d_]+)")),
    ("Linux", re.compile(r"Linux")),
]


def parse_user_agent(ua: str | None) -> dict[str, str | None]:
    """UA → {browser, os, device}；无法识别的字段为 None。

    device 取值：desktop / mobile / tablet；text/plain 探测的爬虫归 desktop。
    """
    if not ua:
        return {"browser": None, "os": None, "device": None}
    browser = None
    for name, pattern in _BROWSER_PATTERNS:
        match = pattern.search(ua)
        if match:
            version = match.group(1).replace("_", ".")
            browser = f"{name} {version.split('.')[0]}"
            break
    os_name = None
    for name, pattern in _OS_PATTERNS:
        match = pattern.search(ua)
        if match:
            version = match.group(1).replace("_", ".") if match.lastindex else None
            os_name = f"{name} {version.split('.')[0]}" if version else name
            break
    if "iPad" in ua or "Tablet" in ua:
        device = "tablet"
    elif "Mobi" in ua:
        device = "mobile"
    elif "bot" in ua.lower() or "spider" in ua.lower() or "crawler" in ua.lower():
        device = "bot"
    else:
        device = "desktop" if browser else None
    return {"browser": browser, "os": os_name, "device": device}

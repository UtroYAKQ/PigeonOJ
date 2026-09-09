"""用户中心集成测试（docs/contracts/users.md）：资料 / 注销 / 会话管理 / 注册开关。

数据所有权：所有查询限定当前用户（越权访问他人会话 → 3001）。
"""
from __future__ import annotations

import httpx
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.system_config import SystemConfig
from app.models.user import User, UserSession

from .conftest import api_login, register_user

PASSWORD = "Pass@123"


async def _login_with_ua(
    client: httpx.AsyncClient, email: str, user_agent: str
) -> str:
    """带指定 UA 登录（device_info 由后端 UA 解析生成，同 UA = 同设备）。"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"User-Agent": user_agent},
    )
    assert resp.json()["code"] == 0, resp.text
    return resp.json()["data"]["token"]


async def _set_config(category: str, key: str, value) -> None:
    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(SystemConfig).where(
                    SystemConfig.category == category, SystemConfig.config_key == key
                )
            )
        ).scalar_one()
        row.config_value = value
        await db.commit()


async def test_register_disabled(client: httpx.AsyncClient) -> None:
    """站点关闭注册（site.register_enabled=false）→ 2005，且不消耗已发验证码。"""
    from app.core.redis import redis_set_json

    await redis_set_json("email:code:closed@pigeonoj.dev:register", {"code": "123456", "attempts": 0}, 600)
    await _set_config("site", "site.register_enabled", False)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "closed@pigeonoj.dev", "code": "123456", "password": PASSWORD, "nickname": "被拒"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == 2005
    # 恢复开关后原验证码仍可用（未被消耗）
    await _set_config("site", "site.register_enabled", True)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "closed@pigeonoj.dev", "code": "123456", "password": PASSWORD, "nickname": "通过"},
    )
    assert resp.json()["code"] == 0


async def test_register_without_email_verification(client: httpx.AsyncClient) -> None:
    """关闭邮箱验证（email.verify_enabled=false）→ 无验证码直接注册成功；开启时缺验证码 → 1002。"""
    await _set_config("auth_email", "email.verify_enabled", False)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "noverify@pigeonoj.dev", "password": PASSWORD, "nickname": "免验证"},
    )
    assert resp.json()["code"] == 0
    token = await api_login(client, "noverify@pigeonoj.dev", PASSWORD)
    assert token

    await _set_config("auth_email", "email.verify_enabled", True)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "needcode@pigeonoj.dev", "password": PASSWORD, "nickname": "缺验证码"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 1002


async def test_me_requires_login(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/users/me")
    assert resp.json()["code"] == 2001
    resp = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer bad-token"})
    assert resp.json()["code"] == 2002


async def test_update_profile(client: httpx.AsyncClient) -> None:
    await register_user(client, "profile@pigeonoj.dev")
    token = await api_login(client, "profile@pigeonoj.dev", PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.put(
        "/api/v1/users/me",
        json={"nickname": "新昵称", "signature": "你好世界", "theme": "dark", "avatar_url": "https://example.com/a.png"},
        headers=headers,
    )
    assert resp.json()["code"] == 0
    data = resp.json()["data"]
    assert data["nickname"] == "新昵称"
    assert data["theme"] == "dark"
    assert data["signature"] == "你好世界"

    # 非法主题 → Pydantic Literal 校验失败，统一转 1001 信封（docs/contracts/common.md 响应信封）
    resp = await client.put("/api/v1/users/me", json={"theme": "red"}, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001

    # 头像形态（docs/contracts/users.md）：拒绝裸 oss_id 与越权站内 URL，接受本人站内 URL
    uid = data["id"]
    resp = await client.put("/api/v1/users/me", json={"avatar_url": f"users/{uid}/avatar/abc"}, headers=headers)
    assert resp.status_code == 400 and resp.json()["code"] == 1001
    resp = await client.put(
        "/api/v1/users/me",
        json={"avatar_url": "/api/v1/files/users/00000000-0000-0000-0000-000000000000/avatar/abc"},
        headers=headers,
    )
    assert resp.status_code == 400 and resp.json()["code"] == 1001
    resp = await client.put(
        "/api/v1/users/me", json={"avatar_url": f"/api/v1/files/users/{uid}/avatar/abc"}, headers=headers
    )
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["avatar_url"] == f"/api/v1/files/users/{uid}/avatar/abc"


async def test_soft_delete(client: httpx.AsyncClient) -> None:
    await register_user(client, "delete@pigeonoj.dev")
    token = await api_login(client, "delete@pigeonoj.dev", PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.request("DELETE", "/api/v1/users/me", json={"password": "wrong"}, headers=headers)
    assert resp.json()["code"] == 2004
    resp = await client.request("DELETE", "/api/v1/users/me", json={"password": PASSWORD}, headers=headers)
    assert resp.json()["code"] == 0
    # 注销后邮箱已脱敏释放（u<id>@invalid.local），旧邮箱无法定位账号 → 2004（不暴露账号存在）
    resp = await client.post("/api/v1/auth/login", json={"email": "delete@pigeonoj.dev", "password": PASSWORD})
    assert resp.json()["code"] == 2004


async def test_sessions_list_and_revoke(client: httpx.AsyncClient) -> None:
    await register_user(client, "sess@pigeonoj.dev")
    token1 = await _login_with_ua(client, "sess@pigeonoj.dev", "pytest-a")
    token2 = await _login_with_ua(client, "sess@pigeonoj.dev", "pytest-b")
    headers2 = {"Authorization": f"Bearer {token2}"}

    resp = await client.get("/api/v1/users/me/sessions", headers=headers2)
    assert resp.json()["code"] == 0
    sessions = resp.json()["data"]
    assert len(sessions) == 2
    current = next(s for s in sessions if s["current"])
    older = next(s for s in sessions if not s["current"])
    assert "token" not in older  # 不回传 token

    # 撤销当前会话 → 3002
    resp = await client.delete(f"/api/v1/users/me/sessions/{current['id']}", headers=headers2)
    assert resp.json()["code"] == 3002

    # 撤销旧会话成功，且 token1 失效
    resp = await client.delete(f"/api/v1/users/me/sessions/{older['id']}", headers=headers2)
    assert resp.json()["code"] == 0
    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token1}"})
    assert resp.json()["code"] == 2002


async def test_same_device_login_replaces_session(client: httpx.AsyncClient) -> None:
    """同设备去重（users.md 关键流程 5）：同设备标识重复登录只保留最新会话，
    旧会话立即失效；不同设备（UA 不同）    互不影响。"""
    await register_user(client, "dup@pigeonoj.dev")
    ua = "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0.0.0"
    token1 = await _login_with_ua(client, "dup@pigeonoj.dev", ua)
    headers1 = {"Authorization": f"Bearer {token1}"}

    # 会话带稳定设备标识（无版本号）
    resp = await client.get("/api/v1/users/me/sessions", headers=headers1)
    sessions = resp.json()["data"]
    assert len(sessions) == 1
    assert sessions[0]["device_info"] == "Chrome · Windows"
    assert sessions[0]["online"] is True  # 当前会话恒在线

    # 同设备再登录 → 旧会话被替换，token1 失效
    token2 = await _login_with_ua(client, "dup@pigeonoj.dev", ua)
    resp = await client.get("/api/v1/users/me", headers=headers1)
    assert resp.json()["code"] == 2002

    # 会话列表仅剩最新会话（同设备只有一个活跃会话）
    resp = await client.get(
        "/api/v1/users/me/sessions", headers={"Authorization": f"Bearer {token2}"}
    )
    sessions = resp.json()["data"]
    assert len(sessions) == 1
    assert sessions[0]["current"] is True

    # 另一台设备（不同 UA）登录 → 各自保留，不互踢
    token3 = await _login_with_ua(
        client, "dup@pigeonoj.dev", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Version/17.0 Mobile Safari"
    )
    resp = await client.get(
        "/api/v1/users/me/sessions", headers={"Authorization": f"Bearer {token3}"}
    )
    sessions = resp.json()["data"]
    assert len(sessions) == 2
    assert {s["device_info"] for s in sessions} == {"Chrome · Windows", "Safari · iOS · 移动端"}

    # UA 无法识别（device_info=None）→ 不参与去重，可并存多个
    token4 = await _login_with_ua(client, "dup@pigeonoj.dev", "unknown-agent/0.9")
    token5 = await _login_with_ua(client, "dup@pigeonoj.dev", "unknown-agent/0.9")
    resp = await client.get(
        "/api/v1/users/me/sessions", headers={"Authorization": f"Bearer {token5}"}
    )
    assert len(resp.json()["data"]) == 4


async def test_revoke_other_sessions(client: httpx.AsyncClient) -> None:
    """下线其他设备：**物理删除**除当前会话外的全部会话行（与登出同语义，无撤销记录残留）；
    被下线 token 立即失效，当前会话保持登录。"""
    await register_user(client, "kick@pigeonoj.dev")
    token1 = await _login_with_ua(client, "kick@pigeonoj.dev", "ua-device-1")
    token2 = await _login_with_ua(client, "kick@pigeonoj.dev", "ua-device-2")
    token3 = await _login_with_ua(client, "kick@pigeonoj.dev", "ua-device-3")
    headers3 = {"Authorization": f"Bearer {token3}"}

    resp = await client.delete("/api/v1/users/me/sessions", headers=headers3)
    assert resp.json()["code"] == 0

    # token1 / token2 全部失效；当前会话 token3 保持登录
    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token1}"})
    assert resp.json()["code"] == 2002
    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token2}"})
    assert resp.json()["code"] == 2002
    resp = await client.get("/api/v1/users/me", headers=headers3)
    assert resp.json()["code"] == 0

    # 物理删除：仅剩当前会话行，被下线会话无 revoked_at 残留
    async with SessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == "kick@pigeonoj.dev"))
        ).scalar_one()
        rows = (
            (await db.execute(select(UserSession).where(UserSession.user_id == user.id)))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].revoked_at is None


async def test_session_activity_touched(client: httpx.AsyncClient) -> None:
    """认证链路节流回写 last_active_at（users.md 关键流程 6）：活跃窗口到期后，
    下一次认证请求把最近活跃更新为当前时刻（会话列表在线判定的数据源）。"""
    from datetime import datetime, timedelta

    await register_user(client, "active@pigeonoj.dev")
    token = await api_login(client, "active@pigeonoj.dev", PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    # 回拨最近活跃 30 分钟 → 已超出 5 分钟节流窗口
    from datetime import timezone as _tz

    async with SessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == "active@pigeonoj.dev"))
        ).scalar_one()
        session = (
            await db.execute(select(UserSession).where(UserSession.user_id == user.id))
        ).scalar_one()
        stale = (session.last_active_at or datetime.now(_tz.utc)) - timedelta(minutes=30)
        session.last_active_at = stale
        await db.commit()

    resp = await client.get("/api/v1/users/me", headers=headers)
    assert resp.json()["code"] == 0

    async with SessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == "active@pigeonoj.dev"))
        ).scalar_one()
        session = (
            await db.execute(select(UserSession).where(UserSession.user_id == user.id))
        ).scalar_one()
        assert session.last_active_at > stale
        assert session.token  # 同一会话行被活跃回写更新


async def test_revoke_others_session_forbidden(client: httpx.AsyncClient) -> None:
    """越权：撤销他人会话 → 3001（数据所有权，docs/architecture.md）。"""
    await register_user(client, "a@pigeonoj.dev")
    await register_user(client, "b@pigeonoj.dev")
    token_a = await api_login(client, "a@pigeonoj.dev", PASSWORD)
    token_b = await api_login(client, "b@pigeonoj.dev", PASSWORD)
    sessions_a = (await client.get("/api/v1/users/me/sessions", headers={"Authorization": f"Bearer {token_a}"})).json()["data"]
    resp = await client.delete(
        f"/api/v1/users/me/sessions/{sessions_a[0]['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.json()["code"] == 3001

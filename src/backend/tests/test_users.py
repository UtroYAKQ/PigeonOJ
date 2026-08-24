"""用户中心集成测试（docs/contracts/users.md）：资料 / 注销 / 会话管理 / 注册开关。

数据所有权：所有查询限定当前用户（越权访问他人会话 → 3001）。
"""
from __future__ import annotations

import httpx
from sqlalchemy import select

from app.shared.infra.database import SessionLocal
from app.shared.infra.system_config import SystemConfig

from .conftest import api_login, register_user

PASSWORD = "Pass@123"


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
    from app.shared.infra.redis import redis_set_json

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
    token1 = await api_login(client, "sess@pigeonoj.dev", PASSWORD)
    token2 = await api_login(client, "sess@pigeonoj.dev", PASSWORD)
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

"""认证模块集成测试（docs/contracts/users.md）：验证码 / 注册 / 登录 / 登出 / 改密 / 换绑。

每个会变更账号状态的用例使用独立注册的账号，避免互相污染。
"""
from __future__ import annotations

import httpx

from app.core.redis import redis_set_json

from .conftest import api_login, register_user

PASSWORD = "Pass@123"


async def test_health(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "ok"


async def test_email_code_and_register(client: httpx.AsyncClient) -> None:
    email = "new@pigeonoj.dev"
    resp = await client.post("/api/v1/auth/email-code", json={"email": email, "purpose": "register"})
    assert resp.json()["code"] == 0
    await register_user(client, email)
    # 重复注册 → 3002
    await redis_set_json(f"email:code:{email}:register", {"code": "123456", "attempts": 0}, 600)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "code": "123456", "password": PASSWORD, "nickname": "重复"},
    )
    assert resp.json()["code"] == 3002


async def test_register_wrong_code(client: httpx.AsyncClient) -> None:
    await redis_set_json("email:code:bad@pigeonoj.dev:register", {"code": "123456", "attempts": 0}, 600)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "bad@pigeonoj.dev", "code": "000000", "password": PASSWORD, "nickname": "错误验证码"},
    )
    assert resp.json()["code"] == 2004


async def test_login_success_and_wrong_password(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/login", json={"email": "user@pigeonoj.dev", "password": "User@123"})
    assert resp.json()["code"] == 0
    data = resp.json()["data"]
    assert data["token"]
    assert data["user"]["email"] == "user@pigeonoj.dev"
    assert "password" not in data["user"]

    resp = await client.post("/api/v1/auth/login", json={"email": "user@pigeonoj.dev", "password": "wrong"})
    assert resp.json()["code"] == 2004


async def test_login_failures_trigger_frozen(client: httpx.AsyncClient) -> None:
    """连续 5 次密码错误 → status='frozen'，后续登录被拦截（3002）。"""
    await register_user(client, "frozen-victim@pigeonoj.dev")
    for _ in range(5):
        await client.post("/api/v1/auth/login", json={"email": "frozen-victim@pigeonoj.dev", "password": "bad-pass"})
    resp = await client.post("/api/v1/auth/login", json={"email": "frozen-victim@pigeonoj.dev", "password": PASSWORD})
    assert resp.json()["code"] == 3002


async def test_logout_revokes_session(client: httpx.AsyncClient) -> None:
    await register_user(client, "logout@pigeonoj.dev")
    token = await api_login(client, "logout@pigeonoj.dev", PASSWORD)
    resp = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["code"] == 0
    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["code"] == 2002


async def test_change_password(client: httpx.AsyncClient) -> None:
    await register_user(client, "pwd@pigeonoj.dev")
    token = await api_login(client, "pwd@pigeonoj.dev", PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/v1/auth/change-password", json={"old_password": "wrong-old", "new_password": "NewPass@123"}, headers=headers
    )
    assert resp.json()["code"] == 2004
    resp = await client.post(
        "/api/v1/auth/change-password", json={"old_password": PASSWORD, "new_password": "NewPass@123"}, headers=headers
    )
    assert resp.json()["code"] == 0
    resp = await client.post("/api/v1/auth/login", json={"email": "pwd@pigeonoj.dev", "password": "NewPass@123"})
    assert resp.json()["code"] == 0


async def test_change_email(client: httpx.AsyncClient) -> None:
    await register_user(client, "mail@pigeonoj.dev")
    token = await api_login(client, "mail@pigeonoj.dev", PASSWORD)
    await redis_set_json("email:code:mail-new@pigeonoj.dev:change_email", {"code": "123456", "attempts": 0}, 600)
    resp = await client.post(
        "/api/v1/auth/change-email",
        json={"new_email": "mail-new@pigeonoj.dev", "code": "123456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["code"] == 0
    resp = await client.post("/api/v1/auth/login", json={"email": "mail-new@pigeonoj.dev", "password": PASSWORD})
    assert resp.json()["code"] == 0


async def test_reset_password(client: httpx.AsyncClient) -> None:
    await register_user(client, "reset@pigeonoj.dev")
    await redis_set_json("email:code:reset@pigeonoj.dev:reset_password", {"code": "123456", "attempts": 0}, 600)
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"email": "reset@pigeonoj.dev", "code": "123456", "new_password": "Reset@123"},
    )
    assert resp.json()["code"] == 0
    resp = await client.post("/api/v1/auth/login", json={"email": "reset@pigeonoj.dev", "password": "Reset@123"})
    assert resp.json()["code"] == 0

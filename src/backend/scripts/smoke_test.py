"""端到端冒烟测试（开发用）：走真实 HTTP 链路（httpx ASGI）验证 auth/users/admin。

用法：python -m scripts.smoke_test
"""
from __future__ import annotations

import asyncio

import httpx

from app import app

BASE = "http://test"


async def call(client: httpx.AsyncClient, method: str, path: str, **kwargs):
    """path 为 /api/v1 之后的路径；/health 单独调用（无前缀）。"""
    url = f"/api/v1{path}"
    resp = await client.request(method, f"{BASE}{url}", **kwargs)
    print(f"{method:6} {url:36} -> {resp.status_code} {resp.json().get('code')} {resp.json().get('message', '')[:40]}")
    return resp


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE) as client:
        # 健康检查（无 /api/v1 前缀）
        r = await client.get(f"{BASE}/health")
        print("GET    /health                            ->", r.status_code, r.json().get("code"))
        assert r.json()["code"] == 0

        # 登录（演示账号）
        r = await call(client, "POST", "/auth/login", json={"email": "admin@pigeonoj.dev", "password": "Admin@123"})
        assert r.json()["code"] == 0, r.text
        token = r.json()["data"]["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 当前用户
        r = await call(client, "GET", "/users/me", headers=headers)
        assert r.json()["data"]["roles"] == ["admin"], r.text

        # 管理端点
        await call(client, "GET", "/admin/users?page=1&page_size=5", headers=headers)
        await call(client, "GET", "/admin/users?keyword=admin", headers=headers)
        await call(client, "GET", "/admin/configs", headers=headers)
        await call(client, "GET", "/admin/configs?category=site", headers=headers)
        await call(client, "GET", "/admin/logs/request", headers=headers)
        await call(client, "GET", "/admin/logs/login", headers=headers)
        await call(client, "GET", "/admin/logs/exception", headers=headers)
        await call(client, "GET", "/admin/sandbox/status", headers=headers)
        await call(client, "GET", "/admin/reports", headers=headers)

        # 会话
        r = await call(client, "GET", "/users/me/sessions", headers=headers)
        sessions = r.json()["data"]
        assert any(s["current"] for s in sessions)
        current = next(s for s in sessions if s["current"])
        await call(client, "DELETE", f"/users/me/sessions/{current['id']}", headers=headers)  # 预期 3002

        # 验证码 + 注册新用户
        email = "smoke@pigeonoj.dev"
        await call(client, "POST", "/auth/email-code", json={"email": email, "purpose": "register"})
        r = await call(client, "POST", "/auth/register", json={
            "email": email, "code": "000000", "password": "Smoke@123", "nickname": "冒烟用户",
        })
        assert r.json()["code"] != 0  # 验证码错误
        # 登录演示账号获取真实验证码（开发期验证码打印在日志中，此处直接断言错误路径即可）

        # 登出
        await call(client, "POST", "/auth/logout", headers=headers)

        # 未登录访问管理端点 → 2001
        r = await call(client, "GET", "/admin/users")
        assert r.json()["code"] == 2001

        print("\nSMOKE OK")
        # 清理冒烟注册尝试（验证码错误不会创建用户）
        from app.models.user import User
        from app.core.database import SessionLocal
        from sqlalchemy import delete, select
        async with SessionLocal() as db:
            u = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if u:
                await db.execute(delete(User).where(User.id == u.id))
                await db.commit()
                print("cleaned smoke user")


if __name__ == "__main__":
    asyncio.run(main())

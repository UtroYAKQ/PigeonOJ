"""管理 / 运维模块集成测试（docs/contracts/admin.md）：权限 / 用户管理 / 配置 / 日志 / 举报。"""
from __future__ import annotations

import uuid

import httpx
from sqlalchemy import select

from app.modules.users.models import User
from app.shared.infra.database import SessionLocal

from .conftest import api_login, register_user

PASSWORD = "Pass@123"


async def test_admin_requires_admin_role(client: httpx.AsyncClient, user_headers: dict[str, str]) -> None:
    resp = await client.get("/api/v1/admin/users", headers=user_headers)
    assert resp.json()["code"] == 2003
    resp = await client.get("/api/v1/admin/users")
    assert resp.json()["code"] == 2001


async def test_admin_list_users(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    resp = await client.get("/api/v1/admin/users?page=1&page_size=5", headers=admin_headers)
    assert resp.json()["code"] == 0
    data = resp.json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert data["total"] >= 2
    assert "password" not in data["items"][0]

    resp = await client.get("/api/v1/admin/users?keyword=admin", headers=admin_headers)
    items = resp.json()["data"]["items"]
    assert items and all("admin" in u["email"] or "admin" in u["nickname"] for u in items)


async def test_admin_set_roles(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    await register_user(client, "roles@pigeonoj.dev")
    users = (await client.get("/api/v1/admin/users?keyword=roles@pigeonoj.dev", headers=admin_headers)).json()["data"]["items"]
    uid = users[0]["id"]
    resp = await client.put(f"/api/v1/admin/users/{uid}/roles", json={"role_ids": ["user", "tutor"]}, headers=admin_headers)
    assert resp.json()["code"] == 0
    token = await api_login(client, "roles@pigeonoj.dev", PASSWORD)
    me = (await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})).json()["data"]
    assert set(me["roles"]) == {"user", "tutor"}
    # 非法角色 → 1001
    resp = await client.put(f"/api/v1/admin/users/{uid}/roles", json={"role_ids": ["superman"]}, headers=admin_headers)
    assert resp.json()["code"] == 1001


async def test_admin_ban_freeze_flow(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    await register_user(client, "ban@pigeonoj.dev")
    users = (await client.get("/api/v1/admin/users?keyword=ban@pigeonoj.dev", headers=admin_headers)).json()["data"]["items"]
    uid = users[0]["id"]

    resp = await client.post(f"/api/v1/admin/users/{uid}/freeze", json={"reason": "测试冻结"}, headers=admin_headers)
    assert resp.json()["code"] == 0
    resp = await client.post("/api/v1/auth/login", json={"email": "ban@pigeonoj.dev", "password": PASSWORD})
    assert resp.json()["code"] == 3002
    await client.post(f"/api/v1/admin/users/{uid}/unfreeze", headers=admin_headers)

    resp = await client.post(f"/api/v1/admin/users/{uid}/ban", json={"reason": "违规"}, headers=admin_headers)
    assert resp.json()["code"] == 0
    resp = await client.post("/api/v1/auth/login", json={"email": "ban@pigeonoj.dev", "password": PASSWORD})
    assert resp.json()["code"] == 3002
    resp = await client.post(f"/api/v1/admin/users/{uid}/unban", headers=admin_headers)
    assert resp.json()["code"] == 0
    resp = await client.post("/api/v1/auth/login", json={"email": "ban@pigeonoj.dev", "password": PASSWORD})
    assert resp.json()["code"] == 0


async def test_admin_configs(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    resp = await client.get("/api/v1/admin/configs", headers=admin_headers)
    assert resp.json()["code"] == 0
    configs = resp.json()["data"]
    assert any(c["config_key"] == "site.name" for c in configs)

    resp = await client.get("/api/v1/admin/configs?category=site", headers=admin_headers)
    assert all(c["category"] == "site" for c in resp.json()["data"])

    target = next(c for c in configs if c["config_key"] == "site.name")
    resp = await client.put(
        "/api/v1/admin/configs", json={"items": [{"id": target["id"], "config_value": "PigeonOJ 测试"}]}, headers=admin_headers
    )
    assert resp.json()["code"] == 0
    after = (await client.get("/api/v1/admin/configs?category=site", headers=admin_headers)).json()["data"]
    updated = next(c for c in after if c["config_key"] == "site.name")
    assert updated["config_value"] == "PigeonOJ 测试"
    assert updated["updated_by"] == "管理员"


async def test_admin_logs(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    # 触发一些请求/登录日志
    await client.get("/api/v1/admin/configs", headers=admin_headers)
    await api_login(client, "user@pigeonoj.dev", "User@123")
    for log_type in ("request", "login", "exception"):
        resp = await client.get(f"/api/v1/admin/logs/{log_type}", headers=admin_headers)
        assert resp.json()["code"] == 0
        assert isinstance(resp.json()["data"]["items"], list)
    resp = await client.get("/api/v1/admin/logs/unknown", headers=admin_headers)
    assert resp.json()["code"] == 3001


async def test_admin_sandbox_status(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    resp = await client.get("/api/v1/admin/sandbox/status", headers=admin_headers)
    assert resp.json()["code"] == 0
    assert resp.json()["data"] == []  # 未注册沙箱节点时为空


async def test_admin_reports(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    # 预置一条举报（社区模块未实现，直接落库）
    async with SessionLocal() as db:
        from app.modules.admin.models import Report
        u = (await db.execute(select(User).where(User.email == "user@pigeonoj.dev"))).scalar_one()
        report = Report(reporter_id=u.id, target_type="solution", target_id=uuid.uuid4(), reason="疑似抄袭")
        db.add(report)
        await db.commit()
        report_id = report.id

    resp = await client.get("/api/v1/admin/reports", headers=admin_headers)
    assert resp.json()["code"] == 0
    items = resp.json()["data"]["items"]
    row = next(r for r in items if r["id"] == str(report_id))
    assert row["status"] == "pending"
    assert row["reporter_nickname"] == "普通用户"

    resp = await client.post(f"/api/v1/admin/reports/{report_id}/handle", json={"action": "handled"}, headers=admin_headers)
    assert resp.json()["code"] == 0
    # 重复处理 → 3002
    resp = await client.post(f"/api/v1/admin/reports/{report_id}/handle", json={"action": "ignored"}, headers=admin_headers)
    assert resp.json()["code"] == 3002

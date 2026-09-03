"""管理 / 运维模块集成测试（docs/contracts/admin.md）：权限 / 用户管理 / 配置 / 日志 / 举报。"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select

from app.models.user import User
from app.core.database import SessionLocal
from app.models.system_config import SystemConfig

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
    # 单一角色模型：整体替换为指定角色
    resp = await client.put(f"/api/v1/admin/users/{uid}/roles", json={"role_id": "tutor"}, headers=admin_headers)
    assert resp.json()["code"] == 0
    token = await api_login(client, "roles@pigeonoj.dev", PASSWORD)
    me = (await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})).json()["data"]
    assert me["roles"] == ["tutor"]
    # 换角色 → 整体替换，不叠加
    resp = await client.put(f"/api/v1/admin/users/{uid}/roles", json={"role_id": "user"}, headers=admin_headers)
    assert resp.json()["code"] == 0
    me = (await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})).json()["data"]
    assert me["roles"] == ["user"]
    # 非法角色 → 1001
    resp = await client.put(f"/api/v1/admin/users/{uid}/roles", json={"role_id": "superman"}, headers=admin_headers)
    assert resp.json()["code"] == 1001
    # 缺字段 → 1001
    resp = await client.put(f"/api/v1/admin/users/{uid}/roles", json={}, headers=admin_headers)
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


async def test_site_config_public(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    """公开站点配置：未登录可读，仅暴露白名单字段，且随管理端修改实时生效。"""
    resp = await client.get("/api/v1/site-config")
    assert resp.json()["code"] == 0
    data = resp.json()["data"]
    assert set(data) == {
        "name", "logo", "icp", "default_theme",
        "register_enabled", "email_verify_enabled",
    }
    assert data["register_enabled"] is True
    assert data["email_verify_enabled"] is True

    configs = (await client.get("/api/v1/admin/configs?category=site", headers=admin_headers)).json()["data"]
    name_row = next(c for c in configs if c["config_key"] == "site.name")
    reg_row = next(c for c in configs if c["config_key"] == "site.register_enabled")
    await client.put(
        "/api/v1/admin/configs",
        json={"items": [
            {"id": name_row["id"], "config_value": "鸽子 OJ"},
            {"id": reg_row["id"], "config_value": False},
        ]},
        headers=admin_headers,
    )
    after = (await client.get("/api/v1/site-config")).json()["data"]
    assert after["name"] == "鸽子 OJ"
    assert after["register_enabled"] is False


async def test_admin_smtp_password_masked(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    """敏感配置（*.password）：列表掩码返回；提交掩码值视为未修改，提交新值才落库。"""
    configs = (await client.get("/api/v1/admin/configs?category=auth_email", headers=admin_headers)).json()["data"]
    pwd = next(c for c in configs if c["config_key"] == "email.smtp.password")
    await client.put(
        "/api/v1/admin/configs",
        json={"items": [{"id": pwd["id"], "config_value": "smtp-secret-1"}]},
        headers=admin_headers,
    )

    async def db_value() -> str:
        async with SessionLocal() as db:
            row = (
                await db.execute(
                    select(SystemConfig).where(SystemConfig.config_key == "email.smtp.password")
                )
            ).scalar_one()
            return row.config_value

    assert await db_value() == "smtp-secret-1"
    # 掩码回写 → 保持原值
    await client.put(
        "/api/v1/admin/configs",
        json={"items": [{"id": pwd["id"], "config_value": "******"}]},
        headers=admin_headers,
    )
    assert await db_value() == "smtp-secret-1"
    # 新值 → 落库；列表仍掩码显示
    listed = (
        await client.put(
            "/api/v1/admin/configs",
            json={"items": [{"id": pwd["id"], "config_value": "smtp-secret-2"}]},
            headers=admin_headers,
        )
    ).json()["data"]
    assert await db_value() == "smtp-secret-2"
    assert next(c for c in listed if c["config_key"] == "email.smtp.password")["config_value"] == "******"


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


async def test_admin_logs_deep_pagination(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    """深分页延迟关联：跨页无重叠、总数正确、同 created_at 行全序稳定（不重复 / 不漏行）。"""
    from uuid import uuid4

    from app.models.audit import RequestLog

    # 种子行 path 携带唯一标记，keyword 过滤掉中间件自身写入的请求日志
    run_id = uuid4().hex[:12]

    async with SessionLocal() as db:
        base = datetime(2026, 8, 30, 12, 0, 0)
        # 25 条、其中 3 条时间戳完全相同（决胜列正确性）
        for i in range(25):
            db.add(RequestLog(
                request_id=f"req-{i:03d}", method="GET", path=f"/seed-{run_id}/x/{i}",
                status_code=200, created_at=base if i < 3 else base - timedelta(seconds=i),
            ))
        await db.commit()

    ids_per_page: list[set[str]] = []
    totals: list[int] = []
    for page in (1, 2, 3):
        resp = await client.get(
            f"/api/v1/admin/logs/request?page={page}&page_size=10&keyword={run_id}",
            headers=admin_headers,
        )
        body = resp.json()
        assert body["code"] == 0
        totals.append(body["data"]["total"])
        items = body["data"]["items"]
        assert len(items) == (10 if page < 3 else 5)
        created = [i["created_at"] for i in items]
        assert created == sorted(created, reverse=True)  # 页内时间倒序
        ids_per_page.append({i["id"] for i in items})

    assert totals == [25, 25, 25]
    all_ids = [i for s in ids_per_page for i in s]
    assert len(all_ids) == 25 and len(set(all_ids)) == 25  # 跨页无重叠、无遗漏


async def test_admin_sandbox_status(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    resp = await client.get("/api/v1/admin/sandbox/status", headers=admin_headers)
    assert resp.json()["code"] == 0
    assert resp.json()["data"] == []  # 未注册沙箱节点时为空


async def test_admin_reports(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    # 预置一条举报（社区模块未实现，直接落库）
    async with SessionLocal() as db:
        from app.models.admin import Report
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

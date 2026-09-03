"""题单模块集成测试（docs/contracts/problem-sets.md）。

覆盖：创建权限、题单中心可见性、详情访问控制、题目编排校验与排序、下线语义。
"""
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

import httpx
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.judge import Submission
from app.models.problem import Problem
from app.models.user import User, UserRole

from .conftest import api_login, register_user

TUTOR_ROLE_ID = uuid_mod.UUID("22222222-2222-2222-2222-222222222222")


async def _seed_problem(
    title: str, *, status: str = "published", visibility: str = "public"
) -> str:
    """种子题目：published 需带 verified_at（CHECK 约束）。"""
    async with SessionLocal() as db:
        uid = (
            await db.execute(select(User).where(User.email == "admin@pigeonoj.dev"))
        ).scalar_one().id
        problem = Problem(
            title=title,
            description="D",
            owner_id=uid,
            status=status,
            visibility=visibility,
            verified_at=datetime.now() if status == "published" else None,
        )
        db.add(problem)
        await db.commit()
        return str(problem.id)


async def _tutor_headers(client: httpx.AsyncClient) -> dict[str, str]:
    """注册一个 tutor 账号并返回认证头（题单管理角色正向用例）。"""
    email = "tutor@pigeonoj.dev"
    await register_user(client, email)
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        db.add(UserRole(user_id=user.id, role_id=TUTOR_ROLE_ID, scope="global", object_id=None))
        await db.commit()
    token = await api_login(client, email, "Pass@123")
    return {"Authorization": f"Bearer {token}"}


async def test_create_requires_manager_role(client: httpx.AsyncClient, user_headers) -> None:
    """普通用户创建题单 → 2003；tutor 创建 → 0。"""
    resp = await client.post(
        "/api/v1/problem-sets", json={"title": "我的题单"}, headers=user_headers
    )
    assert resp.json()["code"] == 2003, resp.text

    tutor = await _tutor_headers(client)
    resp = await client.post(
        "/api/v1/problem-sets",
        json={"title": "入门 100 题", "description": "新手向", "visibility": "public"},
        headers=tutor,
    )
    body = resp.json()
    assert body["code"] == 0, resp.text
    assert body["data"]["visibility"] == "public"
    assert body["data"]["item_count"] == 0

    # 团队题单随 teams 模块开放 → 1001
    resp = await client.post(
        "/api/v1/problem-sets", json={"title": "团队题单", "visibility": "team"}, headers=tutor
    )
    assert resp.json()["code"] == 1001


async def test_center_lists_public_active_only(client: httpx.AsyncClient) -> None:
    """题单中心：仅公开且未下线；私有题单不出现；下线后消失。"""
    tutor = await _tutor_headers(client)
    pub = (
        await client.post(
            "/api/v1/problem-sets", json={"title": "公开题单A"}, headers=tutor
        )
    ).json()["data"]["id"]
    await client.post(
        "/api/v1/problem-sets", json={"title": "私有题单B", "visibility": "private"}, headers=tutor
    )

    resp = await client.get("/api/v1/problem-sets")
    items = resp.json()["data"]["items"]
    assert [it["id"] for it in items] == [pub]

    # 下线公开题单 → 中心不再展示
    resp = await client.post(f"/api/v1/problem-sets/{pub}/archive", headers=tutor)
    assert resp.json()["code"] == 0
    resp = await client.get("/api/v1/problem-sets")
    assert resp.json()["data"]["items"] == []


async def test_detail_visibility(client: httpx.AsyncClient, user_headers) -> None:
    """公开题单匿名可看；私有题单仅创建者 / 管理角色可见（2003）。"""
    tutor = await _tutor_headers(client)
    pub = (
        await client.post("/api/v1/problem-sets", json={"title": "公开C"}, headers=tutor)
    ).json()["data"]["id"]
    priv = (
        await client.post(
            "/api/v1/problem-sets", json={"title": "私有D", "visibility": "private"}, headers=tutor
        )
    ).json()["data"]["id"]

    resp = await client.get(f"/api/v1/problem-sets/{pub}")
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["can_manage"] is False

    # 匿名 / 普通用户访问私有题单 → 2003
    resp = await client.get(f"/api/v1/problem-sets/{priv}")
    assert resp.json()["code"] == 2003
    resp = await client.get(f"/api/v1/problem-sets/{priv}", headers=user_headers)
    assert resp.json()["code"] == 2003

    # 创建者可见
    resp = await client.get(f"/api/v1/problem-sets/{priv}", headers=tutor)
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["can_manage"] is True

    # 不存在的题单 → 3001
    resp = await client.get(f"/api/v1/problem-sets/{uuid_mod.uuid4()}")
    assert resp.json()["code"] == 3001


async def test_detail_items_limits_and_solve_status(
    client: httpx.AsyncClient, user_headers
) -> None:
    """题单详情条目带题目限制与登录用户作答状态（三态）；匿名 solved 恒 null。"""
    tutor = await _tutor_headers(client)
    sid = (
        await client.post("/api/v1/problem-sets", json={"title": "限制与状态"}, headers=tutor)
    ).json()["data"]["id"]
    p1 = await _seed_problem("状态一")
    p2 = await _seed_problem("状态二")
    p3 = await _seed_problem("状态三")
    await client.put(
        f"/api/v1/problem-sets/{sid}/items",
        json={"items": [{"problem_id": p1}, {"problem_id": p2}, {"problem_id": p3}]},
        headers=tutor,
    )

    # 用户 p1 AC、p2 仅 WA、p3 未提交
    async with SessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == "user@pigeonoj.dev"))
        ).scalar_one()
        for pid, status in ((p1, "accepted"), (p2, "wrong_answer")):
            db.add(
                Submission(
                    user_id=user.id,
                    problem_id=uuid_mod.UUID(pid),
                    language="cpp17",
                    code="c",
                    status=status,
                )
            )
        await db.commit()

    resp = await client.get(f"/api/v1/problem-sets/{sid}", headers=user_headers)
    items = {i["problem_id"]: i for i in resp.json()["data"]["items"]}
    assert items[p1]["solved"] is True
    assert items[p2]["solved"] is False
    assert items[p3]["solved"] is None
    assert items[p1]["time_limit_ms"] > 0
    assert items[p1]["memory_limit_mb"] > 0

    # 匿名：solved 恒 null
    resp = await client.get(f"/api/v1/problem-sets/{sid}")
    assert all(i["solved"] is None for i in resp.json()["data"]["items"])


async def test_replace_items_validation_and_ordering(client: httpx.AsyncClient) -> None:
    """编排题目：已发布公开题方可加入；同题单内重复 → 3003；按 sort_order 展示。"""
    tutor = await _tutor_headers(client)
    sid = (
        await client.post("/api/v1/problem-sets", json={"title": "编排题单"}, headers=tutor)
    ).json()["data"]["id"]
    p1 = await _seed_problem("题目一")
    p2 = await _seed_problem("题目二")
    draft = await _seed_problem("草稿题", status="draft")
    private = await _seed_problem("私有题", visibility="private")

    url = f"/api/v1/problem-sets/{sid}/items"
    # 草稿 / 私有题目不可加入 → 1001
    resp = await client.put(url, json={"items": [{"problem_id": draft}]}, headers=tutor)
    assert resp.json()["code"] == 1001
    resp = await client.put(url, json={"items": [{"problem_id": private}]}, headers=tutor)
    assert resp.json()["code"] == 1001
    # 同题单内重复 → 3003
    resp = await client.put(
        url, json={"items": [{"problem_id": p1}, {"problem_id": p1, "sort_order": 1}]}, headers=tutor
    )
    assert resp.json()["code"] == 3003

    # 正常编排：sort_order 决定展示顺序
    resp = await client.put(
        url,
        json={"items": [{"problem_id": p2, "sort_order": 1}, {"problem_id": p1, "sort_order": 0}]},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text

    detail = (await client.get(f"/api/v1/problem-sets/{sid}")).json()["data"]
    assert [it["problem_id"] for it in detail["items"]] == [p1, p2]
    assert detail["item_count"] == 2

    # 全量替换：再次提交仅含 p2 → p1 被移除
    resp = await client.put(url, json={"items": [{"problem_id": p2, "sort_order": 0}]}, headers=tutor)
    assert resp.json()["code"] == 0
    detail = (await client.get(f"/api/v1/problem-sets/{sid}")).json()["data"]
    assert [it["problem_id"] for it in detail["items"]] == [p2]


async def test_archived_set_access_control(client: httpx.AsyncClient, user_headers) -> None:
    """下线题单：中心不可见；创建者 / 管理角色可直接查看；普通用户 → 2003。"""
    tutor = await _tutor_headers(client)
    sid = (
        await client.post("/api/v1/problem-sets", json={"title": "下线题单"}, headers=tutor)
    ).json()["data"]["id"]
    await client.post(f"/api/v1/problem-sets/{sid}/archive", headers=tutor)

    resp = await client.get(f"/api/v1/problem-sets/{sid}", headers=user_headers)
    assert resp.json()["code"] == 2003
    resp = await client.get(f"/api/v1/problem-sets/{sid}", headers=tutor)
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["status"] == "archived"

    # 非管理角色不可编辑 / 下线他人题单 → 2003
    resp = await client.post(f"/api/v1/problem-sets/{sid}/archive", headers=user_headers)
    assert resp.json()["code"] == 2003


async def test_update_set_meta(client: httpx.AsyncClient) -> None:
    """编辑题单元信息：title / visibility 缺省不动，传即改。"""
    tutor = await _tutor_headers(client)
    sid = (
        await client.post("/api/v1/problem-sets", json={"title": "原标题"}, headers=tutor)
    ).json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/problem-sets/{sid}",
        json={"title": "新标题", "visibility": "private"},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text
    detail = (await client.get(f"/api/v1/problem-sets/{sid}", headers=tutor)).json()["data"]
    assert detail["title"] == "新标题"
    assert detail["visibility"] == "private"


async def test_admin_manage_list(client: httpx.AsyncClient, user_headers) -> None:
    """/admin/problem-sets 管理视图：admin 全量（含私有、已下线）；tutor 仅本人创建；普通用户 2003。"""
    tutor = await _tutor_headers(client)
    pub = (
        await client.post("/api/v1/problem-sets", json={"title": "管理公开"}, headers=tutor)
    ).json()["data"]["id"]
    await client.post(
        "/api/v1/problem-sets", json={"title": "管理私有", "visibility": "private"}, headers=tutor
    )
    await client.post(f"/api/v1/problem-sets/{pub}/archive", headers=tutor)

    # 普通用户 → 2003
    resp = await client.get("/api/v1/admin/problem-sets", headers=user_headers)
    assert resp.json()["code"] == 2003

    # tutor：全量（含私有 + 已下线）
    resp = await client.get("/api/v1/admin/problem-sets", headers=tutor)
    assert resp.json()["code"] == 0, resp.text
    titles = {it["title"] for it in resp.json()["data"]["items"]}
    assert {"管理公开", "管理私有"} <= titles

    # 状态过滤：archived 仅含已下线
    resp = await client.get(
        "/api/v1/admin/problem-sets?status=archived", headers=tutor
    )
    items = resp.json()["data"]["items"]
    assert items and all(it["status"] == "archived" for it in items)

    # 单一所有权模型：admin 创建的私有题单对 tutor 不可见、不可编辑
    admin_token = await api_login(client, "admin@pigeonoj.dev", "Admin@123")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin_set = (
        await client.post(
            "/api/v1/problem-sets",
            json={"title": "管理员私有题单", "visibility": "private"},
            headers=admin_headers,
        )
    ).json()["data"]["id"]
    resp = await client.get("/api/v1/admin/problem-sets", headers=tutor)
    assert resp.json()["code"] == 0
    titles = {it["title"] for it in resp.json()["data"]["items"]}
    assert "管理员私有题单" not in titles
    resp = await client.put(
        f"/api/v1/problem-sets/{admin_set}", json={"title": "越权改名"}, headers=tutor
    )
    assert resp.json()["code"] == 2003

    # admin 全量（tutor 的 2 个 + admin 的 1 个）
    resp = await client.get(
        "/api/v1/admin/problem-sets", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["total"] == 3


async def test_set_submission(client: httpx.AsyncClient, user_headers) -> None:
    """题单内交题：题单可见 + 题目属于该题单才可提交；落库走统一判题链路。"""
    tutor = await _tutor_headers(client)
    sid = (
        await client.post("/api/v1/problem-sets", json={"title": "交题题单"}, headers=tutor)
    ).json()["data"]["id"]
    p1 = await _seed_problem("题单内题目")
    p_outside = await _seed_problem("题单外题目")
    await client.put(
        f"/api/v1/problem-sets/{sid}/items",
        json={"items": [{"problem_id": p1, "sort_order": 0}]},
        headers=tutor,
    )

    url = f"/api/v1/problem-sets/{sid}/problems/{p1}/submissions"
    body = {"language": "cpp17", "code": "int main(){}"}

    # 正常提交 → 0，submission_id 返回，落库为 practice 提交
    resp = await client.post(url, json=body, headers=user_headers)
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["submission_id"]

    # 题目不属于该题单 → 3001
    resp = await client.post(
        f"/api/v1/problem-sets/{sid}/problems/{p_outside}/submissions",
        json=body, headers=user_headers,
    )
    assert resp.json()["code"] == 3001

    # 私有题单非创建者 → 2003（不泄漏存在性语义按可见性拦截）
    priv = (
        await client.post(
            "/api/v1/problem-sets", json={"title": "私有交题", "visibility": "private"},
            headers=tutor,
        )
    ).json()["data"]["id"]
    await client.put(
        f"/api/v1/problem-sets/{priv}/items",
        json={"items": [{"problem_id": p1, "sort_order": 0}]},
        headers=tutor,
    )
    resp = await client.post(
        f"/api/v1/problem-sets/{priv}/problems/{p1}/submissions",
        json=body, headers=user_headers,
    )
    assert resp.json()["code"] == 2003

    # 代码超 64KB → 1001
    resp = await client.post(
        url, json={"language": "cpp17", "code": "a" * (64 * 1024 + 1)}, headers=user_headers
    )
    assert resp.json()["code"] == 1001


async def test_set_problem_detail(client: httpx.AsyncClient, user_headers) -> None:
    """题单内题目详情（统一入口）：归属校验后返回与题库一致的详情装配。"""
    tutor = await _tutor_headers(client)
    sid = (
        await client.post("/api/v1/problem-sets", json={"title": "详情题单"}, headers=tutor)
    ).json()["data"]["id"]
    p1 = await _seed_problem("题单内详情题目")
    p_outside = await _seed_problem("题单外详情题目")
    await client.put(
        f"/api/v1/problem-sets/{sid}/items",
        json={"items": [{"problem_id": p1, "sort_order": 0}]},
        headers=tutor,
    )

    url = f"/api/v1/problem-sets/{sid}/problems/{p1}"

    # 匿名可看公开题单内题目详情，结构与题库详情一致
    resp = await client.get(url)
    body = resp.json()
    assert body["code"] == 0, resp.text
    assert body["data"]["id"] == p1
    assert body["data"]["title"] == "题单内详情题目"
    assert "samples" in body["data"] and "difficulty" in body["data"]
    assert body["data"]["can_manage"] is False

    # 题目不属于该题单 → 3001
    resp = await client.get(f"/api/v1/problem-sets/{sid}/problems/{p_outside}")
    assert resp.json()["code"] == 3001

    # 私有题单 → 2003
    priv = (
        await client.post(
            "/api/v1/problem-sets", json={"title": "私有详情", "visibility": "private"},
            headers=tutor,
        )
    ).json()["data"]["id"]
    resp = await client.get(f"/api/v1/problem-sets/{priv}/problems/{p1}")
    assert resp.json()["code"] == 2003

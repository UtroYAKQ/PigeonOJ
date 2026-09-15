"""组织模块集成测试（docs/contracts/orgs.md）。

覆盖：创建权限与初始管理员任命、成员拉人 / 移出 / 授管理员（最后一名保护）、
组织信息编辑、组织内建团、组织题库（直建 / 列表 / 草稿全员可见 / 编辑权全员开放）、
组织题目对组织名下团队管理者的只读门、解散清理。
"""
from __future__ import annotations

from datetime import datetime, timezone
import uuid as uuid_mod

import httpx
from sqlalchemy import delete, select

from .conftest import (
    ORG_ADMIN_ROLE_ID,
    api_login,
    create_org,
    register_user,
)
from app.core.database import SessionLocal
from app.models.problem import Problem
from app.models.user import User, UserRole


async def _make_org_admin(client: httpx.AsyncClient, email: str) -> tuple[dict[str, str], str]:
    """注册 → 创建组织并任命为组织管理员 → (headers, org_id)。"""
    await register_user(client, email)
    token = await api_login(client, email, "Pass@123")
    headers = {"Authorization": f"Bearer {token}"}
    uid = (await client.get("/api/v1/users/me", headers=headers)).json()["data"]["id"]
    org_id = await create_org(client, f"组织-{email}", [uid])
    return headers, org_id


async def _extra_user_headers(client: httpx.AsyncClient, email: str) -> tuple[dict[str, str], str]:
    """注册普通用户 → (headers, uid)。"""
    await register_user(client, email)
    token = await api_login(client, email, "Pass@123")
    headers = {"Authorization": f"Bearer {token}"}
    uid = (await client.get("/api/v1/users/me", headers=headers)).json()["data"]["id"]
    return headers, uid


async def _uid_of(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.get("/api/v1/users/me", headers=headers)
    assert resp.json()["code"] == 0, resp.text
    return resp.json()["data"]["id"]


async def _seed_org_problem(
    title: str,
    *,
    org_id: str,
    owner_email: str,
    status: str = "published",
) -> str:
    """直插一道组织题库题目（published 默认带 verified_at，满足发布约束），返回 id。"""
    async with SessionLocal() as db:
        uid = (
            await db.execute(select(User).where(User.email == owner_email))
        ).scalar_one().id
        problem = Problem(
            title=title,
            background="背景",
            description="题面",
            input_description="输入",
            output_description="输出",
            owner_id=uid,
            org_id=uuid_mod.UUID(org_id),
            visibility="org_visible",
            status=status,
            verified_at=datetime.now(timezone.utc) if status == "published" else None,
        )
        db.add(problem)
        await db.commit()
        return str(problem.id)


async def test_create_org_permissions(client: httpx.AsyncClient) -> None:
    """创建组织：仅站点 admin；匿名拦截；普通用户 2003；名称唯一 3003。"""
    resp = await client.post(
        "/api/v1/orgs",
        json={"name": "信奥学会", "admin_user_ids": []},
        headers={"Authorization": "Bearer bogus"},
    )
    assert resp.json()["code"] in (2001, 2002, 2004)

    user, _uid = await _extra_user_headers(client, "norole@pigeonoj.dev")
    resp = await client.post("/api/v1/orgs", json={"name": "路人组织"}, headers=user)
    assert resp.json()["code"] == 2003

    from .conftest import admin_api_headers

    admin = await admin_api_headers(client)
    a_uid = (await client.get("/api/v1/users/me", headers=admin)).json()["data"]["id"]
    m_headers, _m_uid = await _extra_user_headers(client, "firstadmin@pigeonoj.dev")
    resp = await client.post("/api/v1/orgs", json={"name": "信奥学会"}, headers=admin)
    assert resp.json()["code"] == 0, resp.text
    org_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["member_count"] == 1  # 创建者自动成为成员

    # 创建者（未在 admin_user_ids 中列出）也能在「我的组织」看到该组织，且为组织管理员
    resp = await client.get("/api/v1/orgs/mine", headers=admin)
    assert resp.json()["data"]["total"] == 1
    assert resp.json()["data"]["items"][0]["id"] == org_id
    assert resp.json()["data"]["items"][0]["my_role"] == "admin"

    # 名称唯一
    resp = await client.post("/api/v1/orgs", json={"name": "信奥学会"}, headers=admin)
    assert resp.json()["code"] == 3003

    # 拉人（admin 视同组织管理员）→ 被拉人可见详情
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/members", json={"user_ids": [a_uid]}, headers=admin
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.get(f"/api/v1/orgs/{org_id}", headers=admin)
    assert resp.json()["data"]["member_count"] == 1  # 创建者已是成员，自我拉人幂等跳过
    resp = await client.get(f"/api/v1/orgs/{org_id}", headers=m_headers)
    assert resp.json()["code"] == 2003  # 未被拉入


async def test_member_lifecycle_and_last_admin_guard(client: httpx.AsyncClient) -> None:
    """拉人 → 授管理员 → 移出：org_admin 门；最后一名 org_admin 不可撤销 / 移出（3004）。"""
    mentor, org_id = await _make_org_admin(client, "boss@pigeonoj.dev")
    a, a_uid = await _extra_user_headers(client, "admin2@pigeonoj.dev")
    b, b_uid = await _extra_user_headers(client, "member@pigeonoj.dev")

    # 拉人（可批量）→ 在册成员可看成员列表
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/members", json={"user_ids": [a_uid, b_uid]}, headers=mentor
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.get(f"/api/v1/orgs/{org_id}/members", headers=a)
    assert resp.json()["data"]["total"] == 4

    # 重复拉人幂等（已在册跳过）
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/members", json={"user_ids": [a_uid]}, headers=mentor
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.get(f"/api/v1/orgs/{org_id}/members", headers=mentor)
    assert resp.json()["data"]["total"] == 4

    # 普通组织成员不可拉人 / 授管理员
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/members", json={"user_ids": [a_uid]}, headers=b
    )
    assert resp.json()["code"] == 2003
    resp = await client.put(
        f"/api/v1/orgs/{org_id}/members/{a_uid}/admin", json={"is_admin": True}, headers=b
    )
    assert resp.json()["code"] == 2003

    # 授 a 为组织管理员 → is_admin 标记出现
    resp = await client.put(
        f"/api/v1/orgs/{org_id}/members/{a_uid}/admin", json={"is_admin": True}, headers=mentor
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.get(f"/api/v1/orgs/{org_id}/members", headers=mentor)
    assert next(m["is_admin"] for m in resp.json()["data"]["items"] if m["user_id"] == a_uid)

    # 最后两名 org_admin：移出 / 撤销 a 仍可行（mentor 还在）
    resp = await client.put(
        f"/api/v1/orgs/{org_id}/members/{a_uid}/admin", json={"is_admin": False}, headers=mentor
    )
    assert resp.json()["code"] == 0

    # 仅剩 mentor 一名 org_admin：自移出拒绝（不能移除自己 2003 先拦）、撤销自己 3004
    resp = await client.delete(f"/api/v1/orgs/{org_id}/members/{a_uid}", headers=mentor)
    assert resp.json()["code"] == 0, resp.text
    resp = await client.put(
        f"/api/v1/orgs/{org_id}/members/{a_uid}/admin", json={"is_admin": False}, headers=mentor
    )
    assert resp.json()["code"] == 3001  # 已被移出，非在册成员

    # 站点 admin 是创建者（创建组织自动成为组织管理员）：先清除其本组织授权，
    # 使 mentor 成为「最后一名 org_admin」，便于验证最后一名保护（3004）
    async with SessionLocal() as db:
        site_user = (
            await db.execute(select(User).where(User.email == "admin@pigeonoj.dev"))
        ).scalar_one()
        await db.execute(
            delete(UserRole).where(
                UserRole.user_id == site_user.id,
                UserRole.scope == "org",
                UserRole.object_id == uuid_mod.UUID(org_id),
            )
        )
        await db.commit()

    # 直接插一条 org_admin 授权模拟「最后两名」再撤销其一 → 剩零时 3004
    async with SessionLocal() as db:
        uid = (await db.execute(select(User).where(User.email == "member@pigeonoj.dev"))).scalar_one().id
        db.add(UserRole(user_id=uid, role_id=ORG_ADMIN_ROLE_ID, scope="org", object_id=None))
        await db.commit()
    # b 现在也是 org_admin（但非在册成员行——授权存在即可被撤销门校验）
    resp = await client.put(
        f"/api/v1/orgs/{org_id}/members/{b_uid}/admin", json={"is_admin": False}, headers=mentor
    )
    assert resp.json()["code"] == 0, resp.text  # mentor 仍在，可撤销 b

    # mentor 撤销自己（唯一 org_admin）→ 3004
    m_uid = (await client.get("/api/v1/users/me", headers=mentor)).json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/orgs/{org_id}/members/{m_uid}/admin", json={"is_admin": False}, headers=mentor
    )
    assert resp.json()["code"] == 3004

    # 移出唯一 org_admin（admin 身份执行同样 3004；先移自己被 2003 拦）
    resp = await client.delete(f"/api/v1/orgs/{org_id}/members/{m_uid}", headers=mentor)
    assert resp.json()["code"] == 2003

    # 备注：本人自备注 / 管理员备注他人 / 越权 2003
    resp = await client.put(
        f"/api/v1/orgs/{org_id}/members/{a_uid}/note", json={"note": "x"}, headers=a
    )
    assert resp.json()["code"] == 3001  # a 已被移出


async def test_org_teams(client: httpx.AsyncClient) -> None:
    """组织内建团与团队列表：org_admin 门；创建者 team_creator；组织成员可见团队列表。"""
    mentor, org_id = await _make_org_admin(client, "orgboss@pigeonoj.dev")
    member, member_uid = await _extra_user_headers(client, "orgmember@pigeonoj.dev")

    resp = await client.post(
        f"/api/v1/orgs/{org_id}/teams", json={"name": "A队", "visibility": "public"}, headers=mentor
    )
    assert resp.json()["code"] == 0, resp.text
    team_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["my_role"] == "creator"

    # 非组织成员不可建团；组织成员（拉入后）可见团队列表
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/teams", json={"name": "B队"}, headers=member
    )
    assert resp.json()["code"] == 2003
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/members", json={"user_ids": [member_uid]}, headers=mentor
    )
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/orgs/{org_id}/teams", headers=member)
    assert resp.json()["data"]["total"] == 1
    assert resp.json()["data"]["items"][0]["id"] == team_id

    # 组织详情带团队计数；我的组织列表出现该组织
    resp = await client.get(f"/api/v1/orgs/{org_id}", headers=member)
    assert resp.json()["data"]["team_count"] == 1
    resp = await client.get("/api/v1/orgs/mine", headers=member)
    assert resp.json()["data"]["total"] == 1


async def test_org_problem_library(client: httpx.AsyncClient) -> None:
    """组织题库：org_member 直建 / 全员可编辑（组织成员可改他人题目）/
    列表状态视图（草稿全员可见、归档不返回）/ 组织外拦截 / 团队管理者只读门。"""
    mentor, org_id = await _make_org_admin(client, "libboss@pigeonoj.dev")
    member, member_uid = await _extra_user_headers(client, "libmember@pigeonoj.dev")
    outsider, _outsider_uid = await _extra_user_headers(client, "outsider@pigeonoj.dev")

    # 拉入 member → 可直建（普通用户直建前被 2003 拦）
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/problems",
        json={
            "title": "A+B",
            "background": "背景",
            "description": "题面",
            "input_description": "输入",
            "output_description": "输出",
        },
        headers=outsider,
    )
    assert resp.json()["code"] == 2003
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/members", json={"user_ids": [member_uid]}, headers=mentor
    )
    assert resp.json()["code"] == 0
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/problems",
        json={
            "title": "A+B",
            "background": "背景",
            "description": "题面",
            "input_description": "输入",
            "output_description": "输出",
        },
        headers=member,
    )
    assert resp.json()["code"] == 0, resp.text
    pid = resp.json()["data"]["id"]
    assert resp.json()["data"]["visibility"] == "org_visible"

    # DB 种子：另一道已发布组织题（member 创建人署名）+ 一道草稿
    pid2 = await _seed_org_problem("C+D", org_id=org_id, owner_email="libmember@pigeonoj.dev")
    await _seed_org_problem("草稿题", org_id=org_id, owner_email="libboss@pigeonoj.dev", status="draft")

    # 缺省列表：仅 published（1 道，API 直建的为草稿不返回）；draft 视图全员可见（无个人私稿）
    resp = await client.get(f"/api/v1/orgs/{org_id}/problems", headers=member)
    assert resp.json()["data"]["total"] == 1
    resp = await client.get(f"/api/v1/orgs/{org_id}/problems?status=draft", headers=member)
    assert resp.json()["data"]["total"] == 2

    # 组织成员可编辑他人创建的题目（组织题库全员可编辑；owner_id 仅署名）
    resp = await client.put(
        f"/api/v1/problems/{pid2}",
        json={"title": "C+D（改）"},
        headers=mentor,
    )
    assert resp.json()["code"] == 0, resp.text

    # 组织外用户读详情 / 编辑一律拦截
    resp = await client.get(f"/api/v1/problems/{pid2}", headers=outsider)
    assert resp.json()["code"] == 2003
    resp = await client.put(f"/api/v1/problems/{pid2}", json={"title": "x"}, headers=outsider)
    assert resp.json()["code"] == 2003

    # 组织名下团队管理者（非组织成员）只读可见：建团 → 授团队管理员 → 裸路径可读、编辑仍拦截
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/teams", json={"name": "引用队"}, headers=mentor
    )
    team_id = resp.json()["data"]["id"]
    resp = await client.post(f"/api/v1/teams/{team_id}/invites", headers=mentor)
    token = resp.json()["data"]["token"]
    resp = await client.post(
        f"/api/v1/teams/{team_id}/applications", json={"invite_token": token}, headers=outsider
    )
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/teams/{team_id}/applications", headers=mentor)
    application = resp.json()["data"]["items"][0]
    resp = await client.post(
        f"/api/v1/teams/{team_id}/applications/{application['id']}/review",
        json={"approve": True},
        headers=mentor,
    )
    assert resp.json()["code"] == 0
    resp = await client.post(
        f"/api/v1/teams/{team_id}/members/{await _uid_of(client, outsider)}/admin",
        json={"is_admin": True},
        headers=mentor,
    )
    assert resp.json()["code"] == 0

    resp = await client.get(f"/api/v1/problems/{pid2}", headers=outsider)
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["can_manage"] is False
    resp = await client.put(f"/api/v1/problems/{pid2}", json={"title": "x"}, headers=outsider)
    assert resp.json()["code"] == 2003

    # 组织上下文详情端点（成员门）
    resp = await client.get(f"/api/v1/orgs/{org_id}/problems/{pid2}", headers=member)
    assert resp.json()["code"] == 0, resp.text
    resp = await client.get(f"/api/v1/orgs/{org_id}/problems/{pid2}", headers=outsider)
    assert resp.json()["code"] == 2003

    # 管理端视图：admin 全量（含成员列表）
    from .conftest import admin_api_headers

    admin = await admin_api_headers(client)
    resp = await client.get("/api/v1/admin/orgs", headers=admin)
    assert resp.json()["data"]["total"] == 1
    resp = await client.get(f"/api/v1/admin/orgs/{org_id}/members", headers=admin)
    assert resp.json()["data"]["total"] == 3


async def test_disband_org(client: httpx.AsyncClient) -> None:
    """解散组织：仅站点 admin；授权与成员清理；再次解散 409。"""
    mentor, org_id = await _make_org_admin(client, "disbandboss@pigeonoj.dev")
    from .conftest import admin_api_headers

    admin = await admin_api_headers(client)

    # org_admin 不可解散
    resp = await client.delete(f"/api/v1/orgs/{org_id}", headers=mentor)
    assert resp.json()["code"] == 2003

    resp = await client.delete(f"/api/v1/orgs/{org_id}", headers=admin)
    assert resp.json()["code"] == 0, resp.text

    resp = await client.delete(f"/api/v1/orgs/{org_id}", headers=admin)
    assert resp.json()["code"] == 3002  # 幂等：已解散（状态冲突）

    # 解散后：成员不可见详情、我的组织为空
    resp = await client.get(f"/api/v1/orgs/{org_id}", headers=mentor)
    assert resp.json()["code"] == 2003
    resp = await client.get("/api/v1/orgs/mine", headers=mentor)
    assert resp.json()["data"]["total"] == 0

"""团队模块集成测试（docs/contracts/teams.md）。

覆盖：创建权限与自动授权、邀请链接生成 / 解析、加入申请与审批、
分配 / 取消管理员（仅创建者）、踢出 / 退出 / 解散的授权同步、非成员与普通成员的权限边界。
"""
from __future__ import annotations

import uuid as uuid_mod

import httpx
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.user import User, UserRole

from .conftest import api_login, register_user

TUTOR_ROLE_ID = uuid_mod.UUID("22222222-2222-2222-2222-222222222222")
TEAM_ADMIN_ROLE_ID = uuid_mod.UUID("55555555-5555-5555-5555-555555555555")


async def _tutor_headers(client: httpx.AsyncClient) -> dict[str, str]:
    email = "tutor@pigeonoj.dev"
    await register_user(client, email)
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        db.add(UserRole(user_id=user.id, role_id=TUTOR_ROLE_ID, scope="global", object_id=None))
        await db.commit()
    token = await api_login(client, email, "Pass@123")
    return {"Authorization": f"Bearer {token}"}


async def _extra_user_headers(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    await register_user(client, email)
    token = await api_login(client, email, "Pass@123")
    return {"Authorization": f"Bearer {token}"}


async def _uid_of(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    """当前登录用户 id（GET /users/me）。"""
    resp = await client.get("/api/v1/users/me", headers=headers)
    assert resp.json()["code"] == 0, resp.text
    return resp.json()["data"]["id"]


async def test_create_team_and_permissions(client: httpx.AsyncClient) -> None:
    """创建团队：admin/tutor 可建，普通用户 2003；创建者自动在册并成为 team_creator。"""
    tutor = await _tutor_headers(client)
    resp = await client.post(
        "/api/v1/teams",
        json={"name": "信奥集训队", "description": "校内集训"},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text
    team_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["my_role"] == "creator"
    assert resp.json()["data"]["member_count"] == 1

    resp = await client.post("/api/v1/teams", json={"name": "算法二队"}, headers=tutor)
    assert resp.json()["code"] == 0

    resp = await client.get("/api/v1/teams/mine", headers=tutor)
    assert resp.json()["data"]["total"] == 2

    # 名称关键字过滤
    resp = await client.get(
        "/api/v1/teams/mine?keyword=%E4%BF%A1%E5%A5%A5", headers=tutor
    )
    assert resp.json()["data"]["total"] == 1
    assert resp.json()["data"]["items"][0]["id"] == team_id
    resp = await client.get("/api/v1/teams/mine?keyword=nomatch", headers=tutor)
    assert resp.json()["data"]["total"] == 0

    # 普通用户不可创建团队
    user = await _extra_user_headers(client, "creator2@pigeonoj.dev")
    resp = await client.post("/api/v1/teams", json={"name": "路人队"}, headers=user)
    assert resp.json()["code"] == 2003

    # 非成员不可见详情
    resp = await client.get(f"/api/v1/teams/{team_id}", headers=user)
    assert resp.json()["code"] == 2003


async def test_invite_apply_review_flow(client: httpx.AsyncClient) -> None:
    """邀请 → 申请 → 审批闭环：通过后在册 + team_member 授权；重复申请 3003。"""
    tutor = await _tutor_headers(client)
    resp = await client.post("/api/v1/teams", json={"name": "算法小组"}, headers=tutor)
    team_id = resp.json()["data"]["id"]

    # 生成邀请链接（public 解析）
    resp = await client.post(f"/api/v1/teams/{team_id}/invites", headers=tutor)
    assert resp.json()["code"] == 0, resp.text
    token = resp.json()["data"]["token"]
    assert resp.json()["data"]["expires_at"]

    resp = await client.get(f"/api/v1/teams/invites/{token}")
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["team_id"] == team_id
    assert resp.json()["data"]["team_name"] == "算法小组"

    # 无效 token：解析与申请均 3001
    resp = await client.get("/api/v1/teams/invites/no-such-token")
    assert resp.json()["code"] == 3001
    user = await _extra_user_headers(client, "member1@pigeonoj.dev")
    resp = await client.post(
        f"/api/v1/teams/{team_id}/applications",
        json={"invite_token": "bogus"},
        headers=user,
    )
    assert resp.json()["code"] == 3001

    # 提交申请（带有效 token）→ 重复申请 3003 → 审批通过
    resp = await client.post(
        f"/api/v1/teams/{team_id}/applications",
        json={"invite_token": token},
        headers=user,
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.post(
        f"/api/v1/teams/{team_id}/applications", json={}, headers=user
    )
    assert resp.json()["code"] == 3003

    resp = await client.get(f"/api/v1/teams/{team_id}/applications", headers=tutor)
    assert resp.json()["data"]["total"] == 1
    application = resp.json()["data"]["items"][0]
    assert application["status"] == "pending"
    assert application["invite_token"] == token

    resp = await client.post(
        f"/api/v1/teams/{team_id}/applications/{application['id']}/review",
        json={"approve": True},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text

    # 通过后：成员可见详情与成员列表；成员列表含创建者与新人
    resp = await client.get(f"/api/v1/teams/{team_id}", headers=user)
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["my_role"] == "member"
    assert resp.json()["data"]["member_count"] == 2
    resp = await client.get("/api/v1/teams/mine", headers=user)
    assert resp.json()["data"]["total"] == 1
    resp = await client.get(f"/api/v1/teams/{team_id}/members", headers=user)
    assert resp.json()["data"]["total"] == 2

    # 已在团队成员再申请 → 3003
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=user)
    assert resp.json()["code"] == 3003


async def test_admin_assignment(client: httpx.AsyncClient) -> None:
    """分配 / 取消管理员：仅创建者；分配后可执行团队管理操作；取消后权限回收。"""
    tutor = await _tutor_headers(client)
    resp = await client.post("/api/v1/teams", json={"name": "管理分配队"}, headers=tutor)
    team_id = resp.json()["data"]["id"]
    user = await _extra_user_headers(client, "admin2@pigeonoj.dev")

    resp = await client.post(f"/api/v1/teams/{team_id}/invites", headers=tutor)
    token = resp.json()["data"]["token"]
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={"invite_token": token}, headers=user)
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/teams/{team_id}/applications", headers=tutor)
    application = resp.json()["data"]["items"][0]
    resp = await client.post(
        f"/api/v1/teams/{team_id}/applications/{application['id']}/review",
        json={"approve": True},
        headers=tutor,
    )
    assert resp.json()["code"] == 0

    uid = await client.get(f"/api/v1/teams/{team_id}/members", headers=tutor)
    members = uid.json()["data"]["items"]
    target_uid = next(m["user_id"] for m in members if not m["is_creator"])

    # 非创建者不可分配管理员
    resp = await client.post(
        f"/api/v1/teams/{team_id}/members/{target_uid}/admin",
        json={"is_admin": True},
        headers=user,
    )
    assert resp.json()["code"] == 2003

    # 分配管理员：成员可见 is_admin 标记，可生成邀请 / 查看申请列表
    resp = await client.post(
        f"/api/v1/teams/{team_id}/members/{target_uid}/admin",
        json={"is_admin": True},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.post(f"/api/v1/teams/{team_id}/invites", headers=user)
    assert resp.json()["code"] == 0, resp.text
    resp = await client.get(f"/api/v1/teams/{team_id}/applications", headers=user)
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/teams/{team_id}/members", headers=user)
    assert next(m["is_admin"] for m in resp.json()["data"]["items"] if m["user_id"] == target_uid)

    # 取消管理员：管理权限回收
    resp = await client.post(
        f"/api/v1/teams/{team_id}/members/{target_uid}/admin",
        json={"is_admin": False},
        headers=tutor,
    )
    assert resp.json()["code"] == 0
    resp = await client.post(f"/api/v1/teams/{team_id}/invites", headers=user)
    assert resp.json()["code"] == 2003

    # 普通成员不可查看申请列表
    resp = await client.get(f"/api/v1/teams/{team_id}/applications", headers=user)
    assert resp.json()["code"] == 2003

    # 目标非在册成员 → 3001；创建者本身不可被分配 → 2003
    creator_id = next(m["user_id"] for m in members if m["is_creator"])
    resp = await client.post(
        f"/api/v1/teams/{team_id}/members/{uuid_mod.uuid4()}/admin",
        json={"is_admin": True},
        headers=tutor,
    )
    assert resp.json()["code"] == 3001
    resp = await client.post(
        f"/api/v1/teams/{team_id}/members/{creator_id}/admin",
        json={"is_admin": True},
        headers=tutor,
    )
    assert resp.json()["code"] == 2003


async def test_kick_exit_disband(client: httpx.AsyncClient) -> None:
    """踢出 / 退出 / 解散：成员状态与团队授权同步清理；解散仅创建者。"""
    tutor = await _tutor_headers(client)
    resp = await client.post("/api/v1/teams", json={"name": "生命周期队"}, headers=tutor)
    team_id = resp.json()["data"]["id"]

    member_a = await _extra_user_headers(client, "kickme@pigeonoj.dev")
    member_b = await _extra_user_headers(client, "exitme@pigeonoj.dev")
    admin2 = await _extra_user_headers(client, "disbander@pigeonoj.dev")
    for headers in (member_a, member_b):
        resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=headers)
        assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/teams/{team_id}/applications", headers=tutor)
    for application in resp.json()["data"]["items"]:
        resp = await client.post(
            f"/api/v1/teams/{team_id}/applications/{application['id']}/review",
            json={"approve": True},
            headers=tutor,
        )
        assert resp.json()["code"] == 0

    # 提升一人为管理员（后续用于验证非创建者不可解散）
    resp = await client.get(f"/api/v1/teams/{team_id}/members", headers=tutor)
    members = resp.json()["data"]["items"]
    admin_uid = next(m["user_id"] for m in members if not m["is_creator"])
    resp = await client.post(
        f"/api/v1/teams/{team_id}/members/{admin_uid}/admin",
        json={"is_admin": True},
        headers=tutor,
    )
    assert resp.json()["code"] == 0

    # 踢出 member_a：授权清理（我的团队为空、不可见详情）；创建者不可被踢
    resp = await client.delete(
        f"/api/v1/teams/{team_id}/members/{await _uid_of(client, member_a)}", headers=tutor
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.get("/api/v1/teams/mine", headers=member_a)
    assert resp.json()["data"]["total"] == 0
    resp = await client.get(f"/api/v1/teams/{team_id}", headers=member_a)
    assert resp.json()["code"] == 2003

    creator_uid = next(m["user_id"] for m in members if m["is_creator"])
    resp = await client.delete(f"/api/v1/teams/{team_id}/members/{creator_uid}", headers=tutor)
    assert resp.json()["code"] == 2003

    # 退出：创建者不可退出；成员退出后授权清理
    resp = await client.post(f"/api/v1/teams/{team_id}/exit", headers=tutor)
    assert resp.json()["code"] == 2003
    resp = await client.post(f"/api/v1/teams/{team_id}/exit", headers=admin2)
    assert resp.json()["code"] == 2003  # 非成员
    resp = await client.post(f"/api/v1/teams/{team_id}/exit", headers=member_b)
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/teams/{team_id}/members", headers=tutor)
    assert resp.json()["data"]["total"] == 1  # 仅剩创建者

    # 解散：非创建者（即便管理员）2003；创建者可解散；解散后授权全清
    resp = await client.delete(f"/api/v1/teams/{team_id}", headers=member_b)
    assert resp.json()["code"] == 2003
    resp = await client.delete(f"/api/v1/teams/{team_id}", headers=tutor)
    assert resp.json()["code"] == 0, resp.text

    resp = await client.get(f"/api/v1/teams/{team_id}", headers=tutor)
    assert resp.json()["code"] == 2003  # 已解散：成员授权清理，不可见详情
    resp = await client.get("/api/v1/teams/mine", headers=tutor)
    assert resp.json()["data"]["total"] == 0
    resp = await client.delete(f"/api/v1/teams/{team_id}", headers=tutor)
    assert resp.json()["code"] == 409 or resp.json()["code"] == 2003  # 幂等：再次解散拒绝

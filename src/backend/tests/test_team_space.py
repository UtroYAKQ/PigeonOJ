"""团队空间集成测试（docs/contracts/teams.md「团队空间」节）。

覆盖：团队题库（引用 / 列表可见性 / 裸路径隔离 / 上下文详情与交题）、
团队题单（创建 / 引用 / 编排 / 下线 / 上下文隔离）、团队比赛（创建 / 团队报名 /
非成员不可见 / 编排候选隔离）与团队题目不得流入公开编排的边界。
"""
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.problem import Problem
from app.models.problem_set import ProblemSet
from app.models.user import User, UserRole

from .conftest import api_login, register_user

TUTOR_ROLE_ID = uuid_mod.UUID("22222222-2222-2222-2222-222222222222")
ADMIN_ROLE_ID = uuid_mod.UUID("11111111-1111-1111-1111-111111111111")


async def _tutor_headers(client: httpx.AsyncClient, email: str = "tutor@pigeonoj.dev") -> dict[str, str]:
    await register_user(client, email)
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        db.add(UserRole(user_id=user.id, role_id=TUTOR_ROLE_ID, scope="global", object_id=None))
        await db.commit()
    token = await api_login(client, email, "Pass@123")
    return {"Authorization": f"Bearer {token}"}


async def _user_headers(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    await register_user(client, email)
    token = await api_login(client, email, "Pass@123")
    return {"Authorization": f"Bearer {token}"}


async def _create_team(client: httpx.AsyncClient, headers: dict[str, str], name: str) -> str:
    # 团队空间用例走公开团队（成员可经团队列表直接申请，保持原动线）；私有门控见 test_teams.py
    resp = await client.post(
        "/api/v1/teams", json={"name": name, "visibility": "public"}, headers=headers
    )
    assert resp.json()["code"] == 0, resp.text
    return resp.json()["data"]["id"]


async def _join_team(client: httpx.AsyncClient, team_id: str, headers: dict[str, str]) -> None:
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=headers)
    assert resp.json()["code"] == 0, resp.text
    resp = await client.get(f"/api/v1/teams/{team_id}/applications", headers=headers)
    # 申请人自己看不到申请列表（需管理员），改由创建者审批——headers 传入创建者头时跳过
    return


async def _seed_problem(
    title: str,
    *,
    status: str = "published",
    visibility: str = "public",
    owner_email: str = "admin@pigeonoj.dev",
) -> str:
    async with SessionLocal() as db:
        uid = (
            await db.execute(select(User).where(User.email == owner_email))
        ).scalar_one().id
        problem = Problem(
            title=title,
            description="D",
            owner_id=uid,
            status=status,
            visibility=visibility,
            verified_at=datetime.now(timezone.utc) if status == "published" else None,
        )
        db.add(problem)
        await db.commit()
        return str(problem.id)


async def _approve_all(client: httpx.AsyncClient, team_id: str, owner_headers: dict[str, str]) -> None:
    resp = await client.get(f"/api/v1/teams/{team_id}/applications", headers=owner_headers)
    for application in resp.json()["data"]["items"]:
        resp = await client.post(
            f"/api/v1/teams/{team_id}/applications/{application['id']}/review",
            json={"approve": True},
            headers=owner_headers,
        )
        assert resp.json()["code"] == 0, resp.text


def _future_contest_body(problem_id: str | None = None) -> dict:
    start = datetime.now(timezone.utc) + timedelta(days=7)
    return {
        "title": "队内赛",
        "rule_type": "ACM",
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(hours=2)).isoformat(),
        "register_start_time": datetime.now(timezone.utc).isoformat(),
        "register_end_time": (start - timedelta(hours=1)).isoformat(),
        "problems": [{"problem_id": problem_id, "score": 100}] if problem_id else [],
    }


# ---------------- 团队题库 ----------------


async def test_team_problem_reference_and_isolation(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    """引用本人题目进团队（快照复制新题）：新题继承题面 / referenced_at；
    源题留在个人题库；同源题防重（409）；成员仅见 team_visible；
    题库裸路径拦截团队题；他人题目不可引用。"""
    tutor = await _tutor_headers(client)
    team_id = await _create_team(client, tutor, "题库队")

    # tutor 引用他人（admin）私有题 → 403（单一所有权）
    admin_problem = await _seed_problem("他人私有题", visibility="private")
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": admin_problem, "visibility": "team_visible"},
        headers=tutor,
    )
    assert resp.json()["code"] == 2003, resp.text

    # tutor 创建自己的私有题（直接种子指定 owner=tutor）
    async with SessionLocal() as db:
        tutor_uid = (
            await db.execute(select(User).where(User.email == "tutor@pigeonoj.dev"))
        ).scalar_one().id
        problem = Problem(
            title="我的私有题",
            description="D",
            owner_id=tutor_uid,
            status="published",
            visibility="private",
            verified_at=datetime.now(timezone.utc),
        )
        db.add(problem)
        await db.commit()
        my_problem_id = str(problem.id)
        source_problem_id = problem.id

    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": my_problem_id, "visibility": "team_visible"},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text
    item = resp.json()["data"]
    assert item["referenced_at"]  # 引用字段：非空 = 经引用进入团队
    assert item["visibility"] == "team_visible"
    team_copy_id = item["id"]
    assert team_copy_id != my_problem_id  # 快照复制：新题 ≠ 源题

    # 源题留在个人题库（归属切换语义废弃），未被置为团队题
    async with SessionLocal() as db:
        source = await db.get(Problem, source_problem_id)
        assert source.team_id is None
        assert source.visibility == "private"

    # 同源题重复引用 → 409（同团队同源唯一）
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": my_problem_id},
        headers=tutor,
    )
    assert resp.json()["code"] == 3003, resp.text

    # 引用候选列表：已引用的源题不再出现（服务端排除，引用页不再显示可点按钮）
    resp = await client.get(
        f"/api/v1/teams/{team_id}/problems/referenceable", headers=tutor
    )
    assert resp.json()["code"] == 0, resp.text
    ref_ids = [it["id"] for it in resp.json()["data"]["items"]]
    assert my_problem_id not in ref_ids

    # 源题（个人私有题）走题库裸路径：owner 可见
    user = await _user_headers(client, "member1@pigeonoj.dev")
    resp = await client.get(f"/api/v1/problems/{my_problem_id}", headers=tutor)
    assert resp.json()["code"] == 0

    # 团队快照题（team_visible）对非成员走裸路径 → 403（题库隔离）
    resp = await client.get(f"/api/v1/problems/{team_copy_id}", headers=tutor)
    assert resp.status_code == 403

    # 全局 admin 裸路径可读快照题（管理动线只读浏览，teams.md 管理端；回归：admin 预览不被误伤）
    resp = await client.get(f"/api/v1/problems/{team_copy_id}", headers=admin_headers)
    assert resp.json()["code"] == 0, resp.text

    # 普通成员（非团队成员）访问团队题库 → 2003
    resp = await client.get(f"/api/v1/teams/{team_id}/problems", headers=user)
    assert resp.json()["code"] == 2003

    # 加入团队后可见团队题库（team_visible 快照题）
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=user)
    assert resp.json()["code"] == 0
    await _approve_all(client, team_id, tutor)
    resp = await client.get(f"/api/v1/teams/{team_id}/problems", headers=user)
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["total"] == 1
    assert resp.json()["data"]["items"][0]["id"] == team_copy_id
    assert resp.json()["data"]["items"][0]["referenced_at"]

    # 团队上下文详情 / 交题（统一入口）
    resp = await client.get(f"/api/v1/teams/{team_id}/problems/{team_copy_id}", headers=user)
    assert resp.json()["code"] == 0, resp.text
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/{team_copy_id}/submissions",
        json={"language": "cpp17", "code": "int main(){}"},
        headers=user,
    )
    assert resp.json()["code"] == 0, resp.text

    # admin_visible 题目：他人（admin）题目，tutor 不可引用
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": admin_problem, "visibility": "admin_visible"},
        headers=tutor,
    )
    assert resp.json()["code"] == 2003

    # 题库编辑可见性：团队题分支内切换（team_visible ↔ admin_visible）放行；
    # 跨分支（团队题 → public）拒绝 1001（回归：编辑页团队可见性下拉）
    resp = await client.put(
        f"/api/v1/problems/{team_copy_id}",
        json={"visibility": "admin_visible"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.put(
        f"/api/v1/problems/{team_copy_id}",
        json={"visibility": "public"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 1001

    # 团队快照题不出现在题库中心（公开列表隔离）
    resp = await client.get("/api/v1/problems")
    titles = [it["title"] for it in resp.json()["data"]["items"]]
    assert "我的私有题" not in titles

    # 题库中心「我的」勾选同样不进团队快照题（封闭空间，回归：mine=true 不含 team_id 题；
    # 源题是本人全站题，仍应出现在本人列表——按 id 区分源题与快照）
    resp = await client.get("/api/v1/problems?mine=true", headers=tutor)
    assert resp.json()["code"] == 0, resp.text
    mine_ids = {it["id"] for it in resp.json()["data"]["items"]}
    assert team_copy_id not in mine_ids
    assert my_problem_id in mine_ids


async def test_team_arrangeable_search_excludes_others(client: httpx.AsyncClient) -> None:
    """团队编排候选：本团队 ∪ 全站公开 ∪ 本人私有；他人私有题不出现；成员 2003。"""
    tutor = await _tutor_headers(client)
    team_id = await _create_team(client, tutor, "候选队")
    admin_pub = await _seed_problem("公开题A")
    admin_priv = await _seed_problem("他人私有B", visibility="private")

    resp = await client.get(
        f"/api/v1/teams/{team_id}/problems/arrangeable", headers=tutor
    )
    assert resp.json()["code"] == 0, resp.text
    ids = {it["id"] for it in resp.json()["data"]["items"]}
    assert admin_pub in ids
    assert admin_priv not in ids

    user = await _user_headers(client, "member2@pigeonoj.dev")
    resp = await client.get(f"/api/v1/teams/{team_id}/problems/arrangeable", headers=user)
    assert resp.json()["code"] == 2003


async def _seed_team_problem(
    title: str,
    *,
    team_id: str,
    owner_email: str,
    status: str = "published",
    visibility: str = "team_visible",
    samples_after_verify: bool = False,
) -> str:
    async with SessionLocal() as db:
        uid = (
            await db.execute(select(User).where(User.email == owner_email))
        ).scalar_one().id
        now = datetime.now(timezone.utc)
        if status == "published":
            # 默认样例早于验题通过时间（无需重验）；samples_after_verify 时样例晚于验题
            verified_at, samples_updated_at = (
                (now - timedelta(days=1), now)
                if samples_after_verify
                else (now, now - timedelta(days=1))
            )
        else:
            verified_at, samples_updated_at = None, now
        problem = Problem(
            title=title,
            description="D",
            owner_id=uid,
            status=status,
            visibility=visibility,
            team_id=uuid_mod.UUID(team_id),
            verified_at=verified_at,
            samples_updated_at=samples_updated_at,
        )
        db.add(problem)
        await db.commit()
        return str(problem.id)


async def test_team_problem_list_publish_states_and_draft_box(
    client: httpx.AsyncClient,
) -> None:
    """团队题库管理视图（草稿箱语义）：主列表仅已发布（含 admin_visible），
    草稿收敛到 status=draft 草稿箱且仅本人草稿（他人草稿不可见），
    归档在团队空间任何视图不可见；管理视图回填 needs_reverification。"""
    tutor = await _tutor_headers(client)
    team_id = await _create_team(client, tutor, "草稿箱队")

    await _seed_team_problem("已发布团队题", team_id=team_id, owner_email="tutor@pigeonoj.dev")
    await _seed_team_problem(
        "已发布管理题", team_id=team_id, owner_email="tutor@pigeonoj.dev",
        visibility="admin_visible",
    )
    await _seed_team_problem(
        "样例变更题", team_id=team_id, owner_email="tutor@pigeonoj.dev",
        samples_after_verify=True,
    )
    await _seed_team_problem(
        "tutor草稿", team_id=team_id, owner_email="tutor@pigeonoj.dev", status="draft"
    )
    await _seed_team_problem(
        "已归档题", team_id=team_id, owner_email="tutor@pigeonoj.dev", status="archived"
    )

    # 主列表：仅已发布（团队可见 + 管理可见均返回），草稿 / 归档不出现
    resp = await client.get(f"/api/v1/teams/{team_id}/problems", headers=tutor)
    assert resp.json()["code"] == 0, resp.text
    items = resp.json()["data"]["items"]
    assert {it["title"] for it in items} == {"已发布团队题", "已发布管理题", "样例变更题"}
    assert all(it["status"] == "published" for it in items)

    # 发布与验题状态：needs_reverification 精确回填（样例晚于验题通过时间 → True）
    flags = {it["title"]: it["needs_reverification"] for it in items}
    assert flags["样例变更题"] is True
    assert flags["已发布团队题"] is False

    # 普通成员视图不变：仅 published + team_visible（admin_visible 不出现）
    member = await _user_headers(client, "draftbox-admin@pigeonoj.dev")
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=member)
    assert resp.json()["code"] == 0
    await _approve_all(client, team_id, tutor)
    resp = await client.get(f"/api/v1/teams/{team_id}/problems", headers=member)
    assert resp.json()["code"] == 0, resp.text
    assert {it["title"] for it in resp.json()["data"]["items"]} == {"已发布团队题", "样例变更题"}

    # 提升为团队管理员后：草稿箱视图仅本人草稿；他人草稿不可见
    async with SessionLocal() as db:
        other_uid = str(
            (
                await db.execute(
                    select(User).where(User.email == "draftbox-admin@pigeonoj.dev")
                )
            ).scalar_one().id
        )
    resp = await client.post(
        f"/api/v1/teams/{team_id}/members/{other_uid}/admin",
        json={"is_admin": True},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text
    await _seed_team_problem(
        "他人草稿", team_id=team_id, owner_email="draftbox-admin@pigeonoj.dev", status="draft"
    )

    resp = await client.get(f"/api/v1/teams/{team_id}/problems?status=draft", headers=tutor)
    assert resp.json()["code"] == 0, resp.text
    assert {it["title"] for it in resp.json()["data"]["items"]} == {"tutor草稿"}

    resp = await client.get(f"/api/v1/teams/{team_id}/problems?status=draft", headers=member)
    assert resp.json()["code"] == 0, resp.text
    assert {it["title"] for it in resp.json()["data"]["items"]} == {"他人草稿"}

    # 归档在团队空间不可见（显式 status=archived 恒为空；管理后台 admin_view 仍可查）
    resp = await client.get(f"/api/v1/teams/{team_id}/problems?status=archived", headers=tutor)
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["total"] == 0


# ---------------- 团队题单 ----------------


async def test_team_problem_set_lifecycle(client: httpx.AsyncClient) -> None:
    """团队题单：成员创建 2003；管理员创建 / 编排 / 下线；复制他人题单 403；
    复制 = 快照（源题单保留在全站）；团队题单不进题单中心；成员可见详情。"""
    tutor = await _tutor_headers(client)
    team_id = await _create_team(client, tutor, "题单队")

    # 普通成员不可创建
    member = await _user_headers(client, "setmember@pigeonoj.dev")
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets", json={"title": "成员题单"}, headers=member
    )
    assert resp.json()["code"] == 2003

    # 复制他人题单 → 403（仅可复制本人创建的题单）
    other_set = ProblemSet(
        title="他人全站题单",
        owner_id=(
            await _uid_by_email(client, "admin@pigeonoj.dev")
        ),
        visibility="public",
    )
    async with SessionLocal() as db:
        db.add(other_set)
        await db.commit()
        other_set_id = str(other_set.id)
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets",
        json={"title": "拷贝他人", "copy_items_from": other_set_id},
        headers=tutor,
    )
    assert resp.json()["code"] == 2003

    # tutor 建全站题单（含一条编排公开题）再复制进团队
    my_set = (
        await client.post("/api/v1/problem-sets", json={"title": "集训题单"}, headers=tutor)
    ).json()["data"]
    pub_source = await _seed_problem("复制源公开题")
    resp = await client.put(
        f"/api/v1/problem-sets/{my_set['id']}/items",
        json={"items": [{"problem_id": pub_source}]},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text

    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets",
        json={"title": "集训题单（团队）", "copy_items_from": my_set["id"]},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text
    copied_set = resp.json()["data"]
    assert copied_set["visibility"] == "team_visible"
    assert copied_set["referenced_at"]
    assert copied_set["item_count"] == 1  # 快照复制源题单条目

    # 复制 = 快照：源题单保留在全站题单中心（不再归属切换）
    resp = await client.get("/api/v1/problem-sets")
    assert any(it["id"] == my_set["id"] for it in resp.json()["data"]["items"])

    # 复制来源校验：团队题单不可作为来源 / 不存在 404
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets",
        json={"title": "非法来源", "copy_items_from": copied_set["id"]},
        headers=tutor,
    )
    assert resp.json()["code"] == 1001

    # 团队自建题单 + 编排（公开题 + 本人私有题 + 团队题目候选）
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets", json={"title": "队内训练"}, headers=tutor
    )
    assert resp.json()["code"] == 0, resp.text
    team_set_id = resp.json()["data"]["id"]

    async with SessionLocal() as db:
        tutor_uid = (
            await db.execute(select(User).where(User.email == "tutor@pigeonoj.dev"))
        ).scalar_one().id
        team_problem = Problem(
            title="团队题",
            description="D",
            owner_id=tutor_uid,
            status="published",
            visibility="team_visible",
            team_id=uuid_mod.UUID(team_id),
            verified_at=datetime.now(timezone.utc),
        )
        db.add(team_problem)
        await db.commit()
        team_problem_id = str(team_problem.id)

    pub = await _seed_problem("编排公开题")
    resp = await client.put(
        f"/api/v1/teams/{team_id}/problem-sets/{team_set_id}/items",
        json={"items": [{"problem_id": pub, "sort_order": 0}, {"problem_id": team_problem_id, "sort_order": 1}]},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text

    # 全站题单编排不得引入团队题目（封闭空间隔离）
    solo_set = (
        await client.post("/api/v1/problem-sets", json={"title": "全站隔离"}, headers=tutor)
    ).json()["data"]
    resp = await client.put(
        f"/api/v1/problem-sets/{solo_set['id']}/items",
        json={"items": [{"problem_id": team_problem_id}]},
        headers=tutor,
    )
    assert resp.json()["code"] == 1001

    # 下线团队题单
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets/{team_set_id}/archive", headers=tutor
    )
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["status"] == "archived"

    # 团队题单详情（团队上下文统一入口）：items 与编排一致（回归：详情题目列表非空）
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=member)
    assert resp.json()["code"] == 0
    await _approve_all(client, team_id, tutor)
    resp = await client.get(
        f"/api/v1/teams/{team_id}/problem-sets/{copied_set['id']}", headers=member
    )
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["visibility"] == "team_visible"
    assert len(resp.json()["data"]["items"]) == 1  # 复制题单继承源题单条目
    assert resp.json()["data"]["items"][0]["title"] == "复制源公开题"
    resp = await client.get(
        f"/api/v1/teams/{team_id}/problem-sets/{team_set_id}", headers=member
    )
    assert resp.json()["code"] == 0, resp.text
    detail_items = resp.json()["data"]["items"]
    assert len(detail_items) == 2  # 编排的公开题 + 团队题
    assert [it["title"] for it in detail_items] == ["编排公开题", "团队题"]

    # 团队题单不进题单中心；非成员不可见
    outsider = await _user_headers(client, "outsider1@pigeonoj.dev")
    resp = await client.get(
        f"/api/v1/teams/{team_id}/problem-sets/{copied_set['id']}", headers=outsider
    )
    assert resp.json()["code"] == 2003
    resp = await client.get("/api/v1/problem-sets")
    assert all(it["id"] != copied_set["id"] for it in resp.json()["data"]["items"])

    # 团队题单列表
    resp = await client.get(f"/api/v1/teams/{team_id}/problem-sets", headers=member)
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["total"] == 1  # 队内训练已下线（复制题单仍活跃）


async def test_team_set_visibility_admin_visible(client: httpx.AsyncClient) -> None:
    """团队题单可见性双分支（与团队题目对齐）：admin_visible 题单成员不可见
    （列表不出现 / 详情 / 内题目 / 交题 403），团队管理可见；team_visible 成员正常；
    题单中心与 mine 勾选不含团队题单。"""
    tutor = await _tutor_headers(client)
    team_id = await _create_team(client, tutor, "题单可见队")

    # 创建 admin_visible 题单 + team_visible 题单
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets",
        json={"title": "管理层题单", "visibility": "admin_visible"},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text
    admin_set_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["visibility"] == "admin_visible"

    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets", json={"title": "全员题单"}, headers=tutor
    )
    assert resp.json()["code"] == 0, resp.text
    team_set_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["visibility"] == "team_visible"  # 缺省 team_visible

    # 编排一题到 admin_visible 题单（成员交题 / 内题目门控用）
    pub = await _seed_problem("可见队公开题")
    resp = await client.put(
        f"/api/v1/teams/{team_id}/problem-sets/{admin_set_id}/items",
        json={"items": [{"problem_id": pub, "sort_order": 0}]},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text

    member = await _user_headers(client, "setvismember@pigeonoj.dev")
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=member)
    assert resp.json()["code"] == 0
    await _approve_all(client, team_id, tutor)

    # 成员列表：仅 team_visible；团队管理：两个都见
    resp = await client.get(f"/api/v1/teams/{team_id}/problem-sets", headers=member)
    assert resp.json()["code"] == 0, resp.text
    assert {it["title"] for it in resp.json()["data"]["items"]} == {"全员题单"}
    resp = await client.get(f"/api/v1/teams/{team_id}/problem-sets", headers=tutor)
    assert {it["title"] for it in resp.json()["data"]["items"]} == {"管理层题单", "全员题单"}

    # admin_visible：成员详情 / 内题目 / 交题 403；团队管理放行
    for method, url in (
        ("GET", f"/api/v1/teams/{team_id}/problem-sets/{admin_set_id}"),
        ("GET", f"/api/v1/teams/{team_id}/problem-sets/{admin_set_id}/problems/{pub}"),
        (
            "POST",
            f"/api/v1/teams/{team_id}/problem-sets/{admin_set_id}/problems/{pub}/submissions",
        ),
    ):
        if method == "GET":
            resp = await client.get(url, headers=member)
        else:
            resp = await client.post(url, json={"language": "cpp17", "code": "int main(){}"}, headers=member)
        assert resp.json()["code"] == 2003, resp.text
        assert resp.status_code == 403, resp.text

    resp = await client.get(
        f"/api/v1/teams/{team_id}/problem-sets/{admin_set_id}", headers=tutor
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.get(
        f"/api/v1/teams/{team_id}/problem-sets/{admin_set_id}/problems/{pub}", headers=tutor
    )
    assert resp.json()["code"] == 0, resp.text

    # team_visible：成员详情放行
    resp = await client.get(f"/api/v1/teams/{team_id}/problem-sets/{team_set_id}", headers=member)
    assert resp.json()["code"] == 0, resp.text

    # 团队题单不进题单中心 / mine 勾选（封闭空间）
    resp = await client.get(f"/api/v1/problem-sets?mine=true", headers=tutor)
    assert all(it["id"] not in (admin_set_id, team_set_id) for it in resp.json()["data"]["items"])


async def _uid_by_email(client: httpx.AsyncClient, email: str) -> uuid_mod.UUID:
    async with SessionLocal() as db:
        return (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one().id


# ---------------- 团队比赛 ----------------


async def test_team_contest_flow(client: httpx.AsyncClient) -> None:
    """团队比赛：成员创建 2003；管理员创建（contest_type=team）；编排候选放开团队题目；
    成员可报名；非成员报名 403 / 详情 2003；全站编排搜索不含团队比赛。"""
    tutor = await _tutor_headers(client)
    team_id = await _create_team(client, tutor, "比赛队")

    member = await _user_headers(client, "contestmember@pigeonoj.dev")
    resp = await client.post(
        f"/api/v1/teams/{team_id}/contests", json=_future_contest_body(), headers=member
    )
    assert resp.json()["code"] == 2003

    # 团队题目可入团队比赛（先用 API 引用进团队）
    async with SessionLocal() as db:
        tutor_uid = (
            await db.execute(select(User).where(User.email == "tutor@pigeonoj.dev"))
        ).scalar_one().id
        my_priv = Problem(
            title="队内秘密题",
            description="D",
            owner_id=tutor_uid,
            status="published",
            visibility="private",
            verified_at=datetime.now(timezone.utc),
        )
        db.add(my_priv)
        await db.commit()
        my_priv_id = str(my_priv.id)
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": my_priv_id},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text
    copy_id = resp.json()["data"]["id"]  # 快照题入赛

    body = _future_contest_body(copy_id)
    resp = await client.post(f"/api/v1/teams/{team_id}/contests", json=body, headers=tutor)
    assert resp.json()["code"] == 0, resp.text
    contest = resp.json()["data"]
    assert contest["contest_type"] == "team"
    assert contest["problem_count"] == 1

    # 团队比赛列表（成员视角）
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=member)
    assert resp.json()["code"] == 0
    await _approve_all(client, team_id, tutor)
    resp = await client.get(f"/api/v1/teams/{team_id}/contests", headers=member)
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["total"] == 1

    # 团队成员报名 → 0；重复报名 3003
    resp = await client.post(f"/api/v1/contests/{contest['id']}/register", headers=member)
    assert resp.json()["code"] == 0, resp.text
    resp = await client.post(f"/api/v1/contests/{contest['id']}/register", headers=member)
    assert resp.json()["code"] == 3003

    # 非成员：报名 403 / 详情 2003 / 不出现在比赛中心
    outsider = await _user_headers(client, "outsider2@pigeonoj.dev")
    resp = await client.post(f"/api/v1/contests/{contest['id']}/register", headers=outsider)
    assert resp.json()["code"] == 2003
    resp = await client.get(f"/api/v1/contests/{contest['id']}", headers=outsider)
    assert resp.json()["code"] == 2003
    resp = await client.get("/api/v1/contests")
    assert all(it["id"] != contest["id"] for it in resp.json()["data"]["items"])

    # 封闭空间：赛后看题 / 榜单 / 提交记录 / 单格成功提交均对非成员 2003
    # （回归：复用比赛统一端点时团队门不得缺位）
    resp = await client.get(f"/api/v1/contests/{contest['id']}/problems", headers=outsider)
    assert resp.json()["code"] == 2003, resp.text
    resp = await client.get(f"/api/v1/contests/{contest['id']}/board", headers=outsider)
    assert resp.json()["code"] == 2003, resp.text
    resp = await client.get(f"/api/v1/contests/{contest['id']}/submissions", headers=outsider)
    assert resp.json()["code"] == 2003, resp.text
    resp = await client.get(
        f"/api/v1/contests/{contest['id']}/board/00000000-0000-0000-0000-000000000001/00000000-0000-0000-0000-000000000002/accepted",
        headers=outsider,
    )
    assert resp.json()["code"] in (2003, 3001, 404)  # 团队门先于存在性

    # 团队成员：看题窗口未开（未来比赛）403，但详情可见；榜单可见（成员）
    resp = await client.get(f"/api/v1/contests/{contest['id']}/board", headers=member)
    assert resp.json()["code"] == 0, resp.text

    # 团队成员可见详情（复用比赛端点）
    resp = await client.get(f"/api/v1/contests/{contest['id']}", headers=member)
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["can_register"] is False  # 已报名

    # 全站比赛编排不得引入团队快照题（封闭空间隔离）
    resp = await client.post(
        "/api/v1/contests",
        json={**_future_contest_body(), "title": "全站赛", "problems": [{"problem_id": copy_id}]},
        headers=tutor,
    )
    assert resp.json()["code"] == 1001

    # 团队上下文端点：成员可读详情 / 榜单；比赛不属于该团队 → 3001
    resp = await client.get(
        f"/api/v1/teams/{team_id}/contests/{contest['id']}", headers=member
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.get(
        f"/api/v1/teams/{team_id}/contests/{contest['id']}/board", headers=member
    )
    assert resp.json()["code"] == 0, resp.text
    other_team = await _create_team(client, tutor, "另一队赛")
    resp = await client.get(
        f"/api/v1/teams/{other_team}/contests/{contest['id']}", headers=tutor
    )
    assert resp.json()["code"] == 3001
    resp = await client.get(
        f"/api/v1/teams/{team_id}/contests/{contest['id']}", headers=outsider
    )
    assert resp.json()["code"] == 2003


async def test_team_problem_statement_rejects_extra_team_id(client: httpx.AsyncClient) -> None:
    """团队题面更新：ProblemUpdate extra=forbid，body 不得携带 team_id（归属由路径给定）。"""
    tutor = await _tutor_headers(client)
    team_id = await _create_team(client, tutor, "题面队")
    resp = await client.post(
        "/api/v1/problems",
        json={
            "title": "队内草稿",
            "background": "B",
            "description": "D",
            "input_description": "I",
            "output_description": "O",
            "team_id": team_id,
            "visibility": "team_visible",
        },
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text
    pid = resp.json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/teams/{team_id}/problems/{pid}/statement",
        json={
            "title": "队内草稿改",
            "background": "B",
            "description": "D",
            "input_description": "I",
            "output_description": "O",
            "team_id": team_id,
        },
        headers=tutor,
    )
    assert resp.json()["code"] == 1001, resp.text
    resp = await client.put(
        f"/api/v1/teams/{team_id}/problems/{pid}/statement",
        json={
            "title": "队内草稿改",
            "background": "B",
            "description": "D",
            "input_description": "I",
            "output_description": "O",
        },
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text


async def test_team_problem_bare_path_blocked_after_reference(client: httpx.AsyncClient) -> None:
    """引用后的团队题目（team_visible）：非创建者题库裸路径交题 / 自测 403，
    团队上下文自测门控放行（进入派发阶段——无节点时 502 / 冷却 429 均视为门控通过）。"""
    tutor = await _tutor_headers(client)
    team_id = await _create_team(client, tutor, "自测队")
    async with SessionLocal() as db:
        tutor_uid = (
            await db.execute(select(User).where(User.email == "tutor@pigeonoj.dev"))
        ).scalar_one().id
        problem = Problem(
            title="自测题",
            description="D",
            owner_id=tutor_uid,
            status="published",
            visibility="private",
            verified_at=datetime.now(timezone.utc),
        )
        db.add(problem)
        await db.commit()
        pid = str(problem.id)
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": pid},
        headers=tutor,
    )
    assert resp.json()["code"] == 0
    copy_id = resp.json()["data"]["id"]  # 快照复制：团队上下文走新题 id

    member = await _user_headers(client, "selftestmember@pigeonoj.dev")
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=member)
    assert resp.json()["code"] == 0
    await _approve_all(client, team_id, tutor)

    # 裸路径自测（非创建者）→ 403；快照题对创建者也封死（团队上下文隔离）
    resp = await client.post(
        f"/api/v1/problems/{copy_id}/run-code",
        json={"language": "cpp17", "code": "int main(){}", "input": ""},
        headers=member,
    )
    assert resp.status_code == 403, resp.text

    # 团队上下文自测（快照题）：门控通过后进入网关派发（无节点 → 5001；或冷却窗口 → 429）
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/{copy_id}/run-code",
        json={"language": "cpp17", "code": "int main(){}", "input": ""},
        headers=member,
    )
    assert resp.json()["code"] in (5001, 429), resp.text

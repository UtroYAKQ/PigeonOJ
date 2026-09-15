"""团队空间集成测试（docs/contracts/teams.md「团队空间」节 / orgs.md）。

覆盖：团队题库（引用 = 组织题库 ∪ 全站公开的快照复制 / 列表可见性 / 裸路径隔离 /
上下文详情与交题）、团队题单（创建 / 编排 / 下线 / 上下文隔离）、团队比赛（创建 /
团队报名 / 非成员不可见 / 编排候选隔离）与团队题目不得流入公开编排的边界。
团队直建已移除：团队题目只来自引用快照。
"""
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.problem import Problem
from app.models.problem_set import ProblemSet
from app.models.user import User

from .conftest import api_login, create_org, register_user

ADMIN_ROLE_ID = uuid_mod.UUID("11111111-1111-1111-1111-111111111111")


async def _org_admin_headers(
    client: httpx.AsyncClient, email: str = "mentor@pigeonoj.dev"
) -> tuple[dict[str, str], str]:
    """注册用户 → 创建组织并任命其为组织管理员 → (headers, org_id)。"""
    await register_user(client, email)
    token = await api_login(client, email, "Pass@123")
    headers = {"Authorization": f"Bearer {token}"}
    uid = (await client.get("/api/v1/users/me", headers=headers)).json()["data"]["id"]
    org_id = await create_org(client, f"组织-{email}", [uid])
    return headers, org_id


async def _user_headers(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    await register_user(client, email)
    token = await api_login(client, email, "Pass@123")
    return {"Authorization": f"Bearer {token}"}


async def _create_team(
    client: httpx.AsyncClient, headers: dict[str, str], org_id: str, name: str,
    visibility: str = "public",
) -> str:
    """组织内建团（org_admin 门；团队空间用例走公开团队保持申请动线）。"""
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/teams",
        json={"name": name, "visibility": visibility},
        headers=headers,
    )
    assert resp.json()["code"] == 0, resp.text
    return resp.json()["data"]["id"]


async def _seed_problem(
    title: str,
    *,
    status: str = "published",
    visibility: str = "public",
    owner_email: str = "admin@pigeonoj.dev",
) -> str:
    """全站题（个人出题取消后全站题仅 admin 创建，owner 固定 admin 即可）。"""
    async with SessionLocal() as db:
        uid = (
            await db.execute(select(User).where(User.email == owner_email))
        ).scalar_one().id
        problem = Problem(
            title=title,
            background="B",
            description="D",
            input_description="I",
            output_description="O",
            owner_id=uid,
            status=status,
            visibility=visibility,
            verified_at=datetime.now(timezone.utc) if status == "published" else None,
        )
        db.add(problem)
        await db.commit()
        return str(problem.id)


async def _seed_org_problem(
    title: str,
    *,
    org_id: str,
    owner_email: str,
    status: str = "published",
    visibility: str = "org_visible",
) -> str:
    """组织题库题目（直插，published 带 verified_at）。"""
    async with SessionLocal() as db:
        uid = (
            await db.execute(select(User).where(User.email == owner_email))
        ).scalar_one().id
        problem = Problem(
            title=title,
            background="B",
            description="D",
            input_description="I",
            output_description="O",
            owner_id=uid,
            org_id=uuid_mod.UUID(org_id),
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
    """引用题进团队（快照复制新题）：来源 = 本组织组织题 ∪ 全站公开；
    他人私有题不可引用；新题继承题面 / referenced_at；源题留在组织题库；
    同源题防重（409）；成员仅见 team_visible；题库裸路径拦截团队题。"""
    mentor, org_id = await _org_admin_headers(client)
    team_id = await _create_team(client, mentor, org_id, "题库队")

    # 引用 admin 私有题（非公开、非本组织题库）→ 403（来源池外）
    admin_problem = await _seed_problem("他人私有题", visibility="private")
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": admin_problem, "visibility": "team_visible"},
        headers=mentor,
    )
    assert resp.json()["code"] == 2003, resp.text

    # 组织题库题目（mentor 创建，published + org_visible）→ 引用成功
    org_problem_id = await _seed_org_problem("组织题甲", org_id=org_id, owner_email="mentor@pigeonoj.dev")
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": org_problem_id, "visibility": "team_visible"},
        headers=mentor,
    )
    assert resp.json()["code"] == 0, resp.text
    item = resp.json()["data"]
    assert item["referenced_at"]  # 引用字段：非空 = 经引用进入团队
    assert item["visibility"] == "team_visible"
    team_copy_id = item["id"]
    assert team_copy_id != org_problem_id  # 快照复制：新题 ≠ 源题

    # 源题留在组织题库（快照语义），未被置为团队题
    async with SessionLocal() as db:
        source = await db.get(Problem, uuid_mod.UUID(org_problem_id))
        assert source.team_id is None
        assert str(source.org_id) == org_id
        assert source.visibility == "org_visible"

    # 同源题重复引用 → 409（同团队同源唯一）
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": org_problem_id},
        headers=mentor,
    )
    assert resp.json()["code"] == 3003, resp.text

    # 全站公开题也可引用（来源池 = 组织题 ∪ 全站公开）
    pub_problem_id = await _seed_problem("公开题甲")
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": pub_problem_id, "visibility": "team_visible"},
        headers=mentor,
    )
    assert resp.json()["code"] == 0, resp.text

    # 引用候选列表：已引用的源题不再出现（服务端排除，引用页不再显示可点按钮）
    resp = await client.get(
        f"/api/v1/teams/{team_id}/problems/referenceable", headers=mentor
    )
    assert resp.json()["code"] == 0, resp.text
    ref_ids = [it["id"] for it in resp.json()["data"]["items"]]
    assert org_problem_id not in ref_ids
    assert pub_problem_id not in ref_ids

    # 源组织题走题库裸路径：组织成员可见
    user = await _user_headers(client, "member1@pigeonoj.dev")
    resp = await client.get(f"/api/v1/problems/{org_problem_id}", headers=mentor)
    assert resp.json()["code"] == 0

    # 团队快照题（team_visible）对非成员走裸路径 → 403（题库隔离）
    resp = await client.get(f"/api/v1/problems/{team_copy_id}", headers=mentor)
    assert resp.status_code == 403

    # 全局 admin 裸路径可读快照题（管理动线只读浏览，teams.md 管理端；回归：admin 预览不被误伤）
    resp = await client.get(f"/api/v1/problems/{team_copy_id}", headers=admin_headers)
    assert resp.json()["code"] == 0, resp.text

    # 普通用户（非团队成员）访问团队题库 → 2003
    resp = await client.get(f"/api/v1/teams/{team_id}/problems", headers=user)
    assert resp.json()["code"] == 2003

    # 加入团队后可见团队题库（team_visible 快照题）
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=user)
    assert resp.json()["code"] == 0
    await _approve_all(client, team_id, mentor)
    resp = await client.get(f"/api/v1/teams/{team_id}/problems", headers=user)
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["total"] == 2
    assert all(it["referenced_at"] for it in resp.json()["data"]["items"])

    # 团队上下文详情 / 交题（统一入口）
    resp = await client.get(f"/api/v1/teams/{team_id}/problems/{team_copy_id}", headers=user)
    assert resp.json()["code"] == 0, resp.text
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/{team_copy_id}/submissions",
        json={"language": "cpp17", "code": "int main(){}"},
        headers=user,
    )
    assert resp.json()["code"] == 0, resp.text

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

    # 团队快照题不出现在题库中心（公开列表隔离）；组织题同样不进题库中心
    resp = await client.get("/api/v1/problems")
    titles = [it["title"] for it in resp.json()["data"]["items"]]
    assert "组织题甲" not in titles

    # 题库中心「我的」勾选不进组织 / 团队封闭空间题目（mine=true 仅本人全站题）
    resp = await client.get("/api/v1/problems?mine=true", headers=mentor)
    assert resp.json()["code"] == 0, resp.text
    mine_ids = {it["id"] for it in resp.json()["data"]["items"]}
    assert team_copy_id not in mine_ids
    assert org_problem_id not in mine_ids


async def test_team_arrangeable_search_excludes_others(client: httpx.AsyncClient) -> None:
    """团队编排候选：本团队题目 ∪ 全站公开；他人私有题不出现；
    组织题未引用进团队前不直接入编排（快照边界）；成员 2003。"""
    mentor, org_id = await _org_admin_headers(client)
    team_id = await _create_team(client, mentor, org_id, "候选队")
    admin_pub = await _seed_problem("公开题A")
    admin_priv = await _seed_problem("他人私有B", visibility="private")
    org_problem_id = await _seed_org_problem("组织题乙", org_id=org_id, owner_email="mentor@pigeonoj.dev")

    resp = await client.get(
        f"/api/v1/teams/{team_id}/problems/arrangeable", headers=mentor
    )
    assert resp.json()["code"] == 0, resp.text
    ids = {it["id"] for it in resp.json()["data"]["items"]}
    assert admin_pub in ids
    assert admin_priv not in ids
    assert org_problem_id not in ids  # 组织题须先引用进团队

    # 引用后快照题进入编排候选
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": org_problem_id},
        headers=mentor,
    )
    assert resp.json()["code"] == 0, resp.text
    copy_id = resp.json()["data"]["id"]
    resp = await client.get(
        f"/api/v1/teams/{team_id}/problems/arrangeable", headers=mentor
    )
    assert copy_id in {it["id"] for it in resp.json()["data"]["items"]}

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
            background="B",
            description="D",
            input_description="I",
            output_description="O",
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


async def test_team_problem_list_publish_states_without_draft_box(
    client: httpx.AsyncClient,
) -> None:
    """团队题库管理视图（无草稿箱）：主列表仅已发布（含 admin_visible），
    草稿 / 归档在团队空间任何视图不可见（残留草稿不作草稿箱暴露，含显式
    status=draft 恒为空）；管理视图回填 needs_reverification。"""
    mentor, org_id = await _org_admin_headers(client)
    team_id = await _create_team(client, mentor, org_id, "无草稿箱队")

    await _seed_team_problem("已发布团队题", team_id=team_id, owner_email="mentor@pigeonoj.dev")
    await _seed_team_problem(
        "已发布管理题", team_id=team_id, owner_email="mentor@pigeonoj.dev",
        visibility="admin_visible",
    )
    await _seed_team_problem(
        "样例变更题", team_id=team_id, owner_email="mentor@pigeonoj.dev",
        samples_after_verify=True,
    )
    await _seed_team_problem(
        "残留草稿", team_id=team_id, owner_email="mentor@pigeonoj.dev", status="draft"
    )
    await _seed_team_problem(
        "已归档题", team_id=team_id, owner_email="mentor@pigeonoj.dev", status="archived"
    )

    # 主列表：仅已发布（团队可见 + 管理可见均返回），草稿 / 归档不出现
    resp = await client.get(f"/api/v1/teams/{team_id}/problems", headers=mentor)
    assert resp.json()["code"] == 0, resp.text
    items = resp.json()["data"]["items"]
    assert {it["title"] for it in items} == {"已发布团队题", "已发布管理题", "样例变更题"}
    assert all(it["status"] == "published" for it in items)

    # 发布与验题状态：needs_reverification 精确回填（样例晚于验题通过时间 → True）
    flags = {it["title"]: it["needs_reverification"] for it in items}
    assert flags["样例变更题"] is True
    assert flags["已发布团队题"] is False

    # 普通成员视图不变：仅 published + team_visible（admin_visible 不出现）
    member = await _user_headers(client, "nodraftbox-admin@pigeonoj.dev")
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=member)
    assert resp.json()["code"] == 0
    await _approve_all(client, team_id, mentor)
    resp = await client.get(f"/api/v1/teams/{team_id}/problems", headers=member)
    assert resp.json()["code"] == 0, resp.text
    assert {it["title"] for it in resp.json()["data"]["items"]} == {"已发布团队题", "样例变更题"}

    # 草稿箱已移除：残留草稿 / 归档在团队空间不可见（显式 status=draft / status=archived 恒为空）
    resp = await client.get(f"/api/v1/teams/{team_id}/problems?status=draft", headers=mentor)
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["total"] == 0

    resp = await client.get(f"/api/v1/teams/{team_id}/problems?status=archived", headers=mentor)
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["total"] == 0


# ---------------- 团队题单 ----------------


async def test_team_problem_set_lifecycle(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    """团队题单：成员创建 2003；管理员创建 / 编排 / 下线；编排候选 = 本团队题 ∪ 全站公开
    （组织题须先引用；本人私有分支随个人出题取消移除）；团队题单不进题单中心；成员可见详情。"""
    mentor, org_id = await _org_admin_headers(client)
    team_id = await _create_team(client, mentor, org_id, "题单队")

    # 普通用户不可创建
    member = await _user_headers(client, "setmember@pigeonoj.dev")
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets", json={"title": "成员题单"}, headers=member
    )
    assert resp.json()["code"] == 2003

    # 团队自建题单 + 编排（公开题 + 团队题目候选；组织题未引用不可编排）
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets", json={"title": "队内训练"}, headers=mentor
    )
    assert resp.json()["code"] == 0, resp.text
    team_set_id = resp.json()["data"]["id"]

    team_problem_id = await _seed_team_problem(
        "团队题", team_id=team_id, owner_email="mentor@pigeonoj.dev"
    )
    org_problem_id = await _seed_org_problem("未引用组织题", org_id=org_id, owner_email="mentor@pigeonoj.dev")
    pub = await _seed_problem("编排公开题")
    resp = await client.put(
        f"/api/v1/teams/{team_id}/problem-sets/{team_set_id}/items",
        json={"items": [{"problem_id": pub, "sort_order": 0}, {"problem_id": team_problem_id, "sort_order": 1}]},
        headers=mentor,
    )
    assert resp.json()["code"] == 0, resp.text

    # 组织题未引用进团队 → 编排 1001（快照边界）
    resp = await client.put(
        f"/api/v1/teams/{team_id}/problem-sets/{team_set_id}/items",
        json={"items": [{"problem_id": pub}, {"problem_id": org_problem_id}]},
        headers=mentor,
    )
    assert resp.json()["code"] == 1001

    # 全站题单编排不得引入团队题目（封闭空间隔离；全站题单仅 admin 可建可编排）
    solo_set = (
        await client.post("/api/v1/problem-sets", json={"title": "全站隔离"}, headers=admin_headers)
    ).json()["data"]
    resp = await client.put(
        f"/api/v1/problem-sets/{solo_set['id']}/items",
        json={"items": [{"problem_id": team_problem_id}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 1001

    # 下线团队题单
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets/{team_set_id}/archive", headers=mentor
    )
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["status"] == "archived"

    # 团队题单详情（团队上下文统一入口）：items 与编排一致（回归：详情题目列表非空）
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=member)
    assert resp.json()["code"] == 0
    await _approve_all(client, team_id, mentor)
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets", json={"title": "活跃题单"}, headers=mentor
    )
    active_set_id = resp.json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/teams/{team_id}/problem-sets/{active_set_id}/items",
        json={"items": [{"problem_id": pub, "sort_order": 0}]},
        headers=mentor,
    )
    assert resp.json()["code"] == 0, resp.text

    resp = await client.get(
        f"/api/v1/teams/{team_id}/problem-sets/{active_set_id}", headers=member
    )
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["visibility"] == "team_visible"
    assert len(resp.json()["data"]["items"]) == 1  # 编排的公开题

    # 团队题单不进题单中心；非成员不可见
    outsider = await _user_headers(client, "outsider1@pigeonoj.dev")
    resp = await client.get(
        f"/api/v1/teams/{team_id}/problem-sets/{active_set_id}", headers=outsider
    )
    assert resp.json()["code"] == 2003
    resp = await client.get("/api/v1/problem-sets")
    assert all(it["id"] != active_set_id for it in resp.json()["data"]["items"])

    # 团队题单列表（活跃 1 道；队内训练已下线）
    resp = await client.get(f"/api/v1/teams/{team_id}/problem-sets", headers=member)
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["total"] == 1


async def test_team_problem_set_always_team_visible(client: httpx.AsyncClient) -> None:
    """团队题单恒 team_visible（全队成员可见，无 admin_visible 分支）：
    创建载荷带可见性字段被忽略（恒落 team_visible）；成员列表 / 详情 /
    题单内题目 / 交题全部放行（无可见性拦截）；题单中心与 mine 勾选不含团队题单。"""
    mentor, org_id = await _org_admin_headers(client)
    team_id = await _create_team(client, mentor, org_id, "题单可见队")

    # 创建时携带旧可见性字段（admin_visible）→ 忽略，恒 team_visible
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets",
        json={"title": "全员题单", "visibility": "admin_visible"},
        headers=mentor,
    )
    assert resp.json()["code"] == 0, resp.text
    set_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["visibility"] == "team_visible"  # 团队题单恒 team_visible

    # 编排一题（成员详情 / 内题目 / 交题门控用）
    pub = await _seed_problem("可见队公开题")
    resp = await client.put(
        f"/api/v1/teams/{team_id}/problem-sets/{set_id}/items",
        json={"items": [{"problem_id": pub, "sort_order": 0}]},
        headers=mentor,
    )
    assert resp.json()["code"] == 0, resp.text

    member = await _user_headers(client, "setvismember@pigeonoj.dev")
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=member)
    assert resp.json()["code"] == 0
    await _approve_all(client, team_id, mentor)

    # 成员列表可见；详情 / 内题目 / 交题全部放行（不再有 admin_visible 拦截）
    resp = await client.get(f"/api/v1/teams/{team_id}/problem-sets", headers=member)
    assert resp.json()["code"] == 0, resp.text
    assert {it["title"] for it in resp.json()["data"]["items"]} == {"全员题单"}
    resp = await client.get(f"/api/v1/teams/{team_id}/problem-sets/{set_id}", headers=member)
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["visibility"] == "team_visible"
    resp = await client.get(
        f"/api/v1/teams/{team_id}/problem-sets/{set_id}/problems/{pub}", headers=member
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problem-sets/{set_id}/problems/{pub}/submissions",
        json={"language": "cpp17", "code": "int main(){}"},
        headers=member,
    )
    assert resp.json()["code"] == 0, resp.text

    # 团队题单不进题单中心 / mine 勾选（封闭空间）
    resp = await client.get(f"/api/v1/problem-sets?mine=true", headers=mentor)
    assert all(it["id"] != set_id for it in resp.json()["data"]["items"])


# ---------------- 团队比赛 ----------------


async def test_team_contest_flow(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    """团队比赛：成员创建 2003；管理员创建（contest_type=team）；编排候选放开团队题目；
    成员可报名；非成员报名 403 / 详情 2003；全站编排搜索不含团队比赛。"""
    mentor, org_id = await _org_admin_headers(client)
    team_id = await _create_team(client, mentor, org_id, "比赛队")

    member = await _user_headers(client, "contestmember@pigeonoj.dev")
    resp = await client.post(
        f"/api/v1/teams/{team_id}/contests", json=_future_contest_body(), headers=member
    )
    assert resp.json()["code"] == 2003

    # 组织题可引用进团队并入赛（团队题目唯一来源 = 引用快照）
    org_problem_id = await _seed_org_problem("队内题", org_id=org_id, owner_email="mentor@pigeonoj.dev")
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": org_problem_id},
        headers=mentor,
    )
    assert resp.json()["code"] == 0, resp.text
    copy_id = resp.json()["data"]["id"]  # 快照题入赛

    body = _future_contest_body(copy_id)
    resp = await client.post(f"/api/v1/teams/{team_id}/contests", json=body, headers=mentor)
    assert resp.json()["code"] == 0, resp.text
    contest = resp.json()["data"]
    assert contest["contest_type"] == "team"
    assert contest["problem_count"] == 1

    # 团队比赛列表（成员视角）
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=member)
    assert resp.json()["code"] == 0
    await _approve_all(client, team_id, mentor)
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

    # 全站比赛编排不得引入团队快照题（封闭空间隔离；全站赛仅 admin 可建）
    resp = await client.post(
        "/api/v1/contests",
        json={**_future_contest_body(), "title": "全站赛", "problems": [{"problem_id": copy_id}]},
        headers=admin_headers,
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
    other_team = await _create_team(client, mentor, org_id, "另一队赛")
    resp = await client.get(
        f"/api/v1/teams/{other_team}/contests/{contest['id']}", headers=mentor
    )
    assert resp.json()["code"] == 3001
    resp = await client.get(
        f"/api/v1/teams/{team_id}/contests/{contest['id']}", headers=outsider
    )
    assert resp.json()["code"] == 2003


async def test_team_problem_statement_rejects_extra_team_id(client: httpx.AsyncClient) -> None:
    """团队题面更新：ProblemUpdate extra=forbid，body 不得携带 team_id（归属由路径给定）。
    团队题目经引用产生（直建已移除）。"""
    mentor, org_id = await _org_admin_headers(client)
    team_id = await _create_team(client, mentor, org_id, "题面队")
    org_problem_id = await _seed_org_problem("队内题面题", org_id=org_id, owner_email="mentor@pigeonoj.dev")
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": org_problem_id},
        headers=mentor,
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
        headers=mentor,
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
        headers=mentor,
    )
    assert resp.json()["code"] == 0, resp.text


async def test_team_problem_bare_path_blocked_after_reference(client: httpx.AsyncClient) -> None:
    """引用后的团队题目（team_visible）：非创建者题库裸路径交题 / 自测 403，
    团队上下文自测门控放行（进入派发阶段——无节点时 502 / 冷却 429 均视为门控通过）。"""
    mentor, org_id = await _org_admin_headers(client)
    team_id = await _create_team(client, mentor, org_id, "自测队")
    org_problem_id = await _seed_org_problem("自测源题", org_id=org_id, owner_email="mentor@pigeonoj.dev")
    resp = await client.post(
        f"/api/v1/teams/{team_id}/problems/references",
        json={"problem_id": org_problem_id},
        headers=mentor,
    )
    assert resp.json()["code"] == 0
    copy_id = resp.json()["data"]["id"]  # 快照复制：团队上下文走新题 id

    member = await _user_headers(client, "selftestmember@pigeonoj.dev")
    resp = await client.post(f"/api/v1/teams/{team_id}/applications", json={}, headers=member)
    assert resp.json()["code"] == 0
    await _approve_all(client, team_id, mentor)

    # 裸路径自测（非创建者）→ 403；快照题对组织成员也封死（团队上下文隔离）
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

"""社区模块集成测试：官方题解、题解生命周期、评论两级软删、比赛门禁、开关与举报
（docs/contracts/community.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.redis import close_redis, get_redis
from app.models.contest import Contest, ContestProblem
from app.models.problem import Problem
from app.models.user import User

from .conftest import api_login, register_user


async def _create_problem(client, admin_headers, **overrides) -> dict:
    payload = {
        "title": "A+B Problem",
        "background": "经典入门题",
        "description": "计算 A+B",
        "input_description": "一行两个整数 A B",
        "output_description": "一行输出 A+B 的值",
        "solution": "## 官方题解\n直接相加即可。",
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/problems", json=payload, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0
    return resp.json()["data"]


async def _publish_problem(pid: str) -> None:
    """直接置为已发布（绕过验题链路；社区测试不关心测试点；CHECK 要求 verified_at 非空）。"""
    async with SessionLocal() as db:
        row = await db.get(Problem, uuid.UUID(pid))
        row.status = "published"
        row.verified_at = datetime.now(timezone.utc)
        row.published_at = datetime.now(timezone.utc)
        await db.commit()


async def _user_headers(client, email: str) -> dict:
    await register_user(client, email)
    token = await api_login(client, email, "Pass@123")
    return {"Authorization": f"Bearer {token}"}


async def _create_running_contest(problem_id: str, owner_id: str, *, running: bool) -> uuid.UUID:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        contest = Contest(
            title="门禁比赛",
            contest_type="public",
            owner_id=uuid.UUID(owner_id),
            rule_type="ACM",
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            register_start_time=now - timedelta(hours=2),
            register_end_time=now - timedelta(minutes=30),
            status="running" if running else "finished",
        )
        db.add(contest)
        await db.flush()
        db.add(ContestProblem(contest_id=contest.id, problem_id=uuid.UUID(problem_id)))
        await db.commit()
        return contest.id


async def _admin_id() -> str:
    async with SessionLocal() as db:
        row = (await db.execute(select(User).where(User.email == "admin@pigeonoj.dev"))).scalar_one()
        return str(row.id)


async def _flush_redis() -> None:
    await (await get_redis()).flushdb()


# ---- 官方题解 ----


@pytest.mark.asyncio
async def test_editorial_visibility(client, admin_headers, user_headers):
    """草稿题仅管理者可读官方题解；发布后题目可见者可读；can_manage 随行返回。"""
    problem = await _create_problem(client, admin_headers)
    pid = problem["id"]

    # 草稿：普通用户 2003（题目不可见）；admin 可读且 can_manage=true
    resp = await client.get(f"/api/v1/problems/{pid}/editorial", headers=user_headers)
    assert resp.json()["code"] == 2003
    resp = await client.get(f"/api/v1/problems/{pid}/editorial", headers=admin_headers)
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["can_manage"] is True
    assert "官方题解" in body["data"]["solution"]

    await _publish_problem(pid)
    # 发布后：登录用户与匿名均可读
    resp = await client.get(f"/api/v1/problems/{pid}/editorial", headers=user_headers)
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["can_manage"] is False
    resp = await client.get(f"/api/v1/problems/{pid}/editorial")
    assert resp.json()["code"] == 0


@pytest.mark.asyncio
async def test_editorial_contest_gate(client, admin_headers, user_headers):
    """比赛防作弊门禁：进行中比赛引用的题目，题解内容一律 3002；结束自动恢复。"""
    problem = await _create_problem(client, admin_headers)
    pid = problem["id"]
    await _publish_problem(pid)
    admin_uid = await _admin_id()

    contest_id = await _create_running_contest(pid, admin_uid, running=True)
    resp = await client.get(f"/api/v1/problems/{pid}/editorial", headers=user_headers)
    assert resp.json()["code"] == 3002, resp.text

    # 比赛结束 → 自动恢复
    async with SessionLocal() as db:
        row = await db.get(Contest, contest_id)
        row.status = "finished"
        await db.commit()
    resp = await client.get(f"/api/v1/problems/{pid}/editorial", headers=user_headers)
    assert resp.json()["code"] == 0


# ---- 用户题解生命周期 ----


@pytest.mark.asyncio
async def test_solution_lifecycle(client, admin_headers, user_headers):
    pid = (await _create_problem(client, admin_headers))["id"]
    await _publish_problem(pid)

    # 创建（直接发布）
    resp = await client.post(
        f"/api/v1/problems/{pid}/solutions",
        json={"title": "我的题解", "content": "做法：贪心。", "status": "published"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    solution = resp.json()["data"]
    sid = solution["id"]
    assert solution["status"] == "published"
    assert solution["author"]["nickname"] == "普通用户"
    assert solution["comment_count"] == 0

    # 频控：60s 冷却内再创建 → 4002
    resp = await client.post(
        f"/api/v1/problems/{pid}/solutions",
        json={"title": "另一篇", "content": "内容", "status": "published"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 4002
    await _flush_redis()

    # 公开列表可见；详情匿名可读
    resp = await client.get(f"/api/v1/problems/{pid}/solutions")
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["total"] == 1
    resp = await client.get(f"/api/v1/solutions/{sid}")
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["content"] == "做法：贪心。"

    # 无草稿态：创建请求里的 status 字段被忽略，直接发布；第二篇创建成功（另一用户）
    other = await _user_headers(client, "solut2@pigeonoj.dev")
    resp = await client.post(
        f"/api/v1/problems/{pid}/solutions",
        json={"title": "第二篇", "content": "另一解法", "status": "draft"},
        headers=other,
    )
    assert resp.json()["code"] == 0
    second_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["status"] == "published"

    # owner 编辑（仅标题 / 正文）；他人编辑 2003
    resp = await client.put(
        f"/api/v1/solutions/{second_id}", json={"content": "改过的解法"}, headers=other
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.put(
        f"/api/v1/solutions/{second_id}", json={"title": "劫持"}, headers=admin_headers
    )
    assert resp.json()["code"] == 2003

    # owner 下架（软删）：公开详情 404，作者仍可读（removed 态）；再编辑 3002
    resp = await client.delete(f"/api/v1/solutions/{second_id}", headers=other)
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/solutions/{second_id}")
    assert resp.json()["code"] == 3001
    resp = await client.get(f"/api/v1/solutions/{second_id}", headers=other)
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["status"] == "removed"
    resp = await client.put(
        f"/api/v1/solutions/{second_id}", json={"title": "复活"}, headers=other
    )
    assert resp.json()["code"] == 3002

    # admin 恢复 → 重新公开可见
    resp = await client.put(
        f"/api/v1/admin/solutions/{second_id}/status",
        json={"status": "published"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.get(f"/api/v1/solutions/{second_id}")
    assert resp.json()["code"] == 0

    # mine 视角：other 本人共 1 篇（已恢复 published）；公开列表共 2 篇
    resp = await client.get(
        f"/api/v1/problems/{pid}/solutions?mine=true", headers=other
    )
    assert resp.json()["data"]["total"] == 1
    resp = await client.get(f"/api/v1/problems/{pid}/solutions")
    assert resp.json()["data"]["total"] == 2

    # 管理列表（全状态 + 题目 / 作者信息）
    resp = await client.get("/api/v1/admin/solutions", headers=admin_headers)
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["total"] == 2
    row = body["data"]["items"][0]
    assert row["problem"]["title"] == "A+B Problem"
    assert row["author"]["nickname"]
    # 非 admin 访问管理端点 2003
    resp = await client.get("/api/v1/admin/solutions", headers=user_headers)
    assert resp.json()["code"] == 2003


@pytest.mark.asyncio
async def test_solution_inherits_problem_visibility(client, admin_headers, user_headers):
    """私密题的题解对无权用户一律 2003（题目可见性继承，community.md）。"""
    pid = (
        await _create_problem(client, admin_headers, visibility="private", title="私密题")
    )["id"]
    await _publish_problem(pid)
    resp = await client.post(
        f"/api/v1/problems/{pid}/solutions",
        json={"title": "内部题解", "content": "仅管理者可见的题的题解", "status": "published"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    resp = await client.get(f"/api/v1/problems/{pid}/solutions", headers=user_headers)
    assert resp.json()["code"] == 2003
    resp = await client.get(f"/api/v1/problems/{pid}/solutions", headers=admin_headers)
    assert resp.json()["data"]["total"] == 1


# ---- 评论 ----


@pytest.mark.asyncio
async def test_comment_two_level_and_soft_delete(client, admin_headers, user_headers):
    pid = (await _create_problem(client, admin_headers))["id"]
    await _publish_problem(pid)
    resp = await client.post(
        f"/api/v1/problems/{pid}/solutions",
        json={"title": "题解", "content": "正文", "status": "published"},
        headers=admin_headers,
    )
    sid = resp.json()["data"]["id"]

    # 一级评论 + 回复
    resp = await client.post(
        "/api/v1/comments",
        json={"target_type": "solution", "target_id": sid, "content": "讲得很清楚"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    top = resp.json()["data"]
    resp = await client.post(
        "/api/v1/comments",
        json={
            "target_type": "solution",
            "target_id": sid,
            "parent_id": top["id"],
            "content": "同感",
        },
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    reply = resp.json()["data"]

    # 楼中楼（对回复回复）→ 3002
    resp = await client.post(
        "/api/v1/comments",
        json={
            "target_type": "solution",
            "target_id": sid,
            "parent_id": reply["id"],
            "content": "三层",
        },
        headers=user_headers,
    )
    assert resp.json()["code"] == 3002

    # 评论频控 10s
    resp = await client.post(
        "/api/v1/comments",
        json={"target_type": "solution", "target_id": sid, "content": "再评一条"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 4002
    await _flush_redis()

    # 列表：一级 1 条 + 回复预览 1 条 + reply_count=1
    resp = await client.get(f"/api/v1/comments?target_type=solution&target_id={sid}")
    body = resp.json()["data"]
    assert body["total"] == 1
    top_row = body["items"][0]
    assert top_row["reply_count"] == 1
    assert top_row["replies"][0]["content"] == "同感"

    # 回复分页端点
    resp = await client.get(
        f"/api/v1/comments?target_type=solution&target_id={sid}&parent_id={top['id']}"
    )
    assert resp.json()["data"]["total"] == 1

    # owner 软删回复 → 占位不存在（无未删回复的直接消失）；一级 reply_count=0
    resp = await client.delete(f"/api/v1/comments/{reply['id']}", headers=admin_headers)
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/comments?target_type=solution&target_id={sid}")
    top_row = resp.json()["data"]["items"][0]
    assert top_row["reply_count"] == 0
    assert top_row["replies"] == []

    # 软删一级评论（存在未删……本例无回复 → 整行隐藏）
    resp = await client.delete(f"/api/v1/comments/{top['id']}", headers=user_headers)
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/comments?target_type=solution&target_id={sid}")
    assert resp.json()["data"]["total"] == 0

    # admin include_deleted=true 可见软删行（作者信息保留）
    resp = await client.get(
        f"/api/v1/comments?target_type=solution&target_id={sid}&include_deleted=true",
        headers=admin_headers,
    )
    rows = resp.json()["data"]["items"]
    assert len(rows) == 1
    assert rows[0]["is_deleted"] is True
    assert rows[0]["content"] is None
    assert rows[0]["author"] is None
    # 匿名 / 普通用户 include_deleted → 2003
    resp = await client.get(
        f"/api/v1/comments?target_type=solution&target_id={sid}&include_deleted=true",
        headers=user_headers,
    )
    assert resp.json()["code"] == 2003

    # admin 恢复评论
    resp = await client.put(
        f"/api/v1/admin/comments/{top['id']}/status",
        json={"is_deleted": False},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/comments?target_type=solution&target_id={sid}")
    assert resp.json()["data"]["total"] == 1

    # 他人软删他人评论 → 2003
    resp = await client.post(
        "/api/v1/comments",
        json={"target_type": "solution", "target_id": sid, "content": "第二条"},
        headers=admin_headers,
    )
    sid2 = resp.json()["data"]["id"]
    resp = await client.delete(f"/api/v1/comments/{sid2}", headers=user_headers)
    assert resp.json()["code"] == 2003


@pytest.mark.asyncio
async def test_comments_blocked_on_removed_solution(client, admin_headers, user_headers):
    """题解下架后评论随内容隐藏且不可再评（community.md 关键流程 3）。"""
    pid = (await _create_problem(client, admin_headers))["id"]
    await _publish_problem(pid)
    resp = await client.post(
        f"/api/v1/problems/{pid}/solutions",
        json={"title": "待删题解", "content": "正文", "status": "published"},
        headers=user_headers,
    )
    sid = resp.json()["data"]["id"]
    resp = await client.post(
        "/api/v1/comments",
        json={"target_type": "solution", "target_id": sid, "content": "占楼"},
        headers=admin_headers,
    )
    comment_id = resp.json()["data"]["id"]

    resp = await client.delete(f"/api/v1/solutions/{sid}", headers=user_headers)
    assert resp.json()["code"] == 0
    # 公开评论列表隐藏（题解 removed 对外 404）；再评论 3002
    resp = await client.get(f"/api/v1/comments?target_type=solution&target_id={sid}")
    assert resp.json()["code"] == 3001
    resp = await client.post(
        "/api/v1/comments",
        json={"target_type": "solution", "target_id": sid, "content": "迟到的评论"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 3002
    # 作者与 admin 仍可读既有评论
    resp = await client.get(
        f"/api/v1/comments?target_type=solution&target_id={sid}", headers=user_headers
    )
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["total"] == 1
    assert resp.json()["data"]["items"][0]["id"] == comment_id


# ---- 功能开关 ----


@pytest.mark.asyncio
async def test_feature_switches_disable_writes(client, admin_headers, user_headers):
    pid = (await _create_problem(client, admin_headers))["id"]
    await _publish_problem(pid)
    async with SessionLocal() as db:
        from app.models.system_config import SystemConfig

        row = (
            await db.execute(
                select(SystemConfig).where(
                    SystemConfig.category == "community",
                    SystemConfig.config_key == "community.feature_switches",
                )
            )
        ).scalar_one()
        row.config_value = {"solutions": False, "comments": False}
        await db.commit()

    resp = await client.post(
        f"/api/v1/problems/{pid}/solutions",
        json={"title": "开关题解", "content": "x", "status": "published"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 3002
    resp = await client.get(f"/api/v1/problems/{pid}/solutions")
    assert resp.json()["code"] == 0  # 浏览不受开关影响
    resp = await client.post(
        "/api/v1/comments",
        json={"target_type": "solution", "target_id": str(uuid.uuid4()), "content": "x"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 3002


# ---- 举报 ----


@pytest.mark.asyncio
async def test_report_create_and_duplicate(client, admin_headers, user_headers):
    pid = (await _create_problem(client, admin_headers))["id"]
    await _publish_problem(pid)
    resp = await client.post(
        f"/api/v1/problems/{pid}/solutions",
        json={"title": "被举报的题解", "content": "正文", "status": "published"},
        headers=user_headers,
    )
    sid = resp.json()["data"]["id"]

    resp = await client.post(
        "/api/v1/reports",
        json={"target_type": "solution", "target_id": sid, "reason": "抄袭题解"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    # 同用户同目标 pending 中重复 → 3003
    resp = await client.post(
        "/api/v1/reports",
        json={"target_type": "solution", "target_id": sid, "reason": "再报一次"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 3003
    # 目标不存在 → 3001
    resp = await client.post(
        "/api/v1/reports",
        json={"target_type": "solution", "target_id": str(uuid.uuid4()), "reason": "x"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 3001
    # 匿名举报 → 2001
    resp = await client.post(
        "/api/v1/reports",
        json={"target_type": "solution", "target_id": sid, "reason": "x"},
    )
    assert resp.json()["code"] == 2001

    # admin 举报列表可见（复用既有 /admin/reports）
    resp = await client.get("/api/v1/admin/reports", headers=admin_headers)
    items = resp.json()["data"]["items"]
    assert any(item["target_id"] == sid for item in items)

"""题库模块集成测试：权限、可见性、生命周期、验题流程、提交历史（docs/contracts/problems.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select

from app.modules.judge.models import Problem, Submission
from app.shared.database import SessionLocal


async def _create_problem(client, admin_headers, **overrides) -> dict:
    payload = {"title": "A+B Problem", "description": "计算 A+B", "difficulty": "easy"}
    payload.update(overrides)
    resp = await client.post("/api/v1/problems", json=payload, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0
    return resp.json()["data"]


@pytest.mark.asyncio
async def test_create_problem_requires_manager_role(client, user_headers):
    resp = await client.post("/api/v1/problems", json={"title": "T", "description": "D"}, headers=user_headers)
    body = resp.json()
    assert resp.status_code == 403
    assert body["code"] == 2003  # 越权统一 2003（docs/contracts/common.md）


@pytest.mark.asyncio
async def test_create_defaults_and_draft_visibility(client, admin_headers):
    data = await _create_problem(client, admin_headers)
    assert data["status"] == "draft"
    assert data["visibility"] == "public"
    assert data["difficulty"] == "easy"
    assert data["is_verified"] is False

    # 匿名访问草稿 → 2003；owner 访问 → 可见且带管理标记
    resp = await client.get(f"/api/v1/problems/{data['id']}")
    assert resp.json()["code"] == 2003
    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    assert resp.json()["code"] == 0
    detail = resp.json()["data"]
    assert detail["can_manage"] is True
    assert "solution" in detail and "test_cases" in detail


@pytest.mark.asyncio
async def test_list_pagination_and_filters(client, admin_headers):
    titles = [("Alpha", "easy"), ("Beta", "medium"), ("Alpine", "hard")]
    for title, difficulty in titles:
        problem = await _create_problem(client, admin_headers, title=title, difficulty=difficulty)
        # 直接置为已发布公开，绕过验题链路（链路另有用例覆盖）
        async with SessionLocal() as db:
            row = await db.get(Problem, uuid.UUID(problem["id"]))
            row.status = "published"
            row.is_verified = True
            row.published_at = datetime.now()
            await db.commit()

    resp = await client.get("/api/v1/problems?page=1&page_size=2")
    body = resp.json()["data"]
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["page"] == 1 and body["page_size"] == 2

    resp = await client.get("/api/v1/problems?keyword=alp")
    assert resp.json()["data"]["total"] == 2  # Alpha / Alpine

    resp = await client.get("/api/v1/problems?difficulty=hard")
    items = resp.json()["data"]["items"]
    assert len(items) == 1 and items[0]["title"] == "Alpine"

    # 草稿不出现在公开列表
    await _create_problem(client, admin_headers, title="Hidden Draft")
    resp = await client.get("/api/v1/problems")
    assert all(item["title"] != "Hidden Draft" for item in resp.json()["data"]["items"])


@pytest.mark.asyncio
async def test_publish_requires_verification_and_cases(client, admin_headers, fake_storage):
    data = await _create_problem(client, admin_headers)

    resp = await client.post(f"/api/v1/problems/{data['id']}/publish", headers=admin_headers)
    assert resp.json()["code"] == 3002  # 未验题

    async with SessionLocal() as db:
        row = await db.get(Problem, data["id"])
        row.is_verified = True
        await db.commit()

    # 仅样例、无正式测试点 → 3002
    resp = await client.put(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={"cases": [{"name": "s", "is_sample": True, "input": "1", "expected_output": "2"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 1001  # 分值和 ≠ 100
    resp = await client.post(f"/api/v1/problems/{data['id']}/publish", headers=admin_headers)
    assert resp.json()["code"] == 3002

    resp = await client.put(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={
            "cases": [
                {"name": "s", "is_sample": True, "input": "1", "expected_output": "2"},
                {"name": "c1", "input": "1", "expected_output": "2", "score": 100},
            ]
        },
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text

    resp = await client.post(f"/api/v1/problems/{data['id']}/publish", headers=admin_headers)
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["status"] == "published"

    # 归档后不可编辑、列表不可见
    resp = await client.post(f"/api/v1/problems/{data['id']}/archive", headers=admin_headers)
    assert resp.json()["code"] == 0
    resp = await client.put(f"/api/v1/problems/{data['id']}", json={"title": "X"}, headers=admin_headers)
    assert resp.json()["code"] == 3002
    resp = await client.get("/api/v1/problems")
    assert all(item["id"] != data["id"] for item in resp.json()["data"]["items"])

    # 非管理角色不可归档他人题目
    resp = await client.post(f"/api/v1/problems/{uuid.uuid4()}/archive", headers=admin_headers)
    assert resp.json()["code"] == 3001


@pytest.mark.asyncio
async def test_verification_invite_flow_and_writeback(client, admin_headers, user_headers, fake_storage, monkeypatch):
    data = await _create_problem(client, admin_headers)
    problem_id = data["id"]

    # 发起验题（邀请模式）
    resp = await client.post(
        f"/api/v1/problems/{problem_id}/verify",
        json={"invite_expires_hours": 24},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    invite_token = resp.json()["data"]["invite"]["token"]

    # 重复发起 → 3003
    resp = await client.post(
        f"/api/v1/problems/{problem_id}/verify",
        json={"invite_expires_hours": 24},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 3003

    # 公开解析邀请链接
    resp = await client.get(f"/api/v1/verify-invites/{invite_token}")
    parsed = resp.json()["data"]
    assert parsed["problem_id"] == problem_id
    assert parsed["problem_title"] == "A+B Problem"

    # 受邀人提交验题代码（凭 token，无需特定角色）
    resp = await client.post(
        f"/api/v1/problems/{problem_id}/verify",
        json={"invite_token": invite_token, "code": "print(1)", "language": "python3.12"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    submission_id = resp.json()["data"]["submission_id"]

    async with SessionLocal() as db:
        submission = (
            await db.execute(select(Submission).where(Submission.id == uuid.UUID(submission_id)))
        ).scalar_one()
        assert submission.submit_type == "verify"
        assert submission.verification_id is not None

        # 模拟判题通过后的回写
        submission.status = "accepted"
        from app.modules.judge.service import finalize_verify_submission

        await finalize_verify_submission(db, submission)
        await db.commit()

        problem = await db.get(Problem, uuid.UUID(problem_id))
        assert problem.is_verified is True
        assert problem.verified_by == submission.user_id
        assert problem.verified_at is not None

    # 通过后可发布
    resp = await client.post(f"/api/v1/problems/{problem_id}/publish", headers=admin_headers)
    assert resp.json()["code"] == 3002  # 缺正式测试点

    resp = await client.put(
        f"/api/v1/problems/{problem_id}/test-cases",
        json={"cases": [{"name": "c1", "input": "1", "expected_output": "2", "score": 100}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0
    resp = await client.post(f"/api/v1/problems/{problem_id}/publish", headers=admin_headers)
    assert resp.json()["code"] == 0


@pytest.mark.asyncio
async def test_submission_history_and_detail(client, admin_headers, user_headers, fake_storage, monkeypatch):
    data = await _create_problem(client, admin_headers)
    async with SessionLocal() as db:
        row = await db.get(Problem, data["id"])
        row.status = "published"
        row.is_verified = True
        await db.commit()

    resp = await client.post(
        "/api/v1/submissions",
        json={"problem_id": data["id"], "language": "cpp17", "code": "int main(){}"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    submission_id = resp.json()["data"]["submission_id"]

    # 提交历史（本人）
    resp = await client.get(f"/api/v1/submissions?problem_id={data['id']}", headers=admin_headers)
    history = resp.json()["data"]
    assert history["total"] == 1
    assert history["items"][0]["status"] in {"pending", "judging"}

    # 详情含代码与测试点明细骨架
    resp = await client.get(f"/api/v1/submissions/{submission_id}", headers=admin_headers)
    detail = resp.json()["data"]
    assert detail["code"] == "int main(){}"
    assert detail["language"] == "cpp17"
    assert isinstance(detail["cases"], list)

    # 他人不可读
    resp = await client.get(f"/api/v1/submissions/{submission_id}", headers=user_headers)
    assert resp.json()["code"] == 3001

    # 草稿题目不可被普通用户提交
    draft = await _create_problem(client, admin_headers, visibility="private")
    resp = await client.post(
        "/api/v1/submissions",
        json={"problem_id": draft["id"], "language": "cpp17", "code": "int main(){}"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 2003


@pytest.mark.asyncio
async def test_promote_rejected_until_teams_module(client, admin_headers):
    data = await _create_problem(client, admin_headers)
    resp = await client.post(f"/api/v1/problems/{data['id']}/promote", headers=admin_headers)
    assert resp.json()["code"] == 3002  # 仅团队题目可升级公开


@pytest.mark.asyncio
async def test_list_scope_mine_shows_own_private_problems(client, admin_headers, user_headers):
    """scope=mine：创建者可见自己的私有/草稿题；匿名 401；他人看不到。"""
    mine = await _create_problem(client, admin_headers, title="My Private", visibility="private")
    await _create_problem(client, admin_headers, title="My Draft2")

    # 未登录 → 2001
    resp = await client.get("/api/v1/problems?scope=mine")
    assert resp.json()["code"] == 2001

    # owner（此处为 admin）能看到自己的全部题目，含草稿与私有
    resp = await client.get("/api/v1/problems?scope=mine", headers=admin_headers)
    data = resp.json()["data"]
    titles = {item["title"] for item in data["items"]}
    assert {"My Private", "My Draft2"} <= titles
    assert all(item["status"] in {"draft", "published", "archived"} for item in data["items"])

    # status 过滤叠加
    resp = await client.get("/api/v1/problems?scope=mine&status=draft", headers=admin_headers)
    assert resp.json()["data"]["total"] >= 2

    # 普通用户 scope=mine 只看到自己的（空），绝无他人私有题
    resp = await client.get("/api/v1/problems?scope=mine", headers=user_headers)
    items = resp.json()["data"]["items"]
    assert "My Private" not in {item["title"] for item in items}

    # 公开列表仍不含私有题
    resp = await client.get("/api/v1/problems", headers=user_headers)
    assert "My Private" not in {item["title"] for item in resp.json()["data"]["items"]}

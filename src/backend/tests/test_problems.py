"""题库模块集成测试：权限、可见性、生命周期、验题流程、提交历史（docs/contracts/problems.md）。"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select, text

from app.models.judge import Submission, SubmissionTestCaseResult
from app.models.problem import Problem, TestCase
from app.models.user import User
from app.core.database import SessionLocal


async def _create_problem(client, admin_headers, **overrides) -> dict:
    payload = {
        "title": "A+B Problem",
        "background": "经典入门题",
        "description": "计算 A+B",
        "input_description": "一行两个整数 A B",
        "output_description": "一行输出 A+B 的值",
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/problems", json=payload, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0
    return resp.json()["data"]


async def _pass_verification(pid: str) -> None:
    """模拟验题通过：仅打「已验待生效」标记（不晋升；晋升走 apply 端点）。"""
    async with SessionLocal() as db:
        await db.execute(
            text(
                "UPDATE problems SET pending_verified = true, case_status = 'verified', "
                "verified_at = now() WHERE id = :pid"
            ),
            {"pid": pid},
        )
        await db.commit()


async def _apply_pending(client, admin_headers, pid: str) -> None:
    """显式生效暂存集（POST /test-cases/apply）。"""
    resp = await client.post(
        f"/api/v1/problems/{pid}/test-cases/apply", headers=admin_headers
    )
    assert resp.json()["code"] == 0, resp.text


@pytest.mark.asyncio
async def test_create_problem_requires_manager_role(client, user_headers):
    resp = await client.post(
        "/api/v1/problems",
        json={
            "title": "T",
            "background": "B",
            "description": "D",
            "input_description": "I",
            "output_description": "O",
        },
        headers=user_headers,
    )
    body = resp.json()
    assert resp.status_code == 403
    assert body["code"] == 2003  # 越权统一 2003（docs/contracts/common.md）


@pytest.mark.asyncio
async def test_create_defaults_and_draft_visibility(client, admin_headers):
    data = await _create_problem(client, admin_headers)
    assert data["status"] == "draft"
    assert data["visibility"] == "public"
    assert data["is_verified"] is False

    # 匿名访问草稿 → 2003；owner 访问 → 可见且带管理标记
    resp = await client.get(f"/api/v1/problems/{data['id']}")
    assert resp.json()["code"] == 2003
    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    assert resp.json()["code"] == 0
    detail = resp.json()["data"]
    assert detail["can_manage"] is True
    assert detail["background"] == "经典入门题"
    assert "solution" in detail and "test_cases" in detail


@pytest.mark.asyncio
async def test_update_background_roundtrip(client, admin_headers):
    data = await _create_problem(client, admin_headers)

    resp = await client.put(
        f"/api/v1/problems/{data['id']}",
        json={"background": "新的题目背景"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text

    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    assert resp.json()["data"]["background"] == "新的题目背景"


@pytest.mark.asyncio
async def test_validation_failures_use_unified_envelope(client, admin_headers):
    """Query / Body 校验失败（FastAPI 422）统一转 1001 信封（docs/contracts/common.md）。"""
    resp = await client.get("/api/v1/problems?page=0")
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 1001
    assert set(body) >= {"code", "message", "data"}

    resp = await client.get("/api/v1/problems?page_size=101")
    assert resp.json()["code"] == 1001

    resp = await client.post("/api/v1/problems", json={"title": "No Description"}, headers=admin_headers)
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001

    resp = await client.post(
        "/api/v1/problems",
        json={
            "title": "No Background",
            "description": "D",
            "input_description": "I",
            "output_description": "O",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001


@pytest.mark.asyncio
async def test_list_pagination_and_filters(client, admin_headers):
    for title in ("Alpha", "Beta", "Alpine"):
        problem = await _create_problem(client, admin_headers, title=title)
        # 直接置为已发布公开，绕过验题链路（链路另有用例覆盖）
        async with SessionLocal() as db:
            row = await db.get(Problem, uuid.UUID(problem["id"]))
            row.status = "published"
            row.verified_at = datetime.now()
            row.published_at = datetime.now()
            await db.commit()

    resp = await client.get("/api/v1/problems?page=1&page_size=2")
    body = resp.json()["data"]
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["page"] == 1 and body["page_size"] == 2

    resp = await client.get("/api/v1/problems?keyword=alp")
    assert resp.json()["data"]["total"] == 2  # Alpha / Alpine

    # 草稿不出现在公开列表
    await _create_problem(client, admin_headers, title="Hidden Draft")
    resp = await client.get("/api/v1/problems")
    assert all(item["title"] != "Hidden Draft" for item in resp.json()["data"]["items"])


@pytest.mark.asyncio
async def test_publish_blocked_when_cases_changed_after_verification(client, admin_headers, fake_storage):
    data = await _create_problem(client, admin_headers)
    pid = data["id"]
    cases_url = f"/api/v1/problems/{pid}/test-cases"

    resp = await client.put(
        cases_url,
        json={"cases": [{"name": "c1", "input": "1", "expected_output": "2"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text

    # 模拟验题通过并显式生效：此后数据未再变更 → 无需重验
    await _pass_verification(pid)
    await _apply_pending(client, admin_headers, pid)
    resp = await client.get(f"/api/v1/problems/{pid}", headers=admin_headers)
    assert resp.json()["data"]["needs_reverification"] is False

    # 再次编辑测试点：写入暂存集 → 必须重新验题，发布被阻断（生效集不受影响）
    resp = await client.put(
        cases_url,
        json={"cases": [{"name": "c2", "input": "3", "expected_output": "4"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text

    resp = await client.get(f"/api/v1/problems/{pid}", headers=admin_headers)
    assert resp.json()["data"]["needs_reverification"] is True

    resp = await client.post(f"/api/v1/problems/{pid}/publish", headers=admin_headers)
    body = resp.json()
    assert body["code"] == 3002, body
    assert "重新验题" in body["message"]


@pytest.mark.asyncio
async def test_publish_requires_verification_and_cases(client, admin_headers, fake_storage):
    data = await _create_problem(client, admin_headers)

    resp = await client.post(f"/api/v1/problems/{data['id']}/publish", headers=admin_headers)
    assert resp.json()["code"] == 3002  # 未验题

    async with SessionLocal() as db:
        row = await db.get(Problem, data["id"])
        row.verified_at = datetime.now()  # 模拟曾经验题通过
        await db.commit()

    # 无任何测试点 → 3002（发布须至少 1 个生效测试点）
    resp = await client.post(f"/api/v1/problems/{data['id']}/publish", headers=admin_headers)
    assert resp.json()["code"] == 3002

    resp = await client.put(
        f"/api/v1/problems/{data['id']}/samples",
        json={"samples": [{"input": "1", "output": "2"}, {"input": "3", "output": "4"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0
    assert fake_storage.puts == []  # 样例只落库展示，不进对象存储（docs/contracts/problems.md）

    # 仅样例仍不算正式测试点
    resp = await client.post(f"/api/v1/problems/{data['id']}/publish", headers=admin_headers)
    assert resp.json()["code"] == 3002

    resp = await client.put(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={"cases": [{"name": "c1", "input": "1", "expected_output": "2"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text

    # 暂存集须先经验题通过并显式生效才能发布
    await _pass_verification(data["id"])
    await _apply_pending(client, admin_headers, data["id"])
    resp = await client.post(f"/api/v1/problems/{data['id']}/publish", headers=admin_headers)
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["status"] == "published"

    # 归档后不可编辑、不可重写测试点、列表不可见
    resp = await client.post(f"/api/v1/problems/{data['id']}/archive", headers=admin_headers)
    assert resp.json()["code"] == 0
    resp = await client.put(f"/api/v1/problems/{data['id']}", json={"title": "X"}, headers=admin_headers)
    assert resp.json()["code"] == 3002
    resp = await client.put(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={"cases": [{"name": "c", "input": "1", "expected_output": "2"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 3002  # 归档后编辑统一 3002（docs/contracts/problems.md 错误码）
    resp = await client.put(
        f"/api/v1/problems/{data['id']}/samples",
        json={"samples": []},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 3002  # 归档题目同样不可改样例
    resp = await client.get("/api/v1/problems")
    assert all(item["id"] != data["id"] for item in resp.json()["data"]["items"])

    # 非管理角色不可归档他人题目
    resp = await client.post(f"/api/v1/problems/{uuid.uuid4()}/archive", headers=admin_headers)
    assert resp.json()["code"] == 3001


@pytest.mark.asyncio
async def test_samples_change_requires_reverification(client, admin_headers, fake_storage):
    """样例变更（samples_updated_at 晚于 verified_at）同样触发重验门禁。"""
    data = await _create_problem(client, admin_headers)
    pid = data["id"]

    resp = await client.put(
        f"/api/v1/problems/{pid}/test-cases",
        json={"cases": [{"name": "c1", "input": "1", "expected_output": "2"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0

    # 模拟验题通过：暂存集标记已验（verified_at 晚于当前样例更新）
    await _pass_verification(pid)
    await _apply_pending(client, admin_headers, pid)

    resp = await client.get(f"/api/v1/problems/{pid}", headers=admin_headers)
    assert resp.json()["data"]["needs_reverification"] is False

    # 样例变更后把 verified_at 回拨到过去（模拟时间流逝）→ 须重新验题，发布被阻断
    resp = await client.put(
        f"/api/v1/problems/{pid}/samples",
        json={"samples": [{"input": "9", "output": "9"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0

    async with SessionLocal() as db:
        await db.execute(
            text("UPDATE problems SET verified_at = now() - interval '1 minute' WHERE id = :pid"),
            {"pid": pid},
        )
        await db.commit()

    resp = await client.get(f"/api/v1/problems/{pid}", headers=admin_headers)
    assert resp.json()["data"]["needs_reverification"] is True

    resp = await client.post(f"/api/v1/problems/{pid}/publish", headers=admin_headers)
    body = resp.json()
    assert body["code"] == 3002, body
    assert "重新验题" in body["message"]

    # 样例类重验不涉及暂存集：验题通过刷新 verified_at 即解除门禁（无应用动作）
    async with SessionLocal() as db:
        await db.execute(
            text("UPDATE problems SET verified_at = now() + interval '2 hour' WHERE id = :pid"),
            {"pid": pid},
        )
        await db.commit()
    resp = await client.get(f"/api/v1/problems/{pid}", headers=admin_headers)
    detail = resp.json()["data"]
    assert detail["needs_reverification"] is False
    assert detail["samples"] == [{"name": "sample1", "input": "9", "output": "9"}]

    resp = await client.post(f"/api/v1/problems/{pid}/publish", headers=admin_headers)
    assert resp.json()["code"] == 0, resp.text


@pytest.mark.asyncio
async def test_any_user_can_submit_verification(client, admin_headers, user_headers, fake_storage):
    """提交验题代码不限身份：普通用户无需邀请即可在 pending 记录存在时提交。"""
    data = await _create_problem(client, admin_headers)
    problem_id = data["id"]

    # 发起验题（不带邀请链接，创建空白 pending 记录）
    resp = await client.post(f"/api/v1/problems/{problem_id}/verify", json={}, headers=admin_headers)
    assert resp.json()["code"] == 0, resp.text
    assert "invite" not in resp.json()["data"]

    # 普通用户（非出题人 / 管理角色）直接提交验题代码
    resp = await client.post(
        f"/api/v1/problems/{problem_id}/verify",
        json={"code": "print(1)", "language": "python3.12"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    submission_id = resp.json()["data"]["submission_id"]

    async with SessionLocal() as db:
        submission = (
            await db.execute(select(Submission).where(Submission.id == uuid.UUID(submission_id)))
        ).scalar_one()
        assert submission.submit_type == "verify"

        submission.status = "accepted"
        from app.services.problem import complete_verification

        await complete_verification(
            db, submission.verification_id, passed=True, verifier_id=submission.user_id
        )
        await db.commit()

        problem = await db.get(Problem, uuid.UUID(problem_id))
        assert problem.is_verified is True
        # verifier_id 回写实际提交人（普通用户）
        assert str(problem.verified_by) == str(submission.user_id)


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

    # 重复发起 → 幂等复用同一邀请链接（不再报 3003）
    resp = await client.post(
        f"/api/v1/problems/{problem_id}/verify",
        json={"invite_expires_hours": 24},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["invite"]["token"] == invite_token

    # 公开解析邀请链接（返回题面与样例供受邀人查看）
    resp = await client.get(f"/api/v1/verify-invites/{invite_token}")
    parsed = resp.json()["data"]
    assert parsed["problem_id"] == problem_id
    assert parsed["problem_title"] == "A+B Problem"
    assert parsed["background"] == "经典入门题"
    assert parsed["description"]
    assert isinstance(parsed["samples"], list)

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
        from app.services.problem import complete_verification

        await complete_verification(
            db, submission.verification_id, passed=True, verifier_id=submission.user_id
        )
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
        json={"cases": [{"name": "c1", "input": "1", "expected_output": "2"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0

    # 测试点在验题通过后变更：模拟重新验题通过并显式生效
    await _pass_verification(problem_id)
    await _apply_pending(client, admin_headers, problem_id)

    resp = await client.post(f"/api/v1/problems/{problem_id}/publish", headers=admin_headers)
    assert resp.json()["code"] == 0


@pytest.mark.asyncio
async def test_submission_history_and_detail(client, admin_headers, user_headers, fake_storage, monkeypatch):
    data = await _create_problem(client, admin_headers)
    async with SessionLocal() as db:
        row = await db.get(Problem, data["id"])
        row.status = "published"
        row.verified_at = datetime.now()
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
    assert history["items"][0]["score"] is not None

    # 详情含代码与测试点明细骨架
    resp = await client.get(f"/api/v1/submissions/{submission_id}", headers=admin_headers)
    detail = resp.json()["data"]
    assert detail["code"] == "int main(){}"
    assert detail["language"] == "cpp17"
    assert isinstance(detail["cases"], list)
    assert detail["score"] is not None

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
async def test_replace_cases_keeps_history_results(client, admin_headers, fake_storage):
    """回归（行不可变版本化）：全量替换只改写暂存集，旧行退役留档，
    历史判题结果的 test_case_id 外键恒有效（不再置空）。"""
    data = await _create_problem(client, admin_headers)
    pid = uuid.UUID(data["id"])
    resp = await client.put(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={"cases": [{"name": "c1", "input": "1", "expected_output": "2"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0

    # 模拟一次已完成判题的提交：结果行引用当前测试点
    async with SessionLocal() as db:
        case = (await db.execute(select(TestCase).where(TestCase.problem_id == pid))).scalars().one()
        old_case_id = case.id
        user_id = (await db.execute(select(User).limit(1))).scalar_one().id
        submission = Submission(
            user_id=user_id, problem_id=pid, language="cpp17",
            code="int main(){}", status="accepted",
        )
        db.add(submission)
        await db.flush()
        db.add(SubmissionTestCaseResult(
            submission_id=submission.id, test_case_id=case.id, status="accepted",
        ))
        await db.commit()

    # 全量替换：目标状态写入暂存集，旧行不删除、仅退役
    resp = await client.put(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={"cases": [{"name": "c2", "input": "3", "expected_output": "4"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text

    async with SessionLocal() as db:
        # 历史结果保留且 test_case_id 仍指向退役的原始行（可回溯判题依据）
        row = (await db.execute(select(SubmissionTestCaseResult))).scalars().one()
        assert row.test_case_id == old_case_id
        # 原始行仍在表中（永不物理删除），新版本行为另一行
        remaining = (
            await db.execute(select(TestCase).where(TestCase.problem_id == pid))
        ).scalars().all()
        assert {str(r.id) for r in remaining} >= {str(old_case_id)}
        assert len(remaining) == 2


@pytest.mark.asyncio
async def test_detail_reads_back_case_contents(client, admin_headers, fake_storage):
    """回归：管理角色读详情回读测试点内容（而非 MinIO 对象 key）。"""
    data = await _create_problem(client, admin_headers)
    resp = await client.put(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={"cases": [{"name": "c1", "input": "1", "expected_output": "2"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0

    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    body = resp.json()
    assert body["code"] == 0, resp.text
    cases = body["data"]["test_cases"]
    assert len(cases) == 1
    assert cases[0]["input"] == "1"
    assert cases[0]["expected_output"] == "2"


@pytest.mark.asyncio
async def test_patch_test_cases_incremental(client, admin_headers, fake_storage):
    """PATCH 增量语义：只改动提交的行；缺省字段内容不变；空补丁不触碰集合状态。"""
    data = await _create_problem(client, admin_headers)
    pid = uuid.UUID(data["id"])
    resp = await client.put(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={"cases": [
            {"name": "c1", "input": "1", "expected_output": "2"},
            {"name": "c2", "input": "3", "expected_output": "4"},
        ]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0

    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    detail_cases = resp.json()["data"]["test_cases"]
    c1 = next(c for c in detail_cases if c["name"] == "c1")
    c2 = next(c for c in detail_cases if c["name"] == "c2")

    # 增量：仅改名 c1（input/expected_output 缺省 = 内容不变）+ 目标状态移除 c2
    resp = await client.patch(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={
            "upserts": [{"id": c1["id"], "name": "c1-renamed", "sort_order": 1}],
            "delete_ids": [c2["id"]],
        },
        headers=admin_headers,
    )
    body = resp.json()
    assert body["code"] == 0, resp.text
    returned = body["data"]["cases"]
    assert len(returned) == 1
    kept = returned[0]
    assert kept["name"] == "c1-renamed"
    assert kept["input"] == "1" and kept["expected_output"] == "2"  # 内容保持不变
    assert kept["staged"] is True
    assert kept["id"] != c1["id"]  # 行不可变：有效变更生成新版本行（origin_id 指回原行）

    # 空 PATCH：无任何行被触碰，updated_at 全部不变
    async with SessionLocal() as db:
        before = {str(r.id): r.updated_at for r in (
            await db.execute(select(TestCase).where(TestCase.problem_id == pid))).scalars().all()}
    resp = await client.patch(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={"upserts": [], "delete_ids": []},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0
    async with SessionLocal() as db:
        after = {str(r.id): r.updated_at for r in (
            await db.execute(select(TestCase).where(TestCase.problem_id == pid))).scalars().all()}
    assert after == before


@pytest.mark.asyncio
async def test_patch_test_cases_clear_content(client, admin_headers, fake_storage):
    """回归：PATCH 显式空字符串 = 清空该侧内容（写空对象），缺省字段保持不变。"""
    data = await _create_problem(client, admin_headers)
    resp = await client.put(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={"cases": [{"name": "c1", "input": "1", "expected_output": "2"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    c1 = resp.json()["data"]["test_cases"][0]

    # 仅清空输入（显式空字符串），期望输出缺省 = 不变
    resp = await client.patch(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={"upserts": [{"id": c1["id"], "input": "", "sort_order": 1}], "delete_ids": []},
        headers=admin_headers,
    )
    body = resp.json()
    assert body["code"] == 0, resp.text
    kept = body["data"]["cases"][0]
    assert kept["input"] == ""  # 真正清空，而非保留旧值 "1"
    assert kept["expected_output"] == "2"
    assert kept["id"] != c1["id"]  # 内容变更 → 新版本行

    # 两侧同时显式置空 → 1001（与新增路径「输入输出不能全空」一致）
    resp = await client.patch(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={"upserts": [{"id": kept["id"], "input": "", "expected_output": ""}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 1001

    # 回读稳定：清空结果持久化，未触碰的期望输出不受影响
    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    again = resp.json()["data"]["test_cases"][0]
    assert again["input"] == "" and again["expected_output"] == "2"


@pytest.mark.asyncio
async def test_staged_edit_does_not_touch_active_until_promotion(client, admin_headers, fake_storage):
    """暂存/生效分离：编辑只落暂存集；判题生效集与 data_version 在晋升前不变。"""
    data = await _create_problem(client, admin_headers)
    pid = uuid.UUID(data["id"])
    cases_url = f"/api/v1/problems/{data['id']}/test-cases"

    resp = await client.put(
        cases_url,
        json={"cases": [
            {"name": "c1", "input": "1", "expected_output": "2"},
            {"name": "c2", "input": "3", "expected_output": "4"},
        ]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0
    await _pass_verification(pid)
    await _apply_pending(client, admin_headers, pid)  # 首验通过并生效，生效集就位

    async def _active_ids() -> list[str]:
        async with SessionLocal() as db:
            row = await db.get(Problem, pid)
            return [str(v) for v in row.active_case_ids]

    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    detail = resp.json()["data"]
    active_snapshot = [c["id"] for c in detail["test_cases"]]
    assert active_snapshot == await _active_ids()

    from app.rpc.judge_jobs import compute_data_version
    from app.services.problem import list_active_cases

    def _fingerprint(rows) -> str:
        import hashlib

        latest = max((r.updated_at for r in rows), default=None)
        raw = f"{len(rows)}|{latest.isoformat() if latest else 'empty'}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async with SessionLocal() as db:
        problem = await db.get(Problem, pid)
        _, judged = await compute_data_version(db, problem)
        assert [str(c.id) for c in judged] == active_snapshot
        version_active_before = _fingerprint(await list_active_cases(db, problem))

    # 仅修改 c1 的输入：生成新版本行进暂存集，c2 沿用原 id，生效集不动
    c1 = detail["test_cases"][0]
    c2 = detail["test_cases"][1]
    resp = await client.patch(
        cases_url,
        json={"upserts": [{"id": c1["id"], "input": "9"}], "delete_ids": []},
        headers=admin_headers,
    )
    body = resp.json()
    assert body["code"] == 0, resp.text
    cases = body["data"]["cases"]
    new_c1 = next(c for c in cases if c["name"] == "c1")
    new_c2 = next(c for c in cases if c["name"] == "c2")
    assert new_c1["id"] != c1["id"]
    assert new_c2["id"] == c2["id"]  # 未改动点沿用原 id
    assert all(c["staged"] for c in cases)

    async with SessionLocal() as db:
        row = await db.get(Problem, pid)
        assert [str(v) for v in row.active_case_ids] == active_snapshot  # 生效集未动
        pending_ids = [str(v) for v in row.pending_case_ids]
        assert pending_ids == [new_c1["id"], new_c2["id"]]
        assert row.case_status == "to_reverify"
        # 练习/比赛的判定集（生效集）不受暂存编辑影响；验题判定集为暂存集
        version_active_after = _fingerprint(await list_active_cases(db, row))
        assert version_active_after == version_active_before
        _, judged_after = await compute_data_version(db, row)
        assert [str(c.id) for c in judged_after] == active_snapshot
        _, judged_verify = await compute_data_version(db, row, verify=True)
        assert [str(c.id) for c in judged_verify] == pending_ids
        # 旧行退役留档：3 行（原 c1、原 c2、新 c1）
        total = len((
            await db.execute(select(TestCase).where(TestCase.problem_id == pid))
        ).scalars().all())
        assert total == 3

    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    assert resp.json()["data"]["needs_reverification"] is True

    # 验题通过：仅标记「已验待生效」，生效集与练习判定集仍不动
    await _pass_verification(pid)
    async with SessionLocal() as db:
        row = await db.get(Problem, pid)
        assert row.pending_verified is True
        assert row.case_status == "verified"
        assert [str(v) for v in row.active_case_ids] == active_snapshot
    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    assert resp.json()["data"]["needs_reverification"] is True  # 未显式生效前持续为真

    # 显式应用（点保存）→ 晋升，之后可发布
    await _apply_pending(client, admin_headers, pid)
    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    promoted = resp.json()["data"]
    assert promoted["needs_reverification"] is False
    assert [c["id"] for c in promoted["test_cases"]] == [new_c1["id"], new_c2["id"]]
    assert all(c["staged"] is False for c in promoted["test_cases"])
    resp = await client.post(f"/api/v1/problems/{data['id']}/publish", headers=admin_headers)
    assert resp.json()["code"] == 0, resp.text


@pytest.mark.asyncio
async def test_delete_last_case_rejected(client, admin_headers, fake_storage):
    """目标状态不允许为空：删除最后一个测试点被拒绝，集合状态不被破坏。"""
    data = await _create_problem(client, admin_headers)
    cases_url = f"/api/v1/problems/{data['id']}/test-cases"
    resp = await client.put(
        cases_url,
        json={"cases": [{"name": "c1", "input": "1", "expected_output": "2"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    case_id = resp.json()["data"]["test_cases"][0]["id"]

    resp = await client.patch(
        cases_url,
        json={"upserts": [], "delete_ids": [case_id]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 1001

    # 拒绝后集合状态完好：详情仍能看到该测试点
    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    assert len(resp.json()["data"]["test_cases"]) == 1


@pytest.mark.asyncio
async def test_failed_verification_keeps_pending(client, admin_headers, user_headers, fake_storage):
    """验题失败：暂存集保留（继续编辑后可重验），生效集不变。"""
    data = await _create_problem(client, admin_headers)
    cases_url = f"/api/v1/problems/{data['id']}/test-cases"
    resp = await client.put(
        cases_url,
        json={"cases": [{"name": "c1", "input": "1", "expected_output": "2"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0
    await _pass_verification(data["id"])
    await _apply_pending(client, admin_headers, data["id"])  # 生效集就位

    resp = await client.get(f"/api/v1/problems/{data['id']}", headers=admin_headers)
    old_case = resp.json()["data"]["test_cases"][0]
    resp = await client.patch(
        cases_url,
        json={"upserts": [{"id": old_case["id"], "expected_output": "9"}]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0

    resp = await client.post(f"/api/v1/problems/{data['id']}/verify", json={}, headers=admin_headers)
    verification_id = resp.json()["data"]["verification_id"]

    from app.services.problem import complete_verification

    async with SessionLocal() as db:
        submission = (
            await db.execute(select(User).limit(1))
        ).scalar_one()
        await complete_verification(db, uuid.UUID(verification_id), passed=False, verifier_id=submission.id)
        await db.commit()

        problem = await db.get(Problem, uuid.UUID(data["id"]))
        assert problem.pending_case_ids is not None  # 暂存集保留
        assert [str(v) for v in problem.active_case_ids] == [old_case["id"]]  # 生效集不动
        assert problem.case_status == "to_reverify"
        assert problem.is_verified is True  # 历史验题事实不受失败影响


@pytest.mark.asyncio
async def test_patch_test_cases_rejects_unknown_and_conflicting_ids(client, admin_headers):
    data = await _create_problem(client, admin_headers)
    fake_id = str(uuid.uuid4())
    resp = await client.patch(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={"upserts": [], "delete_ids": [fake_id]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 3001
    resp = await client.patch(
        f"/api/v1/problems/{data['id']}/test-cases",
        json={"upserts": [{"id": fake_id, "name": "x"}], "delete_ids": [fake_id]},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 1001


@pytest.mark.asyncio
async def test_promote_endpoint_removed(client, admin_headers):
    """promote 通道已整体移除（团队题封闭，见 2026-08-24 决策记录）。"""
    data = await _create_problem(client, admin_headers)
    resp = await client.post(f"/api/v1/problems/{data['id']}/promote", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_spj_fields_rejected_on_update(client, admin_headers):
    """ProblemUpdate extra=forbid：spj/spj_code 字段不再可写。"""
    data = await _create_problem(client, admin_headers)
    resp = await client.put(
        f"/api/v1/problems/{data['id']}",
        json={"spj": True},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001  # 参数校验失败（extra 字段禁止）


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


# ---- 标签体系 ----


async def _create_tag(client, admin_headers, name: str, color: str | None = None) -> dict:
    resp = await client.post(
        "/api/v1/admin/tags", json={"name": name, "color": color}, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0
    return resp.json()["data"]


@pytest.mark.asyncio
async def test_tag_admin_crud_and_archive(client, admin_headers, user_headers):
    # 非管理员不可管理标签
    resp = await client.post("/api/v1/admin/tags", json={"name": "DP"}, headers=user_headers)
    assert resp.status_code == 403

    tag = await _create_tag(client, admin_headers, "动态规划", "#4098ec")
    assert tag["status"] == "active"

    # 重名 → 409 重复
    resp = await client.post("/api/v1/admin/tags", json={"name": " 动态规划 "}, headers=admin_headers)
    assert resp.json()["code"] != 0

    # 改名改色
    resp = await client.put(
        f"/api/v1/admin/tags/{tag['id']}", json={"name": "DP", "color": "#18a058"}, headers=admin_headers
    )
    body = resp.json()["data"]
    assert body["name"] == "DP" and body["color"] == "#18a058"

    # 公开激活列表可见
    resp = await client.get("/api/v1/problems/tags")
    assert [item["name"] for item in resp.json()["data"]] == ["DP"]

    # 归档后：管理列表仍在（状态 archived），公开列表消失
    resp = await client.post(f"/api/v1/admin/tags/{tag['id']}/archive", headers=admin_headers)
    assert resp.json()["data"]["status"] == "archived"
    resp = await client.get("/api/v1/problems/tags")
    assert resp.json()["data"] == []
    resp = await client.get("/api/v1/admin/tags", headers=admin_headers)
    names = {item["name"]: item["status"] for item in resp.json()["data"]}
    assert names["DP"] == "archived"


@pytest.mark.asyncio
async def test_problem_tag_assignment_and_filter(client, admin_headers):
    await _create_tag(client, admin_headers, "图论")
    await _create_tag(client, admin_headers, "入门")
    problem = await _create_problem(client, admin_headers, tags=["图论", "入门"])

    resp = await client.get(f"/api/v1/problems/{problem['id']}", headers=admin_headers)
    assert resp.json()["data"]["tags"] == ["入门", "图论"]  # 按名排序返回

    # 编辑全量替换：清空再单挂一个
    resp = await client.put(
        f"/api/v1/problems/{problem['id']}", json={"tags": ["图论"]}, headers=admin_headers
    )
    resp = await client.get(f"/api/v1/problems/{problem['id']}", headers=admin_headers)
    assert resp.json()["data"]["tags"] == ["图论"]

    # 未知 / 归档标签名 → 1001
    resp = await client.put(
        f"/api/v1/problems/{problem['id']}", json={"tags": ["不存在"]}, headers=admin_headers
    )
    assert resp.json()["code"] == 1001
    archive_resp = await client.get("/api/v1/problems/tags")
    graph_id = next(i["id"] for i in archive_resp.json()["data"] if i["name"] == "图论")
    await client.post(f"/api/v1/admin/tags/{graph_id}/archive", headers=admin_headers)
    resp = await client.put(
        f"/api/v1/problems/{problem['id']}", json={"tags": ["图论"]}, headers=admin_headers
    )
    assert resp.json()["code"] == 1001

    # 发布 + 公开后，题库中心可按标签筛选
    async with SessionLocal() as db:
        row = await db.get(Problem, uuid.UUID(problem["id"]))
        row.status = "published"
        row.verified_at = datetime.now()
        row.published_at = datetime.now()
        await db.commit()
    resp = await client.get("/api/v1/problems?tag=图论")
    assert resp.json()["data"]["total"] == 1

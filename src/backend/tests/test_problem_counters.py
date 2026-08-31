"""题目难度分与通过率统计测试（docs/contracts/problems.md problem_counters）。

覆盖：difficulty 创建/编辑校验与区间筛选、problem_counters 判题终态累加、
统计口径（verify / system_error 不计入）、列表与详情计数回填。
"""
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.judge import Submission
from app.models.problem import Problem, ProblemCounter, ProblemVerification, TestCase
from app.models.user import User
from app.rpc.judge_jobs import CaseOutcome, JudgeOutcome, apply_job_result
from app.enums import SubmitType, VerificationStatus

from .conftest import FakeStorage


async def _any_user_id() -> str:
    async with SessionLocal() as db:
        return str((await db.execute(select(User).limit(1))).scalar_one().id)


async def _seed_judged_problem(storage, *, case_id=None) -> str:
    """已发布题目 + 1 个生效测试点（判题数据写入 fake storage）。"""
    case_id = case_id or uuid_mod.uuid4()
    async with SessionLocal() as db:
        problem = Problem(title=f"P-{uuid_mod.uuid4().hex[:8]}", description="D",
                          owner_id=uuid_mod.UUID(await _any_user_id()),
                          status="published", visibility="public", verified_at=datetime.now(),
                          active_case_ids=[str(case_id)], case_status="ok")
        db.add(problem)
        await db.flush()
        db.add(TestCase(id=case_id, problem_id=problem.id, name="c1",
                        input_oss_id=f"cases/{case_id}.in",
                        expected_output_oss_id=f"cases/{case_id}.out", sort_order=1))
        await db.commit()
        pid = str(problem.id)
    storage.store[f"cases/{case_id}.in"] = (b"1\n", "text/plain")
    storage.store[f"cases/{case_id}.out"] = (b"2\n", "text/plain")
    return pid


async def _seed_judging_submission(problem_id: str, *, submit_type: str = "practice",
                                   verification_id=None) -> str:
    async with SessionLocal() as db:
        sub = Submission(user_id=uuid_mod.UUID(await _any_user_id()),
                         problem_id=uuid_mod.UUID(problem_id), language="cpp17", code="int main(){}",
                         submit_type=submit_type, verification_id=verification_id, status="judging")
        db.add(sub)
        await db.commit()
        return str(sub.id)


async def _get_counter(problem_id: str) -> ProblemCounter | None:
    async with SessionLocal() as db:
        return await db.get(ProblemCounter, uuid_mod.UUID(problem_id))


def _outcome(sid: str, case_id, status: str) -> JudgeOutcome:
    return JudgeOutcome(
        submission_id=sid, status=status, time_used_ms=10, memory_used_kb=1024,
        error_message=None,
        cases=(CaseOutcome(test_case_id=str(case_id), status=status,
                           time_used_ms=10, memory_used_kb=1024, output=b"2\n"),),
    )


@pytest.mark.asyncio
async def test_apply_result_counts_accepted_and_wrong(fake_storage):
    """AC 计入 accepted_count；WA 只计提交数。"""
    case_id = uuid_mod.uuid4()
    pid = await _seed_judged_problem(fake_storage, case_id=case_id)

    sid = await _seed_judging_submission(pid)
    async with SessionLocal() as db:
        assert await apply_job_result(db, _outcome(sid, case_id, "accepted"), storage=fake_storage) is True
    counter = await _get_counter(pid)
    assert counter is not None
    assert counter.submission_count == 1 and counter.accepted_count == 1

    sid = await _seed_judging_submission(pid)
    async with SessionLocal() as db:
        await apply_job_result(db, _outcome(sid, case_id, "wrong_answer"), storage=fake_storage)
    counter = await _get_counter(pid)
    assert counter.submission_count == 2 and counter.accepted_count == 1


@pytest.mark.asyncio
async def test_apply_result_excludes_system_error(fake_storage):
    """system_error（平台故障）不计入提交数。"""
    case_id = uuid_mod.uuid4()
    pid = await _seed_judged_problem(fake_storage, case_id=case_id)
    sid = await _seed_judging_submission(pid)
    async with SessionLocal() as db:
        await apply_job_result(db, _outcome(sid, case_id, "system_error"), storage=fake_storage)
    assert await _get_counter(pid) is None


@pytest.mark.asyncio
async def test_apply_result_excludes_verify(fake_storage):
    """验题提交即使 AC 也不计入统计。"""
    case_id = uuid_mod.uuid4()
    pid = await _seed_judged_problem(fake_storage, case_id=case_id)
    async with SessionLocal() as db:
        verification = ProblemVerification(problem_id=uuid_mod.UUID(pid), status=VerificationStatus.PENDING)
        db.add(verification)
        await db.commit()
        vid = verification.id
    sid = await _seed_judging_submission(pid, submit_type=SubmitType.VERIFY, verification_id=vid)
    async with SessionLocal() as db:
        await apply_job_result(db, _outcome(sid, case_id, "accepted"), storage=fake_storage)
    assert await _get_counter(pid) is None


@pytest.mark.asyncio
async def test_problem_difficulty_create_update_and_validation(client, admin_headers):
    """难度分创建/编辑；负数拒绝（1001）。"""
    resp = await client.post("/api/v1/problems", json={
        "title": "T", "background": "B", "description": "D",
        "input_description": "I", "output_description": "O", "difficulty": 1800,
    }, headers=admin_headers)
    data = resp.json()["data"]
    assert data["difficulty"] == 1800

    resp = await client.put(f"/api/v1/problems/{data['id']}", json={"difficulty": 2500},
                            headers=admin_headers)
    assert resp.json()["data"]["difficulty"] == 2500

    resp = await client.post("/api/v1/problems", json={
        "title": "T2", "background": "B", "description": "D",
        "input_description": "I", "output_description": "O", "difficulty": -1,
    }, headers=admin_headers)
    assert resp.json()["code"] == 1001


@pytest.mark.asyncio
async def test_problem_list_difficulty_filter_and_counts(client, admin_headers, fake_storage):
    """列表难度区间筛选 + 计数回填（未评分题目不落入任何区间）。"""
    case_id = uuid_mod.uuid4()
    pid = await _seed_judged_problem(fake_storage, case_id=case_id)
    sid = await _seed_judging_submission(pid)
    async with SessionLocal() as db:
        await apply_job_result(db, _outcome(sid, case_id, "accepted"), storage=fake_storage)

    async with SessionLocal() as db:
        row = await db.get(Problem, uuid_mod.UUID(pid))
        row.difficulty = 1800
        await db.commit()

    resp = await client.get("/api/v1/problems?difficulty_min=1500&difficulty_max=2000")
    body = resp.json()
    assert body["code"] == 0
    items = body["data"]["items"]
    assert pid in [i["id"] for i in items]
    item = next(i for i in items if i["id"] == pid)
    assert item["submission_count"] == 1 and item["accepted_count"] == 1

    resp = await client.get("/api/v1/problems?difficulty_min=2500")
    assert pid not in [i["id"] for i in resp.json()["data"]["items"]]

    resp = await client.get("/api/v1/problems?difficulty_min=100&difficulty_max=50")
    assert resp.json()["code"] == 1001


@pytest.mark.asyncio
async def test_problem_detail_returns_counts(client, admin_headers, fake_storage):
    """详情返回 difficulty 与计数（无提交按 0）。"""
    case_id = uuid_mod.uuid4()
    pid = await _seed_judged_problem(fake_storage, case_id=case_id)
    resp = await client.get(f"/api/v1/problems/{pid}", headers=admin_headers)
    data = resp.json()["data"]
    assert data["submission_count"] == 0 and data["accepted_count"] == 0
    assert data["difficulty"] is None

    sid = await _seed_judging_submission(pid)
    async with SessionLocal() as db:
        await apply_job_result(db, _outcome(sid, case_id, "wrong_answer"), storage=fake_storage)
    resp = await client.get(f"/api/v1/problems/{pid}", headers=admin_headers)
    data = resp.json()["data"]
    assert data["submission_count"] == 1 and data["accepted_count"] == 0

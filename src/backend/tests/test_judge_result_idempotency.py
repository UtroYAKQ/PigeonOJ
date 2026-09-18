"""判题终态回写幂等性测试（docs/contracts/judge.md apply_job_result）。

覆盖：同一 submission 的结果消息重复送达（节点重连后重发）时，第二次调用
不重复累加通过率计数 / 不重复回写状态 / 不重复触发榜单与缓存失效副作用。
幂等机制 = 状态机判断（apply_job_result 仅接受 judging 状态的提交，终态回写后
重放消息被直接拒绝，返回 False）。
"""
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.enums import SubmitType
from app.models.contest import ContestRegistration
from app.models.judge import Submission, SubmissionTestCaseResult
from app.models.problem import Problem, ProblemCounter, TestCase
from app.models.user import User
from app.rpc.judge_jobs import CaseOutcome, JudgeOutcome, apply_job_result
from app.services.contest import ContestService

from .conftest import FakeStorage
from .test_contests import _contest_payload, _manager_headers


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


async def _seed_judging_submission(problem_id: str, **kwargs) -> str:
    async with SessionLocal() as db:
        sub = Submission(user_id=uuid_mod.UUID(await _any_user_id()),
                         problem_id=uuid_mod.UUID(problem_id), language="cpp17", code="int main(){}",
                         submit_type="practice", status="judging", **kwargs)
        db.add(sub)
        await db.commit()
        return str(sub.id)


def _outcome(sid: str, case_id, status: str) -> JudgeOutcome:
    return JudgeOutcome(
        submission_id=sid, status=status, time_used_ms=10, memory_used_kb=1024,
        error_message=None,
        cases=(CaseOutcome(test_case_id=str(case_id), status=status,
                           time_used_ms=10, memory_used_kb=1024, output=b"2\n"),),
    )


async def _get_counter(problem_id: str) -> ProblemCounter | None:
    async with SessionLocal() as db:
        return await db.get(ProblemCounter, uuid_mod.UUID(problem_id))


async def _case_result_count(sid: str) -> int:
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(SubmissionTestCaseResult).where(SubmissionTestCaseResult.submission_id == uuid_mod.UUID(sid))
        )).scalars().all()
        return len(rows)


async def _case_id_of(problem_id: str) -> str:
    """取该题唯一测试点 id（种子时固定 1 个生效测试点）。"""
    async with SessionLocal() as db:
        row = (await db.execute(
            select(TestCase).where(TestCase.problem_id == uuid_mod.UUID(problem_id))
        )).scalar_one()
        return str(row.id)


@pytest.mark.asyncio
async def test_replay_practice_result_is_noop(fake_storage):
    """练习提交：结果重放（第二次 apply_job_result）不重复计数 / 不重复落结果行 / 不重复上传。"""
    case_id = uuid_mod.uuid4()
    pid = await _seed_judged_problem(fake_storage, case_id=case_id)
    sid = await _seed_judging_submission(pid)
    outcome = _outcome(sid, case_id, "accepted")

    async with SessionLocal() as db:
        assert await apply_job_result(db, outcome, storage=fake_storage) is True
    counter = await _get_counter(pid)
    assert counter is not None
    assert counter.submission_count == 1 and counter.accepted_count == 1
    assert await _case_result_count(sid) == 1
    uploads = [k for k, _, _ in fake_storage.puts if k.startswith(f"submissions/{sid}/")]
    assert len(uploads) == 1

    # 节点重连后重发同一条结果消息 → 状态机拒绝（非 judging），零副作用
    async with SessionLocal() as db:
        assert await apply_job_result(db, outcome, storage=fake_storage) is False
    counter = await _get_counter(pid)
    assert counter.submission_count == 1 and counter.accepted_count == 1
    assert await _case_result_count(sid) == 1
    uploads = [k for k, _, _ in fake_storage.puts if k.startswith(f"submissions/{sid}/")]
    assert len(uploads) == 1

    async with SessionLocal() as db:
        row = await db.get(Submission, uuid_mod.UUID(sid))
        assert row.status == "accepted"
        assert row.score == 100 and row.time_used_ms == 10


@pytest.mark.asyncio
async def test_replay_contest_result_is_noop(client, admin_headers, fake_storage, monkeypatch):
    """比赛提交：结果重放不重复累加榜单（IOI score / attempts）且缓存失效只触发一次。"""
    p1 = await _seed_judged_problem(fake_storage)
    manager = await _manager_headers(client)
    payload = _contest_payload(
        problems=[{"problem_id": p1, "score": 100}],
        start_offset=-7200, end_offset=3600, reg_start_offset=-10800, reg_end_offset=-5400,
        rule="IOI",
    )
    resp = await client.post("/api/v1/contests", json=payload, headers=manager)
    assert resp.json()["code"] == 0, resp.text
    cid = uuid_mod.UUID(resp.json()["data"]["id"])
    uid = uuid_mod.UUID(await _any_user_id())
    async with SessionLocal() as db:
        db.add(ContestRegistration(contest_id=cid, user_id=uid))
        await db.commit()
        sub = Submission(user_id=uid, problem_id=uuid_mod.UUID(p1), language="cpp17", code="x",
                         submit_type=SubmitType.CONTEST, contest_id=cid, rule_type="IOI",
                         status="judging")
        db.add(sub)
        await db.commit()
        sid = str(sub.id)

    # 统计缓存失效副作用（判题回写 → 榜单条件更新 → 失效榜单缓存）
    invalidate_calls = {"n": 0}
    orig_invalidate = ContestService.invalidate_board_cache

    async def counting_invalidate(self, contest_id):
        invalidate_calls["n"] += 1
        await orig_invalidate(self, contest_id)

    monkeypatch.setattr(ContestService, "invalidate_board_cache", counting_invalidate)

    outcome = _outcome(sid, await _case_id_of(p1), "accepted")
    async with SessionLocal() as db:
        assert await apply_job_result(db, outcome, storage=fake_storage) is True

    async with SessionLocal() as db:
        from app.models.contest import ContestRanking

        row = (await db.execute(
            select(ContestRanking).where(ContestRanking.contest_id == cid)
        )).scalar_one()
        assert row.score == 100  # IOI 取最高分；accepted 为 ACM 语义，IOI 不置位
    counter = await _get_counter(p1)
    assert counter.submission_count == 1 and counter.accepted_count == 1

    # 重放：榜单行不二次累加（score 仍 100），计数不变，缓存失效不再触发
    async with SessionLocal() as db:
        assert await apply_job_result(db, outcome, storage=fake_storage) is False
    async with SessionLocal() as db:
        from app.models.contest import ContestRanking

        row = (await db.execute(
            select(ContestRanking).where(ContestRanking.contest_id == cid)
        )).scalar_one()
        assert row.score == 100 and row.attempts == 0
    counter = await _get_counter(p1)
    assert counter.submission_count == 1 and counter.accepted_count == 1
    assert invalidate_calls["n"] == 1


@pytest.mark.asyncio
async def test_replay_after_terminal_status_rejected(fake_storage):
    """已终态提交（accepted）再次收到结果消息：直接拒绝且不写计数。"""
    case_id = uuid_mod.uuid4()
    pid = await _seed_judged_problem(fake_storage, case_id=case_id)
    async with SessionLocal() as db:
        sub = Submission(user_id=uuid_mod.UUID(await _any_user_id()),
                         problem_id=uuid_mod.UUID(pid), language="cpp17", code="int main(){}",
                         submit_type="practice", status="accepted", score=100)
        db.add(sub)
        await db.commit()
        sid = str(sub.id)

    async with SessionLocal() as db:
        assert await apply_job_result(db, _outcome(sid, case_id, "wrong_answer"), storage=fake_storage) is False
    counter = await _get_counter(pid)
    assert counter is None  # 拒绝路径不产生任何计数

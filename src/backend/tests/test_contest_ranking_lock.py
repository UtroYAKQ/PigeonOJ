"""榜单重建并发锁测试（ContestService.board 的 Redis SETNX 重建锁）。

覆盖：并发未命中缓存时仅一个请求执行重建（_compute_board 只跑一次，另一请求
等待缓存回填后直接返回）；持锁者长时间未回填时等待方超时回源兜底且不误删他人
锁；重建抛错时锁必须释放（不阻塞后续重建）。
"""
from __future__ import annotations

import asyncio
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.redis import get_redis
from app.models.contest import ContestRanking, ContestRegistration
from app.models.judge import Submission
from app.models.user import User
from app.services import contest as contest_mod
from app.services.contest import ContestService

from .test_contests import _contest_payload, _manager_headers, _seed_problem


async def _seed_contest_with_ranking(client, admin_headers) -> tuple[uuid_mod.UUID, uuid_mod.UUID]:
    """建赛（IOI，1 题）+ 种一条榜单行（score=80），返回 (contest_id, user_id)。"""
    p1 = await _seed_problem("重建锁榜单题")
    manager = await _manager_headers(client)
    payload = _contest_payload(
        problems=[{"problem_id": p1, "score": 100}],
        start_offset=-7200, end_offset=3600, reg_start_offset=-10800, reg_end_offset=-5400,
        rule="IOI",
    )
    resp = await client.post("/api/v1/contests", json=payload, headers=manager)
    assert resp.json()["code"] == 0, resp.text
    cid = uuid_mod.UUID(resp.json()["data"]["id"])
    async with SessionLocal() as db:
        uid = (await db.execute(select(User).where(User.email == "admin@pigeonoj.dev"))).scalar_one().id
        db.add(ContestRegistration(contest_id=cid, user_id=uid))
        await db.flush()
        sub = Submission(user_id=uid, problem_id=uuid_mod.UUID(p1), language="cpp17", code="x",
                         submit_type="contest", contest_id=cid, rule_type="IOI",
                         status="wrong_answer", score=80)
        db.add(sub)
        await db.flush()
        await ContestService(db).update_ranking_on_result(sub, "wrong_answer")
        await db.commit()
    return cid, uid


async def _admin_user() -> User:
    async with SessionLocal() as db:
        return (await db.execute(select(User).where(User.email == "admin@pigeonoj.dev"))).scalar_one()


_PRISTINE_COMPUTE = ContestService._compute_board  # 类属性未被 patch 前的真实计算函数


def _counting_compute(monkeypatch, *, delay: float = 0.0, explode: bool = False):
    """包装 ContestService._compute_board：计数 + 可选延迟 / 抛错。"""
    calls = {"n": 0}
    orig = _PRISTINE_COMPUTE

    async def wrapped(self, contest):
        calls["n"] += 1
        if delay:
            await asyncio.sleep(delay)
        if explode:
            raise RuntimeError("compute exploded")
        return await orig(self, contest)

    monkeypatch.setattr(ContestService, "_compute_board", wrapped)
    return calls


@pytest.mark.asyncio
async def test_board_concurrent_rebuild_runs_compute_once(client, admin_headers, monkeypatch):
    """两个请求并发未命中缓存：SETNX 互斥使 _compute_board 只执行一次，
    第二个请求等待缓存回填后返回同一榜单；完成后重建锁被释放。"""
    cid, uid = await _seed_contest_with_ranking(client, admin_headers)
    viewer = await _admin_user()
    calls = _counting_compute(monkeypatch, delay=0.3)

    lock_key = f"{contest_mod._board_cache_key(cid)}:lock"
    cache_key = contest_mod._board_cache_key(cid)
    r = await get_redis()
    await r.delete(cache_key, lock_key)

    # 各自独立会话的两个并发请求（模拟两个进程同时打到 board）
    async def one_board():
        async with SessionLocal() as db:
            return await ContestService(db).board(cid, viewer)

    boards = await asyncio.gather(one_board(), one_board())

    assert calls["n"] == 1, f"compute 应只执行一次，实际 {calls['n']} 次"
    assert boards[0].rows[0].total_score == 80
    assert boards[1].rows[0].total_score == 80
    assert boards[0].model_dump() == boards[1].model_dump()
    # 持锁者完成后锁必须删除（不靠 10s TTL 自然过期）
    assert await r.get(lock_key) is None


@pytest.mark.asyncio
async def test_board_lock_timeout_falls_back_without_deleting_foreign_lock(
    client, admin_headers, monkeypatch
):
    """他人持锁且迟迟不回填：等待方超时后自行回源计算兜底，
    且不得删除不属于自己的锁（仅 acquired 时才清理）。"""
    cid, uid = await _seed_contest_with_ranking(client, admin_headers)
    viewer = await _admin_user()
    calls = _counting_compute(monkeypatch)

    r = await get_redis()
    cache_key = contest_mod._board_cache_key(cid)
    lock_key = f"{cache_key}:lock"
    await r.delete(cache_key)
    # 模拟另一实例持有重建锁（不会回填缓存）
    await r.set(lock_key, "1", ex=10)
    # 缩短等待窗口，避免测试拖 3s
    monkeypatch.setattr(contest_mod, "BOARD_CACHE_LOCK_WAIT_SECONDS", 0.3)

    async with SessionLocal() as db:
        board = await ContestService(db).board(cid, viewer)

    assert calls["n"] == 1  # 超时回源兜底（正确性优先）
    assert board.rows[0].total_score == 80
    # 外部锁仍完好（未误删），缓存也未被本请求回填
    assert await r.get(lock_key) == "1"


@pytest.mark.asyncio
async def test_board_lock_released_when_compute_fails(client, admin_headers, monkeypatch):
    """重建抛错：锁仍必须在 finally 中释放，后续请求可以重新获得锁重建。"""
    cid, uid = await _seed_contest_with_ranking(client, admin_headers)
    viewer = await _admin_user()
    lock_key = f"{contest_mod._board_cache_key(cid)}:lock"
    r = await get_redis()
    await r.delete(contest_mod._board_cache_key(cid), lock_key)

    calls = _counting_compute(monkeypatch, explode=True)
    with pytest.raises(RuntimeError):
        async with SessionLocal() as db:
            await ContestService(db).board(cid, viewer)
    assert await r.get(lock_key) is None

    # 锁已释放：恢复真实计算后下一次 board 正常重建并回填缓存
    calls = _counting_compute(monkeypatch, delay=0)
    async with SessionLocal() as db:
        board = await ContestService(db).board(cid, viewer)
    assert calls["n"] == 1
    assert board.rows[0].total_score == 80
    assert await r.get(contest_mod._board_cache_key(cid)) is not None

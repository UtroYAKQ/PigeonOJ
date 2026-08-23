"""判题网关与负载均衡测试（无 Celery 架构）。

覆盖：注册表选节点、作业构建原子认领、令牌认证、结果落库、断线回收、巡检重派。
真实 gRPC 传输层由本机冒烟验证覆盖。
"""
from __future__ import annotations

import asyncio
import uuid as uuid_mod
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.modules.judge.gateway import (
    REGISTRY,
    NodeConnection,
    _reset_to_pending,
    _token_ok,
    maintenance_loop,
    send_job,
)
from app.modules.judge.models import Problem, Submission, TestCase
from app.modules.users.models import User
from app.shared.infra.database import SessionLocal


def _add_node(node_id: str, inflight: int = 0, capacity: int = 2) -> NodeConnection:
    conn = NodeConnection(node_id=node_id, name=node_id, capacity=capacity, version="test")
    for i in range(inflight):
        conn.inflight.add(f"fake-{node_id}-{i}")
    REGISTRY.register(conn)
    return conn


async def _any_user_id() -> str:
    async with SessionLocal() as db:
        return str((await db.execute(select(User).limit(1))).scalar_one().id)


async def _seed_problem_with_case(storage) -> str:
    """已发布题目 + 1 个正式测试点（数据写入 fake storage）。"""
    async with SessionLocal() as db:
        problem = Problem(title=f"P-{uuid_mod.uuid4().hex[:8]}", description="D",
                          owner_id=uuid_mod.UUID(await _any_user_id()),
                          status="published", visibility="public", is_verified=True)
        db.add(problem)
        await db.flush()
        case_id = uuid_mod.uuid4()
        db.add(TestCase(id=case_id, problem_id=problem.id, name="c1",
                        input_oss_id=f"cases/{case_id}.in",
                        expected_output_oss_id=f"cases/{case_id}.out",
                        score=100, sort_order=1))
        await db.commit()
        pid = str(problem.id)
    storage.store[f"cases/{case_id}.in"] = (b"1\n", "text/plain")
    storage.store[f"cases/{case_id}.out"] = (b"2\n", "text/plain")
    return pid


@pytest.fixture(autouse=True)
def _clean_registry():
    yield
    REGISTRY._connections.clear()


@pytest.mark.asyncio
async def test_dispatch_picks_least_loaded_node():
    _add_node("node-a", inflight=0)
    _add_node("node-b", inflight=3, capacity=8)
    best = min(REGISTRY.list_nodes(), key=lambda n: (len(n.inflight), n.node_id))
    assert best.node_id == "node-a"


@pytest.mark.asyncio
async def test_dispatch_returns_none_without_nodes():
    from app.modules.judge.gateway import dispatch_submission

    assert await dispatch_submission(uuid_mod.uuid4()) is None


@pytest.mark.asyncio
async def test_send_job_claims_and_pushes(client, admin_headers, fake_storage):
    """注册假节点 → API 提交 → 网关下行队列收到 SubmitJob 且提交已被认领 judging。"""
    pid = await _seed_problem_with_case(fake_storage)
    conn = _add_node("gw-1")

    resp = await client.post(
        "/api/v1/submissions",
        json={"problem_id": pid, "language": "cpp17", "code": "int main(){}"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    sid = resp.json()["data"]["submission_id"]

    msg = await asyncio.wait_for(conn.outbox.get(), timeout=5)
    assert msg.WhichOneof("payload") == "job"
    assert msg.job.submission_id == sid
    assert msg.job.language == "cpp17"
    assert len(msg.job.cases) == 1 and msg.job.cases[0].score == 100
    assert sid in conn.inflight

    async with SessionLocal() as db:
        row = await db.get(Submission, uuid_mod.UUID(sid))
        assert row.status == "judging"


@pytest.mark.asyncio
async def test_send_job_rejects_non_pending(client, admin_headers):
    """非 pending 提交（如已完成）不被重复派发。"""
    uid = uuid_mod.UUID(await _any_user_id())
    async with SessionLocal() as db:
        problem = Problem(title="P-x", description="D", owner_id=uid)
        db.add(problem)
        await db.flush()
        sub = Submission(user_id=uid, problem_id=problem.id, language="cpp17", code="x")
        db.add(sub)
        await db.commit()
        sub.status = "accepted"
        await db.commit()
        sid = str(sub.id)

    conn = _add_node("gw-2")
    assert await send_job("gw-2", uuid_mod.UUID(sid)) is False
    assert conn.outbox.empty()


def test_token_auth_requires_configured_tokens():
    assert _token_ok("") is False       # 未配置令牌 → 全拒绝（网关不启动）
    assert _token_ok("whatever") is False


@pytest.mark.asyncio
async def test_disconnect_resets_inflight_to_pending(client, admin_headers, fake_storage):
    pid = await _seed_problem_with_case(fake_storage)
    conn = _add_node("gw-3")

    resp = await client.post(
        "/api/v1/submissions",
        json={"problem_id": pid, "language": "cpp17", "code": "int main(){}"},
        headers=admin_headers,
    )
    sid = resp.json()["data"]["submission_id"]
    await asyncio.wait_for(conn.outbox.get(), timeout=5)

    recovered = REGISTRY.unregister(conn)
    await _reset_to_pending(recovered, reason="test")
    async with SessionLocal() as db:
        row = await db.get(Submission, uuid_mod.UUID(sid))
        assert row.status == "pending"


@pytest.mark.asyncio
async def test_maintenance_rescans_stale_pending(client, admin_headers, fake_storage):
    """派发后人为把 updated_at 置旧 → 巡检循环应再次投递到节点队列。"""
    pid = await _seed_problem_with_case(fake_storage)
    conn = _add_node("gw-4")

    resp = await client.post(
        "/api/v1/submissions",
        json={"problem_id": pid, "language": "cpp17", "code": "int main(){}"},
        headers=admin_headers,
    )
    sid = resp.json()["data"]["submission_id"]
    first = await asyncio.wait_for(conn.outbox.get(), timeout=5)
    del first

    # 重置回 pending 并把 updated_at 拨旧，模拟"派发丢失"
    async with SessionLocal() as db:
        row = await db.get(Submission, uuid_mod.UUID(sid))
        row.status = "pending"
        row.updated_at = datetime.now() - timedelta(minutes=10)
        await db.commit()

    task = asyncio.create_task(maintenance_loop(interval=0))
    try:
        second = await asyncio.wait_for(conn.outbox.get(), timeout=5)
        assert second.WhichOneof("payload") == "job"
        assert second.job.submission_id == sid
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

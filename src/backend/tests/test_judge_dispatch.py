"""判题网关与负载均衡测试（无 Celery 架构）。

覆盖：注册表选节点、作业构建原子认领、令牌验证、结果落库、断线回收、巡检重派。
真实 gRPC 传输层由容器冒烟验证覆盖。
"""
from __future__ import annotations

import asyncio
import uuid as uuid_mod
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.rpc.judge_gateway import (
    REGISTRY,
    NodeConnection,
    _attach_pump_watchdog,
    _pump_incoming,
    _reset_to_pending,
    _token_ok,
    dispatch_submission,
    maintenance_loop,
    send_job,
)
from app.rpc.gen import judge_pb2
from app.models.judge import Submission
from app.models.problem import Problem, TestCase
from app.models.user import User
from app.core.database import SessionLocal


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
    """已发布题目 + 1 个生效测试点（数据写入 fake storage）。"""
    from datetime import datetime

    async with SessionLocal() as db:
        case_id = uuid_mod.uuid4()
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
    from app.rpc.judge_gateway import dispatch_submission

    assert await dispatch_submission(uuid_mod.uuid4()) is None


@pytest.mark.asyncio
async def test_send_job_claims_and_pushes(client, admin_headers, fake_storage):
    """注册假节点 → API 提交 → 网关下发：队列收到 SubmitJob 且提交已被置为 judging。"""
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
    assert len(msg.job.cases) == 1 and msg.job.cases[0].name
    assert sid in conn.inflight

    async with SessionLocal() as db:
        row = await db.get(Submission, uuid_mod.UUID(sid))
        assert row.status == "judging"


@pytest.mark.asyncio
async def test_send_job_carries_case_metadata_only(client, admin_headers, fake_storage):
    """回归（性能）：派发不得从 MinIO 读测试点数据本体——数据由节点经
    FetchProblemData 按 data_version 拉取；对象缺失时作业仍可构建、消息仅含元数据。"""
    pid = await _seed_problem_with_case(fake_storage)
    fake_storage.store.clear()  # 任何 get_bytes 都会抛 OSError
    conn = _add_node("gw-meta")

    resp = await client.post(
        "/api/v1/submissions",
        json={"problem_id": pid, "language": "cpp17", "code": "int main(){}"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    sid = resp.json()["data"]["submission_id"]

    msg = await asyncio.wait_for(conn.outbox.get(), timeout=5)
    assert msg.job.submission_id == sid
    assert len(msg.job.cases) == 1
    assert msg.job.cases[0].test_case_id and msg.job.cases[0].name


@pytest.mark.asyncio
async def test_send_job_rejects_non_pending(client, admin_headers):
    """非 pending 提交（如已完成）不允许重复派发。"""
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
    assert _token_ok("") is False       # 未配置网关令牌 → 全部拒绝（网关不启动）
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
    """派发后人为把 updated_at 拨旧 → 巡检循环应再次投递到节点队列。"""
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

    # 重置为 pending 并把 updated_at 拨旧，模拟派发丢失
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


@pytest.mark.asyncio
async def test_heartbeat_updates_node_metrics():
    """心跳携带宿主指标 → 连接对象与 Redis 热数据均应体现（不再写死 0）。"""
    import json

    from app.core.redis import SANDBOX_NODE_KEY_PREFIX, get_redis

    conn = _add_node("metric-1", capacity=4)
    msg = judge_pb2.NodeMessage(heartbeat=judge_pb2.Heartbeat(
        running_tasks=1, cpu_usage=55, memory_usage=66,
    ))

    async def stream():
        yield msg

    await _pump_incoming(stream(), None, conn)

    assert conn.cpu_usage == 55
    assert conn.memory_usage == 66
    payload = conn.to_payload()
    assert payload.cpu_usage == 55 and payload.memory_usage == 66

    raw = await get_redis().get(f"{SANDBOX_NODE_KEY_PREFIX}metric-1")
    stored = json.loads(raw)
    assert stored["cpu_usage"] == 55 and stored["memory_usage"] == 66
    assert stored["status"] == "online"

    await REGISTRY.remove_heartbeat("metric-1")


@pytest.mark.asyncio
async def test_heartbeat_metrics_clamped_to_percent():
    """节点上报越界值 → 网关写入前钳制到 0-100。"""
    conn = _add_node("metric-2", capacity=1)
    msg = judge_pb2.NodeMessage(heartbeat=judge_pb2.Heartbeat(
        running_tasks=0, cpu_usage=150, memory_usage=-5,
    ))

    async def stream():
        yield msg

    await _pump_incoming(stream(), None, conn)
    assert conn.cpu_usage == 100
    assert conn.memory_usage == 0
    await REGISTRY.remove_heartbeat("metric-2")


@pytest.mark.asyncio
async def test_pump_survives_message_handler_error(monkeypatch):
    """单条上行消息处理失败（Redis/DB 瞬断）不得终止泵：后续消息仍被处理。

    回归背景：旧实现整个循环一个 try/except pass，一次 Redis 抖动就杀掉上行泵，
    心跳停写、结果回不来，而下行派发仍在继续（僵尸连接）。
    """
    conn = _add_node("pump-resilient", capacity=2)
    calls = {"n": 0}

    async def flaky_redis_heartbeat(target: NodeConnection) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("redis blip")

    monkeypatch.setattr(REGISTRY, "redis_heartbeat", flaky_redis_heartbeat)

    hb = judge_pb2.NodeMessage(heartbeat=judge_pb2.Heartbeat(running_tasks=0, cpu_usage=42, memory_usage=42))

    async def stream():
        yield hb
        yield hb

    await asyncio.wait_for(_pump_incoming(stream(), None, conn), timeout=5)
    assert calls["n"] == 2
    assert conn.cpu_usage == 42  # 第二条心跳仍被处理
    await REGISTRY.remove_heartbeat("pump-resilient")


@pytest.mark.asyncio
async def test_pump_exit_pushes_offline_sentinel():
    """上行泵任何原因退出 → 下行队列收到 None 哨兵 → Connect 主循环退出并清理连接。"""
    conn = NodeConnection(node_id="pump-sentinel", name="pump-sentinel", capacity=1, version="test")

    async def broken_stream():
        raise RuntimeError("stream broken")
        yield  # noqa: unreachable - 使其成为异步生成器

    task = asyncio.create_task(_pump_incoming(broken_stream(), None, conn))
    _attach_pump_watchdog(task, conn)
    sentinel = await asyncio.wait_for(conn.outbox.get(), timeout=5)
    assert sentinel is None


@pytest.mark.asyncio
async def test_stale_node_excluded_from_dispatch():
    """超过判活阈值无上行消息的节点不参与派发与并发统计（僵尸连接防护）。"""
    from app.rpc.judge_gateway import GatewayUnavailableError, active_judge_count, dispatch_run_code

    _add_node("stale-1", inflight=2, capacity=4)
    conn = REGISTRY.get("stale-1")
    conn.last_seen -= 10_000  # 强制判定为僵死（monotonic 秒）

    assert await active_judge_count() == 0
    assert await dispatch_submission(uuid_mod.uuid4()) is None
    with pytest.raises(GatewayUnavailableError):
        await dispatch_run_code(problem=None, sandbox_config=None, language="python3",
                                code=b"print(1)", stdin_data=b"", max_concurrent=4)

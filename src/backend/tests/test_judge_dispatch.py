"""判题网关与负载均衡测试（无 Celery 架构）。

覆盖：注册表选节点、作业构建原子认领、令牌验证、结果落库、断线回收、巡检重派。
真实 gRPC 传输层由容器冒烟验证覆盖。
"""
from __future__ import annotations

import asyncio
import json
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, select

from app.rpc import judge_jobs as jobs
from app.rpc.judge_gateway import (
    REGISTRY,
    NodeConnection,
    _available_nodes,
    _attach_pump_watchdog,
    _iter_rpc_chunks,
    _pump_incoming,
    _reset_to_pending,
    _token_ok,
    dispatch_submission,
    maintenance_loop,
    maintenance_once,
    send_job,
)
from app.rpc.gen import judge_pb2
from app.models.judge import Submission
from app.models.problem import Problem, TestCase
from app.models.user import User
from app.core.database import SessionLocal, engine
from app.core.redis import get_redis


def _add_node(node_id: str, inflight: int = 0, capacity: int = 2, supports_spj: bool = False) -> NodeConnection:
    conn = NodeConnection(node_id=node_id, name=node_id, capacity=capacity, version="test", supports_spj=supports_spj)
    for i in range(inflight):
        conn.inflight.add(f"fake-{node_id}-{i}")
    REGISTRY.register(conn)
    return conn


async def _any_user_id() -> str:
    async with SessionLocal() as db:
        return str((await db.execute(select(User).limit(1))).scalar_one().id)


async def _seed_problem_with_case(storage, *, spj: bool = False) -> str:
    """已发布题目 + 1 个生效测试点（数据写入 fake storage）；spj=True 额外配置生效特判程序。"""
    from datetime import datetime

    async with SessionLocal() as db:
        case_id = uuid_mod.uuid4()
        problem = Problem(title=f"P-{uuid_mod.uuid4().hex[:8]}", description="D",
                          owner_id=uuid_mod.UUID(await _any_user_id()),
                          status="published", visibility="public", verified_at=datetime.now(),
                          active_case_ids=[str(case_id)], case_status="ok",
                          spj_oss_id=f"problems/spj/{case_id}/code" if spj else None)
        db.add(problem)
        await db.flush()
        db.add(TestCase(id=case_id, problem_id=problem.id, name="c1",
                        input_oss_id=f"cases/{case_id}.in",
                        expected_output_oss_id=f"cases/{case_id}.out", sort_order=1))
        await db.commit()
        pid = str(problem.id)
    storage.store[f"cases/{case_id}.in"] = (b"1\n", "text/plain")
    storage.store[f"cases/{case_id}.out"] = (b"2\n", "text/plain")
    if spj:
        storage.store[f"problems/spj/{case_id}/code"] = (b"int main(){return 0;}", "text/x-c++src")
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
async def test_dispatch_skips_nodes_at_capacity():
    _add_node("full", inflight=2, capacity=2)
    free = _add_node("free", inflight=0, capacity=2)
    assert [n.node_id for n in _available_nodes()] == ["free"]
    assert min(_available_nodes(), key=lambda n: n.task_count).node_id == free.node_id


@pytest.mark.asyncio
async def test_dispatch_returns_none_when_all_nodes_full():
    _add_node("full-a", inflight=2, capacity=2)
    _add_node("full-b", inflight=4, capacity=4)
    assert await dispatch_submission(uuid_mod.uuid4()) is None


def test_iter_rpc_chunks_splits_and_rejoins():
    payload = b"x" * (1024 * 1024 + 13)
    chunks = list(_iter_rpc_chunks("cases/1.in", payload))
    assert len(chunks) == 2
    assert all(c.path == "cases/1.in" for c in chunks)
    assert b"".join(c.content for c in chunks) == payload
    empty = list(_iter_rpc_chunks("empty", b""))
    assert len(empty) == 1 and empty[0].content == b""


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


@pytest.mark.asyncio
async def test_dispatch_loads_context_once(client, admin_headers, fake_storage):
    """回归（查询放大）：单次派发只查一次提交/题目/配置/测试点，题面大字段不进 SQL。"""
    pid = await _seed_problem_with_case(fake_storage)
    uid = uuid_mod.UUID(await _any_user_id())
    async with SessionLocal() as db:
        sub = Submission(
            user_id=uid, problem_id=uuid_mod.UUID(pid), language="cpp17",
            code="int main(){}", status="pending",
        )
        db.add(sub)
        await db.commit()
        sid = sub.id
    conn = _add_node("ctx-node")

    statements: list[str] = []

    def _record(_conn, _cursor, statement, _params, _ctx, _many):
        statements.append(statement.lower())

    event.listen(engine.sync_engine, "before_cursor_execute", _record)
    try:
        assert await dispatch_submission(sid) == "ctx-node"
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _record)

    msg = await asyncio.wait_for(conn.outbox.get(), timeout=5)
    assert msg.job.submission_id == str(sid)
    selects = [sql for sql in statements if sql.lstrip().startswith("select")]
    for table in ("submissions", "problems", "sandbox_configs", "test_cases"):
        assert len([sql for sql in selects if f"from {table}" in sql]) == 1, table
    problem_sql = next(sql for sql in selects if "from problems" in sql)
    assert not any(col in problem_sql for col in ("description", "solution", "samples"))


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

async def _submit(client, admin_headers, pid: str) -> str:
    resp = await client.post(
        "/api/v1/submissions",
        json={"problem_id": pid, "language": "cpp17", "code": "int main(){}"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    return resp.json()["data"]["submission_id"]


async def _set_updated_at(sid: str, minutes_ago: int) -> None:
    async with SessionLocal() as db:
        row = await db.get(Submission, uuid_mod.UUID(sid))
        row.updated_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        await db.commit()


@pytest.mark.asyncio
async def test_reconnect_superseded_conn_cannot_reset_new_inflight(client, admin_headers, fake_storage):
    """回归（重连竞态）：同 ID 重连后，旧（僵尸）连接的迟到清理不得重置
    新连接正在判的提交——否则新节点回传结果被 apply_job_result 以「非 judging」
    丢弃、白判一遍并重新排队（断线重连后题卡在排队的根因之一）。"""
    pid = await _seed_problem_with_case(fake_storage)
    old = _add_node("race-node")
    sid = await _submit(client, admin_headers, pid)
    await asyncio.wait_for(old.outbox.get(), timeout=5)
    assert sid in old.inflight

    new = NodeConnection(node_id="race-node", name="race-node", capacity=2, version="test")
    REGISTRY.register(new)  # 同 ID 重连：in-flight 移交并清空旧连接
    assert sid in new.inflight and not old.inflight

    # 旧连接迟到 finally：回收必须为空，重置 no-op，提交保持 judging
    recovered_old = REGISTRY.unregister(old)
    assert recovered_old == set()
    await _reset_to_pending(recovered_old, reason="test")
    async with SessionLocal() as db:
        row = await db.get(Submission, uuid_mod.UUID(sid))
        assert row.status == "judging"

    # 新连接真实离线：正常回收
    await _reset_to_pending(REGISTRY.unregister(new), reason="test")
    async with SessionLocal() as db:
        row = await db.get(Submission, uuid_mod.UUID(sid))
        assert row.status == "pending"


@pytest.mark.asyncio
async def test_registration_kick_dispatches_backlog_immediately(client, admin_headers, fake_storage):
    """回归（节点上线派积压）：断线期间滞留的 pending 提交，在节点重新注册
    （踢醒事件）后立即重派，不必等扫描周期——修复「节点上线了题还在一直排队」。"""
    from app.rpc import judge_gateway as gw

    pid = await _seed_problem_with_case(fake_storage)
    sid = await _submit(client, admin_headers, pid)  # 提交时无在线节点 → 滞留 pending
    await _set_updated_at(sid, minutes_ago=10)

    conn = _add_node("kick-node")  # 节点上线
    gw._MAINTENANCE_KICK.set()     # 注册路径的踢醒（Connect 内同款）
    task = asyncio.create_task(gw.maintenance_loop(interval=30))
    try:
        msg = await asyncio.wait_for(conn.outbox.get(), timeout=5)
        assert msg.WhichOneof("payload") == "job"
        assert msg.job.submission_id == sid
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_failed_dispatch_lock_only_short_cooldown(client, admin_headers, fake_storage, monkeypatch):
    """回归（锁语义）：没有空闲容量时 pending 不抢锁；派发失败仍只短冷却（≤60s），
    派发成功后锁升级为在途保护窗。"""
    pid = await _seed_problem_with_case(fake_storage)
    sid = await _submit(client, admin_headers, pid)
    await _set_updated_at(sid, minutes_ago=10)
    lock_key = f"judge:requeue:{sid}"

    # 无在线节点 → free_slots=0：不进入候选循环，不抢锁、保持 pending
    await maintenance_once(30)
    assert await get_redis().ttl(lock_key) == -2
    async with SessionLocal() as db:
        assert (await db.get(Submission, uuid_mod.UUID(sid))).status == "pending"

    # 有容量但派发失败：短冷却锁（修复断线期烧 300s 锁、恢复后仍长时间排队）
    conn = _add_node("lock-node")

    async def _fail_dispatch(_sid):
        return False

    from app.rpc import judge_gateway as gw

    monkeypatch.setattr(gw, "dispatch_submission", _fail_dispatch)
    await maintenance_once(30)
    ttl = await get_redis().ttl(lock_key)
    assert 0 < ttl <= 60

    # 冷却到期（模拟 TTL 过期）→ 下一轮巡检派发成功，锁升级为在途保护
    await get_redis().delete(lock_key)
    monkeypatch.setattr(gw, "dispatch_submission", dispatch_submission)
    await maintenance_once(30)
    msg = await asyncio.wait_for(conn.outbox.get(), timeout=5)
    assert msg.job.submission_id == sid
    ttl = await get_redis().ttl(lock_key)
    assert ttl > 200


@pytest.mark.asyncio
async def test_reset_exhausted_marks_system_error(client, admin_headers, fake_storage):
    """回收重派满 3 次后转 system_error，不再 pending 空转。"""
    pid = await _seed_problem_with_case(fake_storage)
    conn = _add_node("retry-node")
    sid = await _submit(client, admin_headers, pid)
    assert sid in conn.inflight
    r = get_redis()
    await r.set(f"judge:attempts:{sid}", "2")
    await _reset_to_pending({sid}, reason="test")
    async with SessionLocal() as db:
        row = await db.get(Submission, uuid_mod.UUID(sid))
        assert row.status == "system_error"
        assert "retry exhausted" in row.error_message


# ---- SPJ 特判派发（docs/contracts.md §10.6） ----


@pytest.mark.asyncio
async def test_non_spj_job_dispatches_with_spj_flag_false(client, admin_headers, fake_storage):
    """普通题派发：SubmitJob.spj=False，旧节点（supports_spj=False）照常接单。"""
    pid = await _seed_problem_with_case(fake_storage)
    conn = _add_node("legacy-node", supports_spj=False)
    sid = await _submit(client, admin_headers, pid)
    msg = await asyncio.wait_for(conn.outbox.get(), timeout=5)
    assert msg.WhichOneof("payload") == "job"
    assert msg.job.spj is False


@pytest.mark.asyncio
async def test_spj_submission_fails_without_capable_node(client, admin_headers, fake_storage):
    """SPJ 题派给旧节点会退化为默认比对静默误判：无支持节点 → 直接落 system_error。"""
    pid = await _seed_problem_with_case(fake_storage, spj=True)
    _add_node("legacy-node", supports_spj=False)

    resp = await client.post(
        "/api/v1/submissions",
        json={"problem_id": pid, "language": "cpp17", "code": "int main(){}"},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    sid = resp.json()["data"]["submission_id"]
    async with SessionLocal() as db:
        row = await db.get(Submission, uuid_mod.UUID(sid))
        assert row.status == "system_error"
        assert "special judge" in row.error_message


@pytest.mark.asyncio
async def test_spj_job_dispatched_to_capable_node_with_flag(client, admin_headers, fake_storage):
    """SPJ 题只派给 supports_spj 节点，SubmitJob.spj=True。"""
    pid = await _seed_problem_with_case(fake_storage, spj=True)
    capable = _add_node("spj-node", supports_spj=True)
    _add_node("legacy-node", supports_spj=False)

    sid = await _submit(client, admin_headers, pid)
    msg = await asyncio.wait_for(capable.outbox.get(), timeout=5)
    assert msg.job.submission_id == sid
    assert msg.job.spj is True
    assert len(msg.job.cases) == 1


@pytest.mark.asyncio
async def test_data_fingerprint_changes_with_spj_key():
    """指纹必须覆盖特判程序：SPJ 覆盖 / 移除 / 晋升都使 data_version 变化，
    节点缓存失效；否则改判后仍命中旧数据目录。"""
    from types import SimpleNamespace

    from app.rpc.judge_jobs import data_fingerprint

    rows = [SimpleNamespace(updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))]
    base = data_fingerprint(rows, spj_key=None)
    assert data_fingerprint(rows, spj_key="a") != base
    assert data_fingerprint(rows, spj_key="b") != data_fingerprint(rows, spj_key="a")
    assert data_fingerprint(rows, spj_key=None) == base


@pytest.mark.asyncio
async def test_stream_problem_data_includes_spj_file(client, admin_headers, fake_storage):
    """配置特判程序的数据包：manifest 带 spj 标记并额外下发 spj.cpp；普通题不带。"""
    from app.rpc import judge_jobs

    pid_spj = await _seed_problem_with_case(fake_storage, spj=True)
    async with SessionLocal() as db:
        chunks = {}
        async for path, content in judge_jobs.stream_problem_data(db, uuid_mod.UUID(pid_spj)):
            chunks[path] = chunks.get(path, b"") + content
    manifest = json.loads(chunks["manifest.json"])
    assert manifest["spj"] is True
    assert any(path.endswith(".in") for path in chunks)
    assert any(path == "spj.cpp" and b"return 0" in content for path, content in chunks.items())

    pid_plain = await _seed_problem_with_case(fake_storage)
    async with SessionLocal() as db:
        chunks_plain = {}
        async for path, content in judge_jobs.stream_problem_data(db, uuid_mod.UUID(pid_plain)):
            chunks_plain[path] = chunks_plain.get(path, b"") + content
    manifest_plain = json.loads(chunks_plain["manifest.json"])
    assert manifest_plain["spj"] is False
    assert "spj.cpp" not in chunks_plain


@pytest.mark.asyncio
async def test_stream_problem_data_uses_chunked_object_reader(client, admin_headers, fake_storage, monkeypatch):
    """回归（内存）：流式下发按块读对象，不整对象 get_bytes；同 path 多块按序追加。"""
    from app.rpc import judge_jobs

    pid = await _seed_problem_with_case(fake_storage)
    # 测试数据本体需超过 chunk_size，才能验证同 path 多片按序追加
    for key, (content, content_type) in list(fake_storage.store.items()):
        if key.endswith(".in"):
            fake_storage.store[key] = (b"1234567890\n", content_type)

    async def _forbid_get_bytes(key):
        raise AssertionError("整对象读取不应出现在 FetchProblemData 链路")

    monkeypatch.setattr(fake_storage, "get_bytes", _forbid_get_bytes)
    async with SessionLocal() as db:
        seen: dict[str, list[bytes]] = {}
        async for path, content in judge_jobs.stream_problem_data(
            db, uuid_mod.UUID(pid), chunk_size=4
        ):
            seen.setdefault(path, []).append(content)
    manifest = json.loads(b"".join(seen["manifest.json"]))
    assert manifest["case_count"] == 1 and manifest["spj"] is False
    in_chunks = [parts for path, parts in seen.items() if path.endswith(".in")]
    assert in_chunks and len(in_chunks[0]) > 1
    input_key = next(k for k in fake_storage.store if k.endswith(".in"))
    assert b"".join(in_chunks[0]) == fake_storage.store[input_key][0]


# ---- 排队延迟（pending 无滞留门槛 / 容量释放即派发 / 回收释放锁） ----


@pytest.mark.asyncio
async def test_maintenance_pending_bounded_by_capacity(client, admin_headers, fake_storage):
    """回归（巡检预算）：单节点 capacity=1 时，一轮巡检只投递一个 pending，其余留在队列。"""
    pid = await _seed_problem_with_case(fake_storage)
    uid = uuid_mod.UUID(await _any_user_id())
    sids = []
    async with SessionLocal() as db:
        for _ in range(3):
            sub = Submission(
                user_id=uid, problem_id=uuid_mod.UUID(pid), language="cpp17",
                code="int main(){}", status="pending",
            )
            db.add(sub)
            await db.flush()
            sids.append(sub.id)
        await db.commit()
    conn = _add_node("cap-node", capacity=1)

    await maintenance_once(30)

    jobs = []
    while not conn.outbox.empty():
        jobs.append(conn.outbox.get_nowait())
    assert len(jobs) == 1
    assert jobs[0].job.submission_id in {str(sid) for sid in sids}
    async with SessionLocal() as db:
        statuses = {
            sid: (await db.get(Submission, sid)).status for sid in sids
        }
    assert list(statuses.values()).count("judging") == 1
    assert list(statuses.values()).count("pending") == 2


@pytest.mark.asyncio
async def test_maintenance_stale_reset_consumes_capacity(client, admin_headers, fake_storage):
    """回归（预算顺序）：判死回收优先且复位本身占用容量，本轮不再处理 pending。"""
    pid = await _seed_problem_with_case(fake_storage)
    uid = uuid_mod.UUID(await _any_user_id())
    old = datetime.now(timezone.utc) - timedelta(minutes=10)
    async with SessionLocal() as db:
        stale = Submission(
            user_id=uid, problem_id=uuid_mod.UUID(pid), language="cpp17",
            code="int main(){}", status="judging", updated_at=old,
        )
        pending = Submission(
            user_id=uid, problem_id=uuid_mod.UUID(pid), language="cpp17",
            code="int main(){}", status="pending",
        )
        db.add_all([stale, pending])
        await db.commit()
        stale_id, pending_id = stale.id, pending.id
    conn = _add_node("stale-budget-node", capacity=1)

    await maintenance_once(30)

    msg = await asyncio.wait_for(conn.outbox.get(), timeout=5)
    assert msg.job.submission_id == str(stale_id)
    async with SessionLocal() as db:
        assert (await db.get(Submission, stale_id)).status == "judging"
        assert (await db.get(Submission, pending_id)).status == "pending"
    assert await get_redis().exists(f"judge:requeue:{pending_id}") == 0


@pytest.mark.asyncio
async def test_maintenance_dispatches_fresh_pending_immediately(client, admin_headers, fake_storage):
    """回归（排队下限）：新提交不再等 60s 滞留窗口。

    旧实现巡检候选要求 `updated_at < now-60s`，满载期间新提交至少排队 60s；
    现在 pending 只要节点有空位就派发。
    """
    pid = await _seed_problem_with_case(fake_storage)
    conn = _add_node("fresh-node")
    sid = await _submit(client, admin_headers, pid)
    await asyncio.wait_for(conn.outbox.get(), timeout=5)

    # 模拟「节点满载期间提交滞留」：状态回退 pending，updated_at 保持当前时刻
    async with SessionLocal() as db:
        row = await db.get(Submission, uuid_mod.UUID(sid))
        row.status = "pending"
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
    conn.inflight.discard(sid)
    await get_redis().delete(f"judge:requeue:{sid}")

    await maintenance_once(30)
    msg = await asyncio.wait_for(conn.outbox.get(), timeout=5)
    assert msg.job.submission_id == sid


@pytest.mark.asyncio
async def test_capacity_release_kick_dispatches_pending(client, admin_headers, fake_storage):
    """回归（容量释放即派发）：节点判完腾出容量后踢醒巡检，积压 pending 秒级消化，
    不再等满 30s 扫描周期。"""
    from app.rpc import judge_gateway as gw

    gw._MAINTENANCE_KICK.clear()
    pid = await _seed_problem_with_case(fake_storage)
    sid = await _submit(client, admin_headers, pid)  # 提交时无节点 → pending
    conn = _add_node("release-node")

    task = asyncio.create_task(gw.maintenance_loop(interval=30))
    try:
        await asyncio.sleep(0)  # 让循环进入事件等待
        gw.notify_capacity_released()
        msg = await asyncio.wait_for(conn.outbox.get(), timeout=2)
        assert msg.job.submission_id == sid
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_reset_to_pending_releases_dispatch_lock(client, admin_headers, fake_storage):
    """回归（回收重派）：断线 / 判死回收必须清掉 300s 在途锁，
    否则重置后的 pending 会被残留锁挡回队列。"""
    pid = await _seed_problem_with_case(fake_storage)
    conn = _add_node("relock-node")
    sid = await _submit(client, admin_headers, pid)
    await asyncio.wait_for(conn.outbox.get(), timeout=5)

    lock_key = f"judge:requeue:{sid}"
    await get_redis().set(lock_key, "1", ex=300)
    assert await get_redis().exists(lock_key) == 1

    await _reset_to_pending({sid}, reason="node offline")
    assert await get_redis().exists(lock_key) == 0
    async with SessionLocal() as db:
        assert (await db.get(Submission, uuid_mod.UUID(sid))).status == "pending"


@pytest.mark.asyncio
async def test_result_persist_failure_still_releases_capacity(monkeypatch, fake_storage):
    """回归（容量泄漏）：结果落库异常也必须释放 in-flight 并踢醒巡检，
    否则节点会被网关误判满载，直到 5 分钟判死才恢复。"""
    from app.rpc import judge_gateway as gw

    conn = _add_node("persist-fail", capacity=1)
    sid = str(uuid_mod.uuid4())
    conn.inflight.add(sid)
    gw._MAINTENANCE_KICK.clear()

    async def boom(*_args, **_kwargs):
        raise RuntimeError("storage down")

    monkeypatch.setattr(gw.jobs, "apply_job_result", boom)
    with pytest.raises(RuntimeError):
        await gw._handle_result(judge_pb2.JudgeResult(submission_id=sid, status="accepted"))

    assert sid not in conn.inflight
    assert gw._MAINTENANCE_KICK.is_set()

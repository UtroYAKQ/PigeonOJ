"""用户自测（POST /problems/{id}/run-code）测试。

覆盖：题目可见性 / 语言白名单校验、网关派发与结果回传闭环（模拟节点）、
冷却频控、全局并发上限、无在线节点失败、节点断线簿记清理。
自测不加载测试点、不落库；沙箱真实执行由判题节点容器冒烟验证覆盖。
"""
from __future__ import annotations

import asyncio
import uuid as uuid_mod

import pytest

from app.rpc.gen import judge_pb2
from app.rpc.judge_gateway import (
    REGISTRY,
    GatewayUnavailableError,
    NodeConnection,
    _handle_run_code_result,
    _fail_pending_runs,
    dispatch_run_code,
)
from app.models.problem import Problem
from app.core.database import SessionLocal
from app.core.exceptions import (
    PARAM_FORMAT_INVALID,
    RATE_LIMITED,
    RATE_SEND_TOO_FREQUENT,
    RESOURCE_NOT_FOUND,
    AUTH_FORBIDDEN,
    SYSTEM_UPSTREAM_FAILURE,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    yield
    REGISTRY._connections.clear()


def _add_node(node_id: str, inflight: int = 0, capacity: int = 8) -> NodeConnection:
    conn = NodeConnection(node_id=node_id, name=node_id, capacity=capacity, version="test")
    for i in range(inflight):
        conn.inflight.add(f"fake-{node_id}-{i}")
    REGISTRY.register(conn)
    return conn


async def _seed_problem(status: str = "published", owner: str | None = None, time_limit_ms: int = 1000) -> str:
    """种子题目：自测不依赖测试点，仅需要可见性与限制基准。"""
    from datetime import datetime

    from sqlalchemy import select

    from app.models.user import User

    async with SessionLocal() as db:
        owner_id = uuid_mod.UUID(owner) if owner else (await db.execute(select(User).limit(1))).scalar_one().id
        problem = Problem(title=f"P-{uuid_mod.uuid4().hex[:8]}", description="D",
                          owner_id=owner_id, status=status, visibility="public",
                          time_limit_ms=time_limit_ms,
                          verified_at=datetime.now() if status == "published" else None)
        db.add(problem)
        await db.commit()
        return str(problem.id)


# ---- 服务层校验 ----


@pytest.mark.asyncio
async def test_run_code_problem_not_found(client, user_headers):
    resp = await client.post(
        "/api/v1/problems/00000000-0000-0000-0000-000000000000/run-code",
        json={"language": "python3.12", "code": "print(1)"},
        headers=user_headers,
    )
    assert resp.status_code == 404 and resp.json()["code"] == RESOURCE_NOT_FOUND


@pytest.mark.asyncio
async def test_run_code_rejects_draft_for_regular_user(client, admin_headers, user_headers):
    pid = await _seed_problem(status="draft")
    resp = await client.post(
        f"/api/v1/problems/{pid}/run-code",
        json={"language": "python3.12", "code": "print(1)"},
        headers=user_headers,
    )
    assert resp.status_code == 403 and resp.json()["code"] == AUTH_FORBIDDEN
    # 属主（管理员账号创建）可用
    resp_owner = await client.post(
        f"/api/v1/problems/{pid}/run-code",
        json={"language": "python3.12", "code": "print(1)"},
        headers=admin_headers,
    )
    # 无在线节点：进入派发前已通过校验 → 5001 而非 403
    assert resp_owner.status_code == 502 and resp_owner.json()["code"] == SYSTEM_UPSTREAM_FAILURE


@pytest.mark.asyncio
async def test_run_code_language_whitelist(client, admin_headers):
    pid = await _seed_problem()
    for language in ("ruby", "cpp11"):
        resp = await client.post(
            f"/api/v1/problems/{pid}/run-code",
            json={"language": language, "code": "x"},
            headers=admin_headers,
        )
        assert resp.status_code == 400 and resp.json()["code"] == PARAM_FORMAT_INVALID, language


@pytest.mark.asyncio
async def test_run_code_code_size_limit(client, admin_headers):
    pid = await _seed_problem()
    resp = await client.post(
        f"/api/v1/problems/{pid}/run-code",
        json={"language": "python3.12", "code": "#" * 65537},
        headers=admin_headers,
    )
    assert resp.status_code == 400 and resp.json()["code"] == PARAM_FORMAT_INVALID


# ---- 派发与回传闭环 ----


@pytest.mark.asyncio
async def test_run_code_dispatch_and_result_roundtrip(client, admin_headers):
    conn = _add_node("st-1")
    pid = await _seed_problem(time_limit_ms=800)
    task = asyncio.create_task(client.post(
        f"/api/v1/problems/{pid}/run-code",
        json={"language": "python3.12", "code": "print(input())", "input": "hello\n"},
        headers=admin_headers,
    ))
    msg = await asyncio.wait_for(conn.outbox.get(), timeout=5)
    assert msg.WhichOneof("payload") == "run_code"
    job = msg.run_code
    assert job.language == "python3.12"
    assert job.input == b"hello\n"
    assert job.code == b"print(input())"
    # python3.12 时间比例 3.0 → 有效时间 = 题目基准 × 比例（docs/contracts/judge.md 语言限制换算）
    assert job.limits.time_limit_ms >= 2400

    await _handle_run_code_result(judge_pb2.RunCodeResult(
        request_id=job.request_id, status="ok", output=b"hello\n", time_used_ms=12,
    ))
    resp = await asyncio.wait_for(task, timeout=5)
    body = resp.json()
    assert body["code"] == 0, body
    data = body["data"]
    assert data["status"] == "ok"
    assert data["output"] == "hello\n"
    assert data["time_used_ms"] == 12
    assert not any(m.WhichOneof("payload") == "job" for m in [msg])  # 不与正式判题作业混用


@pytest.mark.asyncio
async def test_run_code_cooldown_blocks_second_request(client, admin_headers):
    conn = _add_node("st-2")
    pid = await _seed_problem()

    async def run() -> object:
        return await client.post(
            f"/api/v1/problems/{pid}/run-code",
            json={"language": "python3.12", "code": "print(1)"},
            headers=admin_headers,
        )

    first = asyncio.create_task(run())
    msg = await asyncio.wait_for(conn.outbox.get(), timeout=5)
    await _handle_run_code_result(judge_pb2.RunCodeResult(request_id=msg.run_code.request_id, status="ok"))
    resp = await asyncio.wait_for(first, timeout=5)
    assert resp.json()["code"] == 0

    second = await run()
    assert second.status_code == 429 and second.json()["code"] == RATE_SEND_TOO_FREQUENT


@pytest.mark.asyncio
async def test_run_code_release_cooldown_on_node_failure(client, admin_headers):
    """派发失败（无在线节点）不占用冷却槽：补上节点后立即可用。"""
    pid = await _seed_problem()
    resp = await client.post(
        f"/api/v1/problems/{pid}/run-code",
        json={"language": "python3.12", "code": "print(1)"},
        headers=admin_headers,
    )
    assert resp.status_code == 502
    _add_node("st-3")
    resp2 = await client.post(
        f"/api/v1/problems/{pid}/run-code",
        json={"language": "python3.12", "code": "print(1)"},
        headers=admin_headers,
    )
    assert resp2.status_code != 429


@pytest.mark.asyncio
async def test_run_code_busy_when_concurrency_full(client, admin_headers):
    _add_node("busy-1", inflight=8, capacity=8)
    pid = await _seed_problem()
    resp = await client.post(
        f"/api/v1/problems/{pid}/run-code",
        json={"language": "python3.12", "code": "print(1)"},
        headers=admin_headers,
    )
    assert resp.status_code == 429 and resp.json()["code"] == RATE_LIMITED


@pytest.mark.asyncio
async def test_dispatch_run_code_without_nodes_raises():
    with pytest.raises(GatewayUnavailableError):
        await dispatch_run_code(
            problem=None, sandbox_config=None, language="python3.12",
            code=b"x", stdin_data=b"", max_concurrent=8,
        )


@pytest.mark.asyncio
async def test_node_disconnect_fails_pending_runs():
    conn = NodeConnection(node_id="st-off", name="n", capacity=1, version="t")
    REGISTRY.register(conn)
    fut = asyncio.get_running_loop().create_future()
    conn.pending_runs["req-x"] = fut
    REGISTRY.unregister(conn)
    _fail_pending_runs(conn, reason="test")
    assert fut.done()
    assert isinstance(fut.exception(), GatewayUnavailableError)


@pytest.mark.asyncio
async def test_run_code_ignores_orphan_result():
    """超时后才回传的结果（Future 已移除）静默丢弃，不抛异常。"""
    conn = NodeConnection(node_id="st-orphan", name="n", capacity=1, version="t")
    REGISTRY.register(conn)
    await _handle_run_code_result(judge_pb2.RunCodeResult(request_id="gone", status="ok"))

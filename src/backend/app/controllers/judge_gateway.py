"""gRPC 判题网关：远程 Judge 节点的注册、派发与结果回收。

- 节点主动出站连接 Connect() 双向流（穿 NAT）；首条消息 Register 携带令牌认证。
- 注册表 REGISTRY 保存每节点的下行队列（asyncio.Queue）与 in-flight 集合；
  心跳桥接写 Redis sandbox:node:<id>，管理后台沙箱状态页自动可见。
- dispatch：负载最低节点优先；作业经 build_job_bundle 构建后推入该节点队列。
- 断线/维护循环回收：in-flight 与超时未完成的提交重置 pending 并重派。
- 派发统计：active_judge_count（原 dispatcher 模块并入本文件）。
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import grpc

from app.settings.config import get_settings
from app.controllers import judge_jobs as jobs
from app.rpc_gen import judge_pb2, judge_pb2_grpc
from app.core.database import SessionLocal
from app.core.redis import get_redis
from app.core.storage import get_storage

logger = logging.getLogger(__name__)

_HEARTBEAT_TTL_SECONDS = 30
_PENDING_RESCAN_SECONDS = 30
_JUDGING_STALE_SECONDS = 5 * 60


async def active_judge_count() -> int:
    """全平台正在判题的任务数（提交并发上限 4002 依据）。"""
    return sum(len(conn.inflight) for conn in REGISTRY.list_nodes())


class NodeConnection:
    def __init__(self, node_id: str, name: str, capacity: int, version: str) -> None:
        self.node_id = node_id
        self.name = name or node_id
        self.capacity = max(1, capacity)
        self.version = version
        self.outbox: asyncio.Queue[judge_pb2.ServerMessage | None] = asyncio.Queue()
        self.inflight: set[str] = set()

    @property
    def load(self) -> float:
        return round(min(1.0, len(self.inflight) / self.capacity), 3)

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.node_id,
            "name": self.name,
            "status": "online",
            "channel": "gateway",
            "load": self.load,
            "cpu_usage": 0,
            "memory_usage": 0,
            "running_tasks": len(self.inflight),
            "capacity": self.capacity,
            "version": self.version,
            "last_heartbeat_at": datetime.now().astimezone().isoformat(),
        }


class GatewayRegistry:
    """连接注册表：仅在 FastAPI 主事件循环内访问。"""

    def __init__(self) -> None:
        self._connections: dict[str, NodeConnection] = {}

    def register(self, conn: NodeConnection) -> None:
        old = self._connections.get(conn.node_id)
        if old is not None and old is not conn:
            # 同 ID 重连：踢掉旧流（其 inflight 移交新连接）
            conn.inflight |= old.inflight
            try:
                old.outbox.put_nowait(None)
            except Exception:  # noqa: BLE001
                pass
        self._connections[conn.node_id] = conn

    def unregister(self, conn: NodeConnection) -> set[str]:
        """注销并返回需要回收的 in-flight 提交 ID。"""
        if self._connections.get(conn.node_id) is conn:
            self._connections.pop(conn.node_id, None)
        return conn.inflight

    def get(self, node_id: str) -> NodeConnection | None:
        return self._connections.get(node_id)

    def list_nodes(self) -> list[NodeConnection]:
        return list(self._connections.values())

    async def redis_heartbeat(self, conn: NodeConnection) -> None:
        await get_redis().set(
            f"sandbox:node:{conn.node_id}",
            json.dumps(conn.to_payload(), ensure_ascii=False),
            ex=_HEARTBEAT_TTL_SECONDS,
        )

    async def remove_heartbeat(self, node_id: str) -> None:
        await get_redis().delete(f"sandbox:node:{node_id}")


REGISTRY = GatewayRegistry()


def _token_ok(token: str) -> bool:
    return bool(get_settings().gateway_tokens) and token in get_settings().gateway_tokens


async def _handle_result(result: judge_pb2.JudgeResult) -> None:
    storage = get_storage()
    payload = {
        "submission_id": result.submission_id,
        "status": result.status,
        "time_used_ms": result.time_used_ms,
        "memory_used_kb": result.memory_used_kb or None,
        "error_message": result.error_message or None,
        "cases": [
            {
                "test_case_id": c.test_case_id,
                "status": c.status,
                "time_used_ms": c.time_used_ms,
                "memory_used_kb": c.memory_used_kb or None,
                "output": c.output,
            }
            for c in result.cases
        ],
    }
    async with SessionLocal() as db:
        applied = await jobs.apply_job_result(db, payload, storage=storage)
        if not applied:
            logger.warning("忽略过期判题结果 submission=%s", result.submission_id)
    conn = _find_conn_by_submission(result.submission_id)
    if conn is not None:
        conn.inflight.discard(result.submission_id)


def _find_conn_by_submission(submission_id: str) -> NodeConnection | None:
    for conn in REGISTRY.list_nodes():
        if submission_id in conn.inflight:
            return conn
    return None


class JudgeGatewayService(judge_pb2_grpc.JudgeGatewayServicer):
    """Connect 双向流：注册 → 下行作业泵 + 上行消息处理。"""

    async def Connect(  # noqa: N802 (gRPC 命名约定)
        self,
        request_iterator: asyncio.Iterator[judge_pb2.NodeMessage],
        context: grpc.aio.ServicerContext,
    ):
        settings = get_settings()
        first = await request_iterator.__anext__()
        if not first.HasField("register") or not _token_ok(first.register.token):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "invalid node token")

        node_id = first.register.node_id or f"{first.register.name or 'node'}-{context.peer()}"
        conn = NodeConnection(
            node_id=node_id,
            name=first.register.name,
            capacity=first.register.capacity or 1,
            version=first.register.version or "",
        )
        REGISTRY.register(conn)
        await REGISTRY.redis_heartbeat(conn)
        logger.info("判题节点上线: %s (capacity=%s)", conn.node_id, conn.capacity)

        yield judge_pb2.ServerMessage(
            ack=judge_pb2.RegisterAck(
                node_id=conn.node_id,
                heartbeat_interval_seconds=settings.judge_heartbeat_interval_seconds,
            )
        )

        incoming = asyncio.create_task(_pump_incoming(request_iterator, context, conn))
        try:
            while True:
                msg = await conn.outbox.get()
                if msg is None:
                    break
                yield msg
        finally:
            incoming.cancel()
            recovered = REGISTRY.unregister(conn)
            await REGISTRY.remove_heartbeat(conn.node_id)
            if recovered:
                await _reset_to_pending(recovered, reason="node offline")
            logger.info("判题节点离线: %s", conn.node_id)

    async def FetchProblemData(  # noqa: N802
        self,
        request: judge_pb2.ProblemDataRequest,
        context: grpc.aio.ServicerContext,
    ):
        token = dict(context.invocation_metadata()).get("x-node-token", "")
        if not _token_ok(token):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "invalid node token")
        problem_id = uuid.UUID(request.problem_id)
        async with SessionLocal() as db:
            async for path, content in jobs.stream_problem_data(db, problem_id):
                yield judge_pb2.FileChunk(path=path, content=content)


async def _pump_incoming(request_iterator, context: grpc.aio.ServicerContext, conn: NodeConnection) -> None:
    try:
        async for msg in request_iterator:
            kind = msg.WhichOneof("payload")
            if kind == "heartbeat":
                await REGISTRY.redis_heartbeat(conn)
            elif kind == "result":
                await _handle_result(msg.result)
    except Exception:  # noqa: BLE001 - 流断开属正常退出路径
        pass


async def send_job(node_id: str, submission_id: uuid.UUID) -> bool:
    """构建作业并推入指定节点的下行队列；返回是否成功。"""
    conn = REGISTRY.get(node_id)
    if conn is None:
        return False
    storage = get_storage()
    sid_str = str(submission_id)
    # 残留簿记清理：重复派发的正确性由 build_job_bundle 的原子认领保证
    conn.inflight.discard(sid_str)
    async with SessionLocal() as db:
        bundle = await jobs.build_job_bundle(db, submission_id, storage=storage)
        if bundle is None:
            return False
        job_msg = judge_pb2.SubmitJob(
            submission_id=bundle["submission_id"],
            language=bundle["language"],
            code=bundle["code"],
            limits=judge_pb2.ResourceLimits(
                time_limit_ms=bundle["limits"].time_limit_ms,
                memory_limit_mb=bundle["limits"].memory_limit_mb,
                output_limit_kb=bundle["limits"].output_limit_kb,
                process_limit=bundle["limits"].process_limit,
                cpu_cores=bundle["limits"].cpu_cores,
            ),
            problem_id=bundle["problem_id"],
            data_version=bundle["data_version"],
            cases=[
                judge_pb2.TestCaseFile(test_case_id=c["test_case_id"], name=c["name"])
                for c in bundle["cases"]
            ],
        )
        conn.outbox.put_nowait(judge_pb2.ServerMessage(job=job_msg))
        conn.inflight.add(sid_str)
        return True


async def _reset_to_pending(submission_ids: set[str], *, reason: str) -> None:
    from sqlalchemy import update

    from app.models.judge import Submission

    ids = [uuid.UUID(s) for s in submission_ids]
    async with SessionLocal() as db:
        await db.execute(
            update(Submission).where(Submission.id.in_(ids), Submission.status == "judging").values(status="pending")
        )
        await db.commit()
    logger.info("回收 %s 个 in-flight 提交（%s）", len(ids), reason)


async def maintenance_loop(interval: int | None = None) -> None:
    """周期巡检：pending 超时未派发 / judging 超时未完成 → 重置并重派。"""
    from sqlalchemy import select, update

    from app.models.judge import Submission

    scan_interval = _PENDING_RESCAN_SECONDS if interval is None else max(0, interval)
    stale_after = timedelta(seconds=scan_interval * 2)
    r = get_redis()
    while True:
        try:
            await asyncio.sleep(scan_interval)
            now = datetime.now()
            async with SessionLocal() as db:
                stale = (
                    await db.execute(
                        select(Submission).where(
                            Submission.status.in_(["pending", "judging"]),
                            Submission.updated_at < now - stale_after,
                        )
                    )
                ).scalars().all()
                for submission in stale:
                    lock_key = f"judge:requeue:{submission.id}"
                    if not await r.set(lock_key, "1", nx=True, ex=_JUDGING_STALE_SECONDS):
                        continue
                    if submission.status == "judging" and submission.updated_at < now - timedelta(seconds=_JUDGING_STALE_SECONDS):
                        await db.execute(
                            update(Submission).where(Submission.id == submission.id).values(status="pending")
                        )
                    await db.commit()
                    if await dispatch_submission(submission.id):
                        logger.info("巡检重派提交 %s", submission.id)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - 巡检失败不影响主流程
            logger.exception("判题巡检循环异常")


async def dispatch_submission(submission_id: uuid.UUID) -> str | None:
    """负载均衡派发：in-flight 最少者优先。无在线节点返回 False（留待巡检）。"""
    nodes = REGISTRY.list_nodes()
    if not nodes:
        return None
    best = min(nodes, key=lambda n: (len(n.inflight), n.node_id))
    if await send_job(best.node_id, submission_id):
        return best.node_id
    return None


async def start_grpc_server() -> grpc.aio.Server | None:
    settings = get_settings()
    if not settings.gateway_tokens:
        logger.warning("未配置 JUDGE_GATEWAY_TOKENS，判题网关不启动")
        return None
    server = grpc.aio.server()
    judge_pb2_grpc.add_JudgeGatewayServicer_to_server(JudgeGatewayService(), server)
    bind = f"{settings.judge_grpc_host}:{settings.judge_grpc_port}"
    server.add_insecure_port(bind)
    await server.start()
    logger.info("判题网关已启动 %s", bind)
    return server


__all__ = [
    "REGISTRY",
    "JudgeGatewayService",
    "dispatch_submission",
    "maintenance_loop",
    "start_grpc_server",
]

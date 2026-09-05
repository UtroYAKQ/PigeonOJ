"""gRPC 判题网关：远程 Judge 节点的注册、派发与结果回收。

- 节点主动出站连接 Connect() 双向流（穿 NAT）；首条消息 Register 携带令牌认证。
- 注册表 REGISTRY 保存每节点的下行队列（asyncio.Queue）与 in-flight 集合；
  心跳桥接写 Redis sandbox:node:<id>，管理后台沙箱状态页自动可见。
- dispatch：负载最低节点优先；判题作业经 build_job_bundle 构建后推入该节点队列，
  用户自测经 dispatch_run_code 挂 pending Future 等待节点沿流回传。
- 断线/维护循环回收：in-flight 与超时未完成的提交重置 pending 并重派；自测请求即时置错。
- 派发统计：active_judge_count（原 dispatcher 模块并入本文件）。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

import grpc

from app.enums import SubmissionStatus
from app.schemas.admin import SandboxNodeOut
from app.settings.config import get_settings
from app.rpc import judge_jobs as jobs
from app.rpc.gen import judge_pb2, judge_pb2_grpc
from app.core.database import SessionLocal
from app.core.redis import SANDBOX_NODE_KEY_PREFIX, get_redis
from app.core.storage import get_storage

logger = logging.getLogger(__name__)

_HEARTBEAT_TTL_SECONDS = 30
_PENDING_RESCAN_SECONDS = 30
_JUDGING_STALE_SECONDS = 5 * 60
# 用户自测整链路兜底超时（> 节点侧编译+运行最大预算；到期未回传视为节点故障）
_RUN_TIMEOUT_SECONDS = 120
# 心跳指标钳制边界（节点上报 0-100 百分比，越界值写 Redis 前收敛）
_METRIC_PERCENT_MIN = 0
_METRIC_PERCENT_MAX = 100
# 巡检滞留判定倍数：连续 N 个扫描周期无更新才纳入巡检候选（避免误判在途提交）
_STALE_SCAN_MULTIPLIER = 2
# FetchProblemData 的认证 metadata 键（与判题节点 daemon 约定一致）
_NODE_TOKEN_METADATA_KEY = "x-node-token"
# 心跳状态值（写 Redis 供管理后台沙箱页展示）
_NODE_STATUS_ONLINE = "online"
_CHANNEL_GATEWAY = "gateway"
# 维护循环重派互斥锁键前缀（docs/operations.md Redis 约定）
_REQUEUE_LOCK_PREFIX = "judge:requeue:"
# 重派锁 TTL：派发成功后在途保护（与 judging 判死阈值一致，防长作业被频繁重置）；
# 派发失败仅短 TTL 冷却（一个扫描周期量级），不冻结积压
_REQUEUE_LOCK_TTL_SECONDS = _JUDGING_STALE_SECONDS
_REQUEUE_RETRY_TTL_SECONDS = 60

# 节点注册/重连踢醒事件：巡检循环立即消化积压，免等扫描周期
# （断线→重连后积压提交秒级重派，修复「节点上线了题还在排队」）
_MAINTENANCE_KICK = asyncio.Event()


async def active_judge_count() -> int:
    """全平台正在执行的任务数（提交判题 + 用户自测；提交并发上限 4002 依据）。"""
    return sum(len(conn.inflight) + len(conn.pending_runs) for conn in _live_nodes())


def _live_nodes() -> list[NodeConnection]:
    """参与派发与并发统计的节点：注册表中有连接且上行流近期有消息。

    防僵尸连接：上行泵死亡或节点 hang 死时心跳停流，若仅凭注册表派发，
    任务会派给永远回不来结果的节点；判活阈值与心跳 Redis TTL（管理页可见性）对齐。
    """
    return [conn for conn in REGISTRY.list_nodes() if not conn.is_stale()]


class GatewayUnavailableError(RuntimeError):
    """无在线判题节点 / 节点在作业派发后断线。"""


class GatewayBusyError(RuntimeError):
    """全局执行并发上限已达。"""


class GatewayTimeoutError(RuntimeError):
    """自测任务超时未回传（节点侧无响应）。"""


class NodeConnection:
    def __init__(self, node_id: str, name: str, capacity: int, version: str) -> None:
        self.node_id = node_id
        self.name = name or node_id
        self.capacity = max(1, capacity)
        self.version = version
        self.outbox: asyncio.Queue[judge_pb2.ServerMessage | None] = asyncio.Queue()
        # 正式判题 in-flight（submission_id 字符串）；自测任务另有 pending_runs，不与提交混用命名空间
        self.inflight: set[str] = set()
        # 自测 pending：request_id → Future；节点断线时统一置错
        self.pending_runs: dict[str, asyncio.Future] = {}
        # 节点宿主指标（心跳上报；未上报前为 0）
        self.cpu_usage = 0
        self.memory_usage = 0
        # 最近一次收到上行消息的时刻（monotonic 秒 + UTC 墙钟）：判活与管理页 last_heartbeat_at 依据
        self.last_seen = time.monotonic()
        self.last_seen_at = datetime.now(timezone.utc)

    def touch(self) -> None:
        """收到任一上行消息（心跳 / 判题结果 / 自测结果）时刷新活跃时刻。"""
        self.last_seen = time.monotonic()
        self.last_seen_at = datetime.now(timezone.utc)

    def is_stale(self) -> bool:
        """连续 max(2×心跳间隔, 心跳 TTL) 未收到上行消息 → 判为僵死，不参与派发。"""
        interval = max(1, get_settings().judge_heartbeat_interval_seconds)
        return (time.monotonic() - self.last_seen) > max(_HEARTBEAT_TTL_SECONDS, 2 * interval)

    @property
    def task_count(self) -> int:
        """节点当前承担的任务数（判题 + 自测），负载均衡与并发统计共用。"""
        return len(self.inflight) + len(self.pending_runs)

    @property
    def load(self) -> float:
        return round(min(1.0, self.task_count / self.capacity), 3)

    def to_payload(self) -> SandboxNodeOut:
        """节点热状态 → 管理端契约模型（键以 SandboxNodeOut 为唯一来源）。"""
        return SandboxNodeOut(
            id=self.node_id,
            name=self.name,
            status=_NODE_STATUS_ONLINE,
            channel=_CHANNEL_GATEWAY,
            load=self.load,
            cpu_usage=self.cpu_usage,
            memory_usage=self.memory_usage,
            running_tasks=self.task_count,
            capacity=self.capacity,
            version=self.version,
            # 显式 UTC（aware），序列化带 +00:00 偏移；前端 formatDateTime 直接解析。
            # 取真实最近活跃时刻，而非写入瞬间的 now（否则管理页永远显示"刚刚"）
            last_heartbeat_at=self.last_seen_at.isoformat(),
        )


class GatewayRegistry:
    """连接注册表：仅在 FastAPI 主事件循环内访问。"""

    def __init__(self) -> None:
        self._connections: dict[str, NodeConnection] = {}

    def register(self, conn: NodeConnection) -> None:
        old = self._connections.get(conn.node_id)
        if old is not None and old is not conn:
            # 同 ID 重连：踢掉旧流（其 inflight 移交新连接后立即清空）——
            # 旧连接的生成器可能长时间悬挂在半开 TCP 的 yield 上，若不清空，
            # 其迟到 finally 会经 unregister 拿到这批 ID，把新连接正在判的提交重置回 pending
            conn.inflight |= old.inflight
            old.inflight.clear()
            try:
                old.outbox.put_nowait(None)
            except Exception:  # noqa: BLE001
                pass
        self._connections[conn.node_id] = conn

    def unregister(self, conn: NodeConnection) -> set[str]:
        """注销并返回需要回收的 in-flight 提交 ID。

        仅当 conn 仍是该 ID 的注册连接时才回收：同 ID 重连后，旧（僵尸）连接的
        迟到清理必须视为空——in-flight 已移交新连接，重置/删心跳都会破坏新连接的在途作业。
        """
        if self._connections.get(conn.node_id) is conn:
            self._connections.pop(conn.node_id, None)
            return conn.inflight
        return set()

    def get(self, node_id: str) -> NodeConnection | None:
        return self._connections.get(node_id)

    def list_nodes(self) -> list[NodeConnection]:
        return list(self._connections.values())

    async def redis_heartbeat(self, conn: NodeConnection) -> None:
        await get_redis().set(
            f"{SANDBOX_NODE_KEY_PREFIX}{conn.node_id}",
            json.dumps(conn.to_payload().model_dump(mode="json"), ensure_ascii=False),
            ex=_HEARTBEAT_TTL_SECONDS,
        )

    async def remove_heartbeat(self, node_id: str) -> None:
        await get_redis().delete(f"{SANDBOX_NODE_KEY_PREFIX}{node_id}")


REGISTRY = GatewayRegistry()


def _token_ok(token: str) -> bool:
    return bool(get_settings().gateway_tokens) and token in get_settings().gateway_tokens


def _to_outcome(result: judge_pb2.JudgeResult) -> jobs.JudgeOutcome:
    """proto 回传消息 → 落库入参（字段一一对应，空串回退由 apply_job_result 兜底）。"""
    return jobs.JudgeOutcome(
        submission_id=result.submission_id,
        status=result.status,
        time_used_ms=result.time_used_ms,
        memory_used_kb=result.memory_used_kb or None,
        error_message=result.error_message or None,
        cases=tuple(
            jobs.CaseOutcome(
                test_case_id=c.test_case_id,
                status=c.status,
                time_used_ms=c.time_used_ms,
                memory_used_kb=c.memory_used_kb or None,
                output=c.output,
            )
            for c in result.cases
        ),
    )


async def _handle_result(result: judge_pb2.JudgeResult) -> None:
    storage = get_storage()
    async with SessionLocal() as db:
        applied = await jobs.apply_job_result(db, _to_outcome(result), storage=storage)
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


def _to_run_outcome(result: judge_pb2.RunCodeResult) -> jobs.RunCodeOutcome:
    return jobs.RunCodeOutcome(
        request_id=result.request_id,
        status=result.status or SubmissionStatus.SYSTEM_ERROR,
        output=result.output or b"",
        error_message=result.error_message or None,
        time_used_ms=result.time_used_ms,
        memory_used_kb=result.memory_used_kb or None,
    )


async def _handle_run_code_result(result: judge_pb2.RunCodeResult) -> None:
    """按 request_id 关联唤醒等待方；无人认领（等待已超时/断开）则静默丢弃。"""
    for conn in REGISTRY.list_nodes():
        fut = conn.pending_runs.get(result.request_id)
        if fut is not None and not fut.done():
            fut.set_result(_to_run_outcome(result))
            return


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
        # 节点上线/重连：立即唤醒巡检消化积压（含断线期间滞留的 pending 提交）
        _MAINTENANCE_KICK.set()

        yield judge_pb2.ServerMessage(
            ack=judge_pb2.RegisterAck(
                node_id=conn.node_id,
                heartbeat_interval_seconds=settings.judge_heartbeat_interval_seconds,
            )
        )

        incoming = asyncio.create_task(_pump_incoming(request_iterator, context, conn))
        _attach_pump_watchdog(incoming, conn)
        try:
            while True:
                msg = await conn.outbox.get()
                if msg is None:
                    break
                yield msg
        finally:
            incoming.cancel()
            recovered = REGISTRY.unregister(conn)
            _fail_pending_runs(conn, reason="node offline")
            if recovered:
                # 仅本连接仍是注册连接时才回收（同 ID 重连后旧连接的迟到清理不再越权）
                await REGISTRY.remove_heartbeat(conn.node_id)
                await _reset_to_pending(recovered, reason="node offline")
            logger.info("判题节点离线: %s", conn.node_id)

    async def FetchProblemData(  # noqa: N802
        self,
        request: judge_pb2.ProblemDataRequest,
        context: grpc.aio.ServicerContext,
    ):
        token = dict(context.invocation_metadata()).get(_NODE_TOKEN_METADATA_KEY, "")
        if not _token_ok(token):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "invalid node token")
        problem_id = uuid.UUID(request.problem_id)
        async with SessionLocal() as db:
            async for path, content in jobs.stream_problem_data(
                db, problem_id, requested_version=request.data_version or None
            ):
                yield judge_pb2.FileChunk(path=path, content=content)


def _attach_pump_watchdog(incoming: asyncio.Task, conn: NodeConnection) -> None:
    """上行泵退出（流断开/异常）→ 向下行队列塞 None 哨兵，令 Connect 主循环退出
    并走 finally 清理（注销、自测置错、删心跳 key、重派 in-flight）。

    若没有这道联动，上行泵死亡后下行派发泵仍在空转：任务照常派给节点、
    结果却永远回不来，连接变成只有离线日志都没有的「僵尸连接」。
    """

    def _on_pump_done(task: asyncio.Task) -> None:
        if not task.cancelled():
            task.exception()  # 取出异常，避免 "Task exception was never retrieved" 告警
        try:
            conn.outbox.put_nowait(None)
        except Exception:  # noqa: BLE001 - 队列极端异常时放弃（连接随后由对端清理兜底）
            pass

    incoming.add_done_callback(_on_pump_done)


async def _pump_incoming(request_iterator, context: grpc.aio.ServicerContext, conn: NodeConnection) -> None:
    """上行消息泵：心跳桥接 Redis / 判题结果落库 / 自测结果唤醒等待方。

    单条消息处理失败（Redis、DB 瞬断等基础设施抖动）只记日志并跳过，不终止泵——
    否则一次抖动就杀掉上行流，心跳停写、结果丢失，而下行派发仍在继续。
    仅当流本身断开（EOF / 传输层错误）才退出，退出后由 watchdog 触发连接清理。
    """
    try:
        async for msg in request_iterator:
            conn.touch()
            kind = msg.WhichOneof("payload")
            try:
                if kind == "heartbeat":
                    conn.cpu_usage = max(_METRIC_PERCENT_MIN, min(_METRIC_PERCENT_MAX, msg.heartbeat.cpu_usage))
                    conn.memory_usage = max(_METRIC_PERCENT_MIN, min(_METRIC_PERCENT_MAX, msg.heartbeat.memory_usage))
                    await REGISTRY.redis_heartbeat(conn)
                elif kind == "result":
                    await _handle_result(msg.result)
                elif kind == "run_code_result":
                    await _handle_run_code_result(msg.run_code_result)
            except Exception:  # noqa: BLE001 - 单条消息失败不终止流，保住连接活性
                logger.exception("节点 %s 上行消息处理失败（kind=%s），跳过该消息", conn.node_id, kind)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 - 上行流断开（正常断线路径），记日志后退出
        logger.warning("节点 %s 上行流断开，触发连接清理", conn.node_id, exc_info=True)


async def send_job(node_id: str, submission_id: uuid.UUID) -> bool:
    """构建作业并推入指定节点的下行队列；返回是否成功。"""
    conn = REGISTRY.get(node_id)
    if conn is None:
        return False
    sid_str = str(submission_id)
    # 残留簿记清理：重复派发的正确性由 build_job_bundle 的原子认领保证
    conn.inflight.discard(sid_str)
    async with SessionLocal() as db:
        bundle = await jobs.build_job_bundle(db, submission_id)
        if bundle is None:
            return False
        job_msg = judge_pb2.SubmitJob(
            submission_id=bundle.submission_id,
            language=bundle.language,
            code=bundle.code,
            limits=judge_pb2.ResourceLimits(
                time_limit_ms=bundle.limits.time_limit_ms,
                memory_limit_mb=bundle.limits.memory_limit_mb,
                output_limit_kb=bundle.limits.output_limit_kb,
                process_limit=bundle.limits.process_limit,
                cpu_cores=bundle.limits.cpu_cores,
            ),
            problem_id=bundle.problem_id,
            data_version=bundle.data_version,
            stop_on_failure=bundle.stop_on_failure,
            cases=[
                judge_pb2.TestCaseFile(test_case_id=c.test_case_id, name=c.name)
                for c in bundle.cases
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
        # updated_at 同步刷新为状态变更时刻：巡检的「滞留」判定以它为基准，
        # 若停留在创建时间，断线回收后的重派门槛与实际滞留时长脱节
        await db.execute(
            update(Submission)
            .where(Submission.id.in_(ids), Submission.status == SubmissionStatus.JUDGING)
            .values(status=SubmissionStatus.PENDING, updated_at=datetime.now(timezone.utc))
        )
        await db.commit()
    logger.info("回收 %s 个 in-flight 提交（%s）", len(ids), reason)


async def maintenance_once(scan_interval: int, now: datetime | None = None) -> None:
    """单轮巡检（maintenance_loop 循环体，独立成函数便于测试注入）：
    重置超时未完成的 judging、重派滞留的 pending / judging 提交。"""
    from sqlalchemy import select, update

    from app.models.judge import Submission

    stale_after = timedelta(seconds=scan_interval * _STALE_SCAN_MULTIPLIER)
    now = now or datetime.now(timezone.utc)
    r = get_redis()
    async with SessionLocal() as db:
        stale = (
            await db.execute(
                select(Submission).where(
                    Submission.status.in_([SubmissionStatus.PENDING, SubmissionStatus.JUDGING]),
                    Submission.updated_at < now - stale_after,
                )
            )
        ).scalars().all()
        for submission in stale:
            lock_key = f"{_REQUEUE_LOCK_PREFIX}{submission.id}"
            # 先以短 TTL 上锁防同轮重复处理；派发成功后再升级为在途保护窗。
            # 失败（无在线节点等）只冷却一个扫描周期量级——不冻结积压，
            # 节点恢复后下一轮即可重派（修复断线期烧锁导致恢复后仍长时间排队）
            if not await r.set(lock_key, "1", nx=True, ex=_REQUEUE_RETRY_TTL_SECONDS):
                continue
            if (
                submission.status == SubmissionStatus.JUDGING
                and submission.updated_at < now - timedelta(seconds=_JUDGING_STALE_SECONDS)
            ):
                await db.execute(
                    update(Submission)
                    .where(Submission.id == submission.id)
                    .values(status=SubmissionStatus.PENDING, updated_at=now)
                )
            await db.commit()
            if await dispatch_submission(submission.id):
                logger.info("巡检重派提交 %s", submission.id)
                await r.set(lock_key, "1", ex=_REQUEUE_LOCK_TTL_SECONDS)


async def maintenance_loop(interval: int | None = None) -> None:
    """周期巡检：pending 超时未派发 / judging 超时未完成 → 重置并重派。

    节点注册（含断线重连）会 set 踢醒事件，积压立即消化、不等扫描周期。
    """
    scan_interval = _PENDING_RESCAN_SECONDS if interval is None else max(0, interval)
    while True:
        try:
            try:
                await asyncio.wait_for(_MAINTENANCE_KICK.wait(), timeout=scan_interval)
            except asyncio.TimeoutError:
                pass
            _MAINTENANCE_KICK.clear()
            await maintenance_once(scan_interval)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - 巡检失败不影响主流程
            logger.exception("判题巡检循环异常")


async def dispatch_submission(submission_id: uuid.UUID) -> str | None:
    """负载均衡派发：任务数（判题 + 自测）最少者优先。无在线节点返回 None（留待巡检）。"""
    nodes = _live_nodes()
    if not nodes:
        return None
    best = min(nodes, key=lambda n: (n.task_count, n.node_id))
    if await send_job(best.node_id, submission_id):
        return best.node_id
    return None


def _fail_pending_runs(conn: NodeConnection, *, reason: str) -> None:
    """节点断线 / 重连：该连接名下未完成的自测请求全部置错，等待方立即失败。"""
    for fut in conn.pending_runs.values():
        if not fut.done():
            fut.set_exception(GatewayUnavailableError(f"node offline: {reason}"))
    conn.pending_runs.clear()


async def dispatch_run_code(
    *,
    problem,
    sandbox_config,
    language: str,
    code: bytes,
    stdin_data: bytes,
    max_concurrent: int,
) -> jobs.RunCodeOutcome:
    """用户自测派发（docs/contracts/judge.md「用户自测」）：

    - 负载最低节点优先；作业不落库，等待节点沿流回传 RunCodeResult。
    - 无在线节点 / 并发上限已满 → 立即失败；整链路超时兜底 _RUN_TIMEOUT_SECONDS。
    - 节点断线时 pending Future 被置错，等待方即时感知。

    运行限制按语言比例换算（基准取题目 time_limit_ms / memory_limit_mb），
    编译预算由节点侧按运行限制独立推导（与正式判题一致）。
    """
    nodes = _live_nodes()
    if not nodes:
        raise GatewayUnavailableError("no judge node online")
    if await active_judge_count() >= max_concurrent:
        raise GatewayBusyError("judge concurrency limit reached")

    limits, _compile_limits = jobs.resolve_limits(problem, sandbox_config)
    request_id = uuid.uuid4().hex
    best = min(nodes, key=lambda n: (n.task_count, n.node_id))
    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    best.pending_runs[request_id] = fut
    try:
        best.outbox.put_nowait(judge_pb2.ServerMessage(run_code=judge_pb2.RunCodeJob(
            request_id=request_id,
            language=language,
            code=code,
            input=stdin_data,
            limits=judge_pb2.ResourceLimits(
                time_limit_ms=limits.time_limit_ms,
                memory_limit_mb=limits.memory_limit_mb,
                output_limit_kb=limits.output_limit_kb,
                process_limit=limits.process_limit,
                cpu_cores=limits.cpu_cores,
            ),
        )))
        try:
            return await asyncio.wait_for(fut, timeout=_RUN_TIMEOUT_SECONDS)
        except asyncio.TimeoutError as exc:
            raise GatewayTimeoutError("selftest result timeout") from exc
    finally:
        best.pending_runs.pop(request_id, None)


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
    "dispatch_run_code",
    "maintenance_loop",
    "start_grpc_server",
]

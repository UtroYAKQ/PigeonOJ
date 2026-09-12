"""PigeonOJ 判题节点守护进程。

- 主动出站连接后端 gRPC 网关（穿 NAT，无需开放入站端口）
- 注册认证 → 接收 SubmitJob → 拉取/命中题目数据缓存 → nsjail 判题 → 回传结果
- capacity 并发（asyncio.Semaphore），心跳按间隔上行

用法：python daemon.py --config node.toml
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path

import grpc

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import JudgeNodeConfig, load_config  # noqa: E402
from datacache import ProblemDataCache  # noqa: E402
from executor import JudgeCase, JudgeWorker, NsjailExecutor, ResourceLimits  # noqa: E402
from gen import judge_pb2, judge_pb2_grpc  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("judge-node")

# 与后端 app/rpc/judge_gateway._GRPC_MAX_MESSAGE_BYTES 对齐
# （测试点 ≤8MB，默认输出 5MB×N；gRPC 默认 4MB 会卡死 Connect / FetchProblemData）
_GRPC_MAX_MESSAGE_BYTES = 128 * 1024 * 1024
_GRPC_CHANNEL_OPTIONS = (
    ("grpc.max_send_message_length", _GRPC_MAX_MESSAGE_BYTES),
    ("grpc.max_receive_message_length", _GRPC_MAX_MESSAGE_BYTES),
)


def classify_gateway_error(*, code: str = "", details: str = "", text: str = "") -> tuple[str, str]:
    """把 gRPC / 传输失败收成管理页可读原因：(code, message)。"""
    blob = f"{code} {details} {text}".lower()
    if "unauthenticated" in blob or "invalid node token" in blob or "invalid token" in blob:
        return "token", "令牌错误：与后端 JUDGE_GATEWAY_TOKENS 不一致"
    if any(k in blob for k in ("ssl", "tls", "handshake", "certificate", "wrong_version_number", "cert")):
        return "tls", "TLS 握手失败：本机明文网关不要勾 TLS；公网请检查证书"
    if any(k in blob for k in (
        "unavailable", "connection refused", "failed to connect",
        "name resolution", "dns", "timed out", "timeout",
        "network is unreachable", "no route to host",
    )):
        return "unreachable", "后端网关未在监听，或地址/端口不对"
    if "cancel" in blob:
        return "cancelled", "连接被关闭（若反复出现，先测连通并核对令牌）"
    msg = (details or text or code or "未知错误").strip()
    return "unknown", f"连接失败：{msg}"


def aggregate_status(statuses: list[str]) -> str:
    if not statuses:
        return "system_error"
    for s in ("compile_error", "system_error", "time_limit_exceeded",
              "memory_limit_exceeded", "output_limit_exceeded", "runtime_error", "wrong_answer"):
        if s in statuses:
            return s
    return "accepted" if all(x == "accepted" for x in statuses) else "system_error"


def read_cpu_times(path: str = "/proc/stat") -> tuple[int, int] | None:
    """读 /proc/stat 首行，返回 (idle, total) 累加计数；非 Linux / 读取失败返回 None。"""
    try:
        with open(path, "r", encoding="ascii") as f:
            line = f.readline()
    except OSError:
        return None
    if not line.startswith("cpu "):
        return None
    try:
        fields = [int(x) for x in line.split()[1:]]
    except ValueError:
        return None
    if len(fields) < 4:
        return None
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)  # idle + iowait
    return idle, sum(fields)


def read_memory_usage(path: str = "/proc/meminfo") -> int | None:
    """读 /proc/meminfo，返回内存使用率（0-100）；无 MemAvailable 时按 MemFree+Buffers+Cached 估算。"""
    total = available = free = buffers = cached = None
    try:
        with open(path, "r", encoding="ascii") as f:
            for raw in f:
                if raw.startswith("MemTotal:"):
                    total = int(raw.split()[1])
                elif raw.startswith("MemAvailable:"):
                    available = int(raw.split()[1])
                elif raw.startswith("MemFree:"):
                    free = int(raw.split()[1])
                elif raw.startswith("Buffers:"):
                    buffers = int(raw.split()[1])
                elif raw.startswith("Cached:"):
                    cached = int(raw.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    if not total:
        return None
    if available is not None:
        used = total - available
    else:
        used = total - (free or 0) - (buffers or 0) - (cached or 0)
    return max(0, min(100, round(used * 100 / total)))


class NodeDaemon:
    def __init__(self, cfg: JudgeNodeConfig) -> None:
        self.cfg = cfg
        self.node_id = cfg.node.id or f"{socket.gethostname()}-{os.getpid()}"
        self.outbox: asyncio.Queue[judge_pb2.NodeMessage] = asyncio.Queue()
        self.cache = ProblemDataCache(Path(cfg.paths.data_cache))
        # 节点固定运行在 Linux 容器内：nsjail 原生执行，无 Docker 包装分支
        self.executor = JudgeWorker(
            NsjailExecutor(cfg.sandbox.nsjail_binary, cfg.sandbox.nsjail_config),
            cfg.paths.workspace,
        )
        self.semaphore: asyncio.Semaphore | None = None
        self.running_tasks = 0
        # 持有判题任务引用，防止 fire-and-forget 任务被 GC 中途回收
        self._pending: set[asyncio.Task] = set()
        self.heartbeat_interval = 10
        self.cpu_sample: tuple[int, int] | None = None  # (idle, total) 上次 /proc/stat 采样
        self._cancels: dict[str, threading.Event] = {}
        self.registered = False
        self.reconnect_requested = False
        self.connection_state = "disconnected"
        self.last_error_code = ""
        self.last_error = ""
        self._had_connection = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._channel = None

    def request_reconnect(self) -> None:
        self.reconnect_requested = True
        self.connection_state = "reconnecting"
        channel = self._channel
        loop = self._loop
        if channel is None or loop is None or loop.is_closed():
            return
        try:
            asyncio.run_coroutine_threadsafe(channel.close(), loop)
        except RuntimeError:
            pass

    def record_gateway_error(self, exc: BaseException) -> None:
        code = ""
        details = ""
        if isinstance(exc, grpc.aio.AioRpcError):
            try:
                code = exc.code().name
            except Exception:
                code = ""
            details = exc.details() or ""
        new_code, new_msg = classify_gateway_error(code=code, details=details, text=str(exc))
        if self.last_error_code == "token" and new_code in {"cancelled", "unknown"}:
            return
        self.last_error_code = new_code
        self.last_error = new_msg

    async def run(self) -> None:
        cfg = self.cfg
        self._loop = asyncio.get_running_loop()
        was_reconnect = self.reconnect_requested or self._had_connection
        self.reconnect_requested = False
        self.registered = False
        self.connection_state = "reconnecting" if was_reconnect else "connecting"
        self.semaphore = asyncio.Semaphore(max(1, cfg.node.capacity))
        if cfg.server.tls:
            # TLS 模式：连公网域名 443（nginx grpc_pass 按服务路径转发到网关），
            # Let's Encrypt 等公共证书在 gRPC 默认根证书信任链内
            channel = grpc.aio.secure_channel(
                cfg.server.address, grpc.ssl_channel_credentials(), options=_GRPC_CHANNEL_OPTIONS
            )
        else:
            channel = grpc.aio.insecure_channel(cfg.server.address, options=_GRPC_CHANNEL_OPTIONS)
        self._channel = channel
        stub = judge_pb2_grpc.JudgeGatewayStub(channel)

        async def outgoing():
            yield judge_pb2.NodeMessage(register=judge_pb2.Register(
                token=cfg.server.token,
                node_id=self.node_id,
                name=cfg.node.name or self.node_id,
                capacity=cfg.node.capacity,
                version="nsjail-node-1.3",
                supports_spj=True,
            ))
            while True:
                msg = await self.outbox.get()
                yield msg

        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        cache_gc_task = asyncio.create_task(self._cache_gc_loop())
        log.info("连接后端 %s（节点 %s）...", cfg.server.address, self.node_id)
        responses = stub.Connect(outgoing())
        try:
            registered = False
            async for sm in responses:
                if not registered:
                    assert sm.WhichOneof("payload") == "ack"
                    self.heartbeat_interval = max(3, sm.ack.heartbeat_interval_seconds)
                    log.info("注册成功：%s（心跳间隔 %ss）", sm.ack.node_id, self.heartbeat_interval)
                    registered = True
                    self.registered = True
                    self._had_connection = True
                    self.connection_state = "connected"
                    self.last_error_code = ""
                    self.last_error = ""
                    continue
                kind = sm.WhichOneof("payload")
                if kind == "job":
                    self._spawn(self._execute_job(stub, sm.job))
                elif kind == "run_code":
                    self._spawn(self._execute_run_code(sm.run_code))
                elif kind == "cancel":
                    ev = self._cancels.get(sm.cancel.submission_id)
                    if ev is not None:
                        ev.set()
        except grpc.aio.AioRpcError as exc:
            self.record_gateway_error(exc)
        except asyncio.CancelledError as exc:
            self.record_gateway_error(exc)
            raise
        finally:
            heartbeat_task.cancel()
            cache_gc_task.cancel()
            self.registered = False
            self._channel = None
            if self.reconnect_requested or self._had_connection:
                self.connection_state = "reconnecting"
            else:
                self.connection_state = "disconnected"
            await channel.close()
            log.info("连接关闭")

    def _spawn(self, coro) -> None:
        """创建判题任务并保存引用（done 后自动清除，docs/architecture.md 异步规范）。"""
        task = asyncio.create_task(coro)
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _heartbeat_loop(self) -> None:
        interval = max(3, self.heartbeat_interval)
        while True:
            await self.outbox.put(judge_pb2.NodeMessage(heartbeat=judge_pb2.Heartbeat(
                running_tasks=self.running_tasks,
                cpu_usage=self._cpu_usage(),
                memory_usage=self._memory_usage(),
            )))
            await asyncio.sleep(interval)

    def _cpu_usage(self) -> int:
        """宿主 CPU 使用率（0-100）：按两次心跳间的 /proc/stat 增量计算；无基线/非 Linux 返回 0。"""
        sample = read_cpu_times()
        if sample is None:
            return 0
        idle, total = sample
        prev = self.cpu_sample
        self.cpu_sample = sample
        if prev is None:
            return 0
        delta_total = total - prev[1]
        if delta_total <= 0:
            return 0
        return max(0, min(100, round((delta_total - (idle - prev[0])) * 100 / delta_total)))

    def _memory_usage(self) -> int:
        return read_memory_usage() or 0

    async def _cache_gc_loop(self) -> None:
        """定时巡检缓存总量，超限则按 LRU 回收（max_mb<=0 表示不启用）。"""
        max_bytes = int(self.cfg.cache.max_mb) * 1024 * 1024
        if max_bytes <= 0:
            return
        interval = max(60, int(self.cfg.cache.gc_interval_seconds))
        while True:
            await asyncio.sleep(interval)
            try:
                removed = await asyncio.to_thread(self.cache.collect, max_bytes)
                if removed:
                    total_mb = await asyncio.to_thread(lambda: round(self.cache.total_size() / 1048576, 1))
                    log.info("缓存回收 %d 个目录，剩余 %.1fMB", len(removed), total_mb)
            except Exception:  # noqa: BLE001 - 回收失败不影响判题
                log.warning("缓存回收失败", exc_info=True)

    async def _ensure_data(self, stub, job: judge_pb2.SubmitJob) -> Path:
        if not self.cache.has(job.problem_id, job.data_version):
            metadata = (("x-node-token", self.cfg.server.token),)
            call = stub.FetchProblemData(
                judge_pb2.ProblemDataRequest(problem_id=job.problem_id, data_version=job.data_version),
                metadata=metadata,
            )
            await self.cache.sync(job.problem_id, job.data_version, call)
        return self.cache.dir_for(job.problem_id, job.data_version)

    async def _execute_job(self, stub, job: judge_pb2.SubmitJob) -> None:
        cancel = threading.Event()
        self._cancels[job.submission_id] = cancel
        async with self.semaphore:
            self.running_tasks += 1
            try:
                if cancel.is_set():
                    log.info("作业取消（未开始）%s", job.submission_id)
                    return
                result = await self._execute_inner(stub, job, cancel)
                if cancel.is_set():
                    log.info("作业取消 %s", job.submission_id)
                    return
            except Exception as exc:  # noqa: BLE001 - 节点侧故障以 system_error 回传
                log.exception("作业执行异常 submission=%s", job.submission_id)
                if cancel.is_set():
                    return
                result = {
                    "submission_id": job.submission_id, "status": "system_error",
                    "error_message": f"node error: {exc}"[:2000], "cases": [],
                }
            finally:
                self.running_tasks -= 1
                self._cancels.pop(job.submission_id, None)
            await self.outbox.put(_to_result_message(result))
            log.info("判题完成 %s → %s (score=%s)", job.submission_id, result["status"], result.get("score"))

    async def _execute_inner(self, stub, job: judge_pb2.SubmitJob, cancel: threading.Event | None = None) -> dict:
        data_dir = await self._ensure_data(stub, job)
        self.cache.mark_in_use(data_dir.name)
        try:
            return await self._judge_with_data(job, data_dir, cancel)
        finally:
            self.cache.unmark_in_use(data_dir.name)

    async def _judge_with_data(
        self, job: judge_pb2.SubmitJob, data_dir: Path, cancel: threading.Event | None = None
    ) -> dict:
        limits = ResourceLimits(
            time_limit_ms=job.limits.time_limit_ms,
            memory_limit_mb=job.limits.memory_limit_mb,
            output_limit_kb=job.limits.output_limit_kb or 1024,
            process_limit=job.limits.process_limit or 32,
            cpu_cores=job.limits.cpu_cores or 1,
        )
        compile_limits = ResourceLimits(
            time_limit_ms=max(10_000, limits.time_limit_ms * 10),
            memory_limit_mb=limits.memory_limit_mb,
            output_limit_kb=limits.output_limit_kb,
            cpu_cores=limits.cpu_cores,
            process_limit=limits.process_limit,
        )
        # SPJ 特判（docs/contracts/judge.md「SPJ 特判」）：编译预算与提交一致；
        # 运行时限 max(2×单点时限, 5s)、内存与提交一致、输出上限 16KB（超出即 checker 故障）
        spj_source: bytes | None = None
        if job.spj:
            spj_path = data_dir / "spj.cpp"
            if not spj_path.is_file():
                return {"submission_id": job.submission_id, "status": "system_error",
                        "time_used_ms": 0, "memory_used_kb": None,
                        "error_message": "special judge data missing (spj.cpp)", "cases": []}
            spj_source = spj_path.read_bytes()
        spj_limits = ResourceLimits(
            time_limit_ms=max(2 * limits.time_limit_ms, 5_000),
            memory_limit_mb=limits.memory_limit_mb,
            output_limit_kb=16,
            process_limit=limits.process_limit,
            cpu_cores=limits.cpu_cores,
        )
        cases = await asyncio.to_thread(
            self._load_cases_sync, job, data_dir, limits
        )
        # 判题为阻塞进程等待（单次数秒），必须移出事件循环线程，否则心跳/其他任务全部停摆
        results = await asyncio.to_thread(
            self.executor.execute_cases,
            cases,
            compile_limits=compile_limits,
            stop_on_failure=job.stop_on_failure,
            spj_source=spj_source,
            spj_limits=spj_limits,
            cancel_event=cancel,
            max_parallel=self.cfg.sandbox.case_parallel,
        )

        max_time = 0
        case_results = []
        # 分数由服务端按通过比例派生，节点只回传状态与用量
        for tc, res in zip(job.cases, results, strict=False):
            max_time = max(max_time, res.time_used_ms)
            case_results.append({
                "test_case_id": tc.test_case_id, "status": res.status,
                "time_used_ms": res.time_used_ms, "memory_used_kb": res.memory_used_kb or 0,
                "output": res.stdout, "message": res.message,
            })
        status = aggregate_status([r.status for r in results])
        error_message = ""
        if results and results[0].compile:
            error_message = results[0].stderr.decode("utf-8", errors="replace")[:8000]
        elif any(r.status == "system_error" for r in results):
            # 逐点 system_error 仅由特判程序故障产生：统一口径、不回传 stderr 细节
            error_message = "special judge program failed"
        return {"submission_id": job.submission_id, "status": status,
                "time_used_ms": max_time, "memory_used_kb": None,
                "error_message": error_message, "cases": case_results}

    def _load_cases_sync(self, job: judge_pb2.SubmitJob, data_dir: Path, limits: ResourceLimits) -> list[JudgeCase]:
        """只登记测试点路径，真正读文件推迟到执行该点（ACM 短路不读后续）。"""
        cases = []
        for tc in job.cases:
            cases.append(JudgeCase(
                job.language, job.code, limits=limits,
                stdin_path=data_dir / "cases" / f"{tc.test_case_id}.in",
                expected_path=data_dir / "cases" / f"{tc.test_case_id}.out",
            ))
        return cases

    async def _execute_run_code(self, job: judge_pb2.RunCodeJob) -> None:
        """用户自测：单次独立运行，无测试点、无比对、不落库（docs/contracts/judge.md「用户自测」）。"""
        async with self.semaphore:
            self.running_tasks += 1
            try:
                result = await self._run_code_inner(job)
            except Exception as exc:  # noqa: BLE001 - 节点侧故障以 system_error 回传
                log.exception("自测执行异常 request=%s", job.request_id)
                result = {
                    "request_id": job.request_id, "status": "system_error",
                    "output": b"", "error_message": f"node error: {exc}"[:2000],
                    "time_used_ms": 0, "memory_used_kb": None,
                }
            finally:
                self.running_tasks -= 1
        await self.outbox.put(judge_pb2.NodeMessage(run_code_result=judge_pb2.RunCodeResult(
            request_id=result["request_id"],
            status=result["status"],
            output=result["output"],
            error_message=result.get("error_message") or "",
            time_used_ms=result.get("time_used_ms", 0),
            memory_used_kb=result.get("memory_used_kb") or 0,
        )))
        log.info("自测完成 %s → %s", result["request_id"], result["status"])

    async def _run_code_inner(self, job: judge_pb2.RunCodeJob) -> dict:
        limits = ResourceLimits(
            time_limit_ms=job.limits.time_limit_ms,
            memory_limit_mb=job.limits.memory_limit_mb,
            output_limit_kb=job.limits.output_limit_kb or 1024,
            process_limit=job.limits.process_limit or 32,
            cpu_cores=job.limits.cpu_cores or 1,
        )
        # 与正式判题一致：编译预算独立于单点运行限制（PreparedSubmission 编译一次）
        compile_limits = ResourceLimits(
            time_limit_ms=max(10_000, limits.time_limit_ms * 10),
            memory_limit_mb=limits.memory_limit_mb,
            output_limit_kb=limits.output_limit_kb,
            cpu_cores=limits.cpu_cores,
            process_limit=limits.process_limit,
        )
        def _run_case_sync():
            with self.executor.prepare_submission(job.language, job.code, compile_limits) as submission:
                return submission.run_case(job.input, None, limits)

        # 编译 + 运行为阻塞等待，移出事件循环线程
        res = await asyncio.to_thread(_run_case_sync)
        error_message = ""
        if res.status in ("compile_error", "runtime_error", "system_error"):
            error_message = res.stderr.decode("utf-8", errors="replace")[:8000]
        return {
            "request_id": job.request_id, "status": res.status,
            "output": res.stdout, "error_message": error_message,
            "time_used_ms": res.time_used_ms, "memory_used_kb": res.memory_used_kb,
        }


def _to_result_message(result: dict) -> judge_pb2.NodeMessage:
    return judge_pb2.NodeMessage(result=judge_pb2.JudgeResult(
        submission_id=result["submission_id"],
        status=result["status"],
        score=result.get("score", 0),
        time_used_ms=result.get("time_used_ms", 0),
        memory_used_kb=result.get("memory_used_kb") or 0,
        error_message=result.get("error_message") or "",
        cases=[
            judge_pb2.CaseResult(
                test_case_id=c["test_case_id"], status=c["status"],
                time_used_ms=c["time_used_ms"], memory_used_kb=c["memory_used_kb"],
                output=c["output"], message=c.get("message") or b"",
            )
            for c in result.get("cases", [])
        ],
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description="PigeonOJ 判题节点守护进程")
    parser.add_argument("--config", default="node.toml", help="TOML 配置文件路径")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if not cfg.server.token:
        print("[错误] 配置缺少 server.token（需与后端 JUDGE_GATEWAY_TOKENS 之一匹配）", file=sys.stderr)
        raise SystemExit(64)
    Path(cfg.paths.workspace).mkdir(parents=True, exist_ok=True)

    from admin_server import NodeAdmin

    daemon = NodeDaemon(cfg)
    admin = NodeAdmin(daemon, args.config)
    admin.start()
    if cfg.admin.bind and cfg.admin.port > 0:
        log.info("管理页 http://%s:%s/", cfg.admin.bind, cfg.admin.port)

    backoff = 3
    try:
        while True:
            try:
                asyncio.run(daemon.run())
                if daemon.reconnect_requested:
                    log.info("按管理页请求重连网关")
                else:
                    log.info("网关连接结束，%ss 后重连", backoff)
            except KeyboardInterrupt:
                raise SystemExit(0)
            except asyncio.CancelledError as exc:
                daemon.record_gateway_error(exc)
                log.warning("%s；%ss 后重试", daemon.last_error or "网关连接被取消", backoff)
            except grpc.aio.AioRpcError as exc:
                daemon.record_gateway_error(exc)
                log.warning("%s；%ss 后重试", daemon.last_error, backoff)
            except Exception as exc:  # noqa: BLE001 - 保管理页存活，网关异常只重连
                daemon.record_gateway_error(exc)
                log.warning("%s；%ss 后重试", daemon.last_error, backoff)
            time.sleep(backoff)
    finally:
        admin.stop()


if __name__ == "__main__":
    main()

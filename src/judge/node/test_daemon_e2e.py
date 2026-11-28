"""判题节点端到端测试：真实 daemon + 真实 isolate + 真实 gRPC 网关。

默认跳过；在节点容器内运行：

    ISOLATE_INTEGRATION=1 python3.12 -m pytest -q test_daemon_e2e.py

覆盖链路：注册认证 → 派发 SubmitJob → FetchProblemData 拉取测试点 →
isolate 编译/判题 → JudgeResult 回传，以及 SPJ、用户自测、编译错误。
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace

import grpc
import pytest

from config import JudgeNodeConfig
from gen import judge_pb2, judge_pb2_grpc

pytestmark = pytest.mark.skipif(
    os.environ.get("ISOLATE_INTEGRATION") != "1"
    or sys.platform != "linux"
    or shutil.which("isolate") is None,
    reason="需要 Linux + isolate（容器内以 ISOLATE_INTEGRATION=1 运行）",
)

TOKEN = "e2e-token"
PROBLEM_ID = "p1"
DATA_VERSION = "v1"
CC_SOURCE = b"""
#include <iostream>
int main() { long long a, b; std::cin >> a >> b; std::cout << a + b << std::endl; }
"""
CC_WA = b"""
#include <iostream>
int main() { long long a, b; std::cin >> a >> b; std::cout << a - b << std::endl; }
"""
SPJ_SOURCE = b"""
#include <fstream>
int main(int argc, char** argv) {
    std::ifstream in(argv[1]), out(argv[2]), ans(argv[3]);
    long long a, b, got, want;
    in >> a >> b; out >> got; ans >> want;
    if (got == want) { std::printf("ok\\n"); return 0; }
    std::printf("wrong answer expected %lld, found %lld\\n", want, got);
    return 1;
}
"""

CASES = {"c1": (b"1 2\n", b"3\n"), "c2": (b"10 20\n", b"30\n")}


class FakeGateway(judge_pb2_grpc.JudgeGatewayServicer):
    """最小网关桩：只实现节点用到的两条 RPC。"""

    def __init__(self) -> None:
        self.registered_id: str = ""
        self.results: dict[str, dict] = {}
        self.run_code: dict[str, dict] = {}
        self.token_ok = False
        self._job: judge_pb2.SubmitJob | None = None
        self._run_job: judge_pb2.RunCodeJob | None = None
        self.registered = threading.Event()
        self._queue: asyncio.Queue | None = None

    async def Connect(self, request_iterator, context):
        loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        first = await request_iterator.__anext__()
        assert first.WhichOneof("payload") == "register"
        if first.register.token != TOKEN:
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "invalid node token")
        self.token_ok = True
        self.registered_id = first.register.node_id
        yield judge_pb2.ServerMessage(ack=judge_pb2.RegisterAck(
            node_id=first.register.node_id, heartbeat_interval_seconds=3,
        ))
        self.registered.set()

        async def pump() -> None:
            async for msg in request_iterator:
                kind = msg.WhichOneof("payload")
                if kind == "result":
                    self.results[msg.result.submission_id] = {
                        "status": msg.result.status,
                        "error_message": msg.result.error_message,
                        "cases": [
                            {"id": c.test_case_id, "status": c.status, "message": c.message}
                            for c in msg.result.cases
                        ],
                    }
                elif kind == "run_code_result":
                    self.run_code[msg.run_code_result.request_id] = {
                        "status": msg.run_code_result.status,
                        "output": msg.run_code_result.output,
                    }

        pump_task = loop.create_task(pump())
        while True:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                if pump_task.done():
                    break
                continue
            yield item

    async def FetchProblemData(self, request, context):
        if request.problem_id != PROBLEM_ID:
            await context.abort(grpc.StatusCode.NOT_FOUND, "unknown problem")
        for case_id, (stdin, answer) in CASES.items():
            yield judge_pb2.FileChunk(path=f"cases/{case_id}.in", content=stdin)
            yield judge_pb2.FileChunk(path=f"cases/{case_id}.out", content=answer)
        # manifest.json 是缓存完整性的哨兵（datacache 以它判断命中）
        yield judge_pb2.FileChunk(
            path="manifest.json",
            content=b'{"problem_id": "p1", "data_version": "v1"}',
        )
        yield judge_pb2.FileChunk(path="spj.cpp", content=SPJ_SOURCE)

    def _push(self, message: judge_pb2.ServerMessage) -> None:
        assert self.registered.wait(30), "节点未注册"
        assert self._queue is not None
        self._queue._loop.call_soon_threadsafe(self._queue.put_nowait, message)  # noqa: SLF001

    def push_job(self, job: judge_pb2.SubmitJob) -> None:
        self._push(judge_pb2.ServerMessage(job=job))

    def push_run_code(self, job: judge_pb2.RunCodeJob) -> None:
        self._push(judge_pb2.ServerMessage(run_code=job))


@pytest.fixture(scope="module")
def harness():
    """在同一事件循环内同时跑节点 daemon 与网关桩（gRPC aio 不接受跨 loop 使用）。"""
    from daemon import NodeDaemon

    gateway = FakeGateway()
    root = Path(tempfile.mkdtemp(prefix="pigeonoj-e2e-"))
    cfg = JudgeNodeConfig()
    cfg.server.address = "127.0.0.1:0"  # 由下方 aio server 绑定后回填
    cfg.server.token = TOKEN
    cfg.server.tls = False
    cfg.node.id = "e2e-node"
    cfg.node.capacity = 2
    cfg.paths.workspace = str(root / "work")
    cfg.paths.data_cache = str(root / "cache")
    cfg.sandbox.case_parallel = 2
    cfg.sandbox.box_pool_size = 4
    cfg.sandbox.box_id_base = 700
    cfg.admin.bind = ""
    cfg.admin.port = 0
    for sub in ("work", "cache"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    state: dict = {}

    async def bootstrap() -> None:
        server = grpc.aio.server()
        judge_pb2_grpc.add_JudgeGatewayServicer_to_server(gateway, server)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        state["server"] = server
        state["port"] = port
        cfg.server.address = f"127.0.0.1:{port}"
        state["daemon"] = NodeDaemon(cfg)
        state["task"] = asyncio.create_task(state["daemon"].run())
        state["ready"].set()

    loop = asyncio.new_event_loop()
    state["ready"] = threading.Event()
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()
    state["loop"] = loop
    asyncio.run_coroutine_threadsafe(bootstrap(), loop).result(30)
    assert state["ready"].wait(30), "网关 / 节点未就绪"
    try:
        yield SimpleNamespace(
            gateway=gateway, daemon=state["daemon"], root=root,
            loop=loop, state=state,
        )
    finally:
        async def shutdown() -> None:
            state["daemon"].executor.close()
            await state["server"].stop(0)

        try:
            asyncio.run_coroutine_threadsafe(shutdown(), loop).result(30)
        finally:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(timeout=10)


def _job(submission_id: str, source: bytes, *, spj: bool = False, stop_on_failure: bool = False):
    return judge_pb2.SubmitJob(
        submission_id=submission_id,
        language="cpp17",
        code=source,
        problem_id=PROBLEM_ID,
        data_version=DATA_VERSION,
        limits=judge_pb2.ResourceLimits(
            time_limit_ms=2000, memory_limit_mb=256, output_limit_kb=64,
            process_limit=32, cpu_cores=1,
        ),
        spj=spj,
        stop_on_failure=stop_on_failure,
        cases=[
            judge_pb2.TestCaseFile(test_case_id=cid, name=cid) for cid in CASES
        ],
    )


def _await_result(gateway: FakeGateway, submission_id: str, timeout: float = 120.0) -> dict:
    deadline = __import__("time").time() + timeout
    while __import__("time").time() < deadline:
        if submission_id in gateway.results:
            return gateway.results[submission_id]
        __import__("time").sleep(0.1)
    raise AssertionError(f"等待 {submission_id} 结果超时")


def test_node_registers_with_gateway(harness):
    # 注册是异步的：daemon 连上后才会走到 Register
    assert harness.gateway.registered.wait(30), "节点未在 30s 内注册"
    assert harness.gateway.token_ok
    assert harness.gateway.registered_id == "e2e-node"


def test_accepted_submission_end_to_end(harness):
    sid = str(uuid.uuid4())
    harness.gateway.push_job(_job(sid, CC_SOURCE))
    result = _await_result(harness.gateway, sid)
    assert result["status"] == "accepted", result
    assert [c["status"] for c in result["cases"]] == ["accepted", "accepted"]


def test_wrong_answer_submission_end_to_end(harness):
    sid = str(uuid.uuid4())
    harness.gateway.push_job(_job(sid, CC_WA))
    result = _await_result(harness.gateway, sid)
    assert result["status"] == "wrong_answer", result


def test_compile_error_reports_compiler_output(harness):
    sid = str(uuid.uuid4())
    harness.gateway.push_job(_job(sid, b"int main() { not c++ }"))
    result = _await_result(harness.gateway, sid)
    assert result["status"] == "compile_error", result
    assert result["error_message"]  # 编译器 stderr 回传用户


def test_acm_stop_on_failure_short_circuits(harness):
    sid = str(uuid.uuid4())
    harness.gateway.push_job(_job(sid, CC_WA, stop_on_failure=True))
    result = _await_result(harness.gateway, sid)
    assert result["status"] == "wrong_answer", result
    assert len(result["cases"]) == 1  # 首点即 WA，不再执行 c2


def test_spj_submission_end_to_end(harness):
    sid = str(uuid.uuid4())
    harness.gateway.push_job(_job(sid, CC_SOURCE, spj=True))
    result = _await_result(harness.gateway, sid)
    assert result["status"] == "accepted", result
    assert result["cases"][0]["message"].startswith(b"ok")

    sid_wa = str(uuid.uuid4())
    harness.gateway.push_job(_job(sid_wa, CC_WA, spj=True))
    result_wa = _await_result(harness.gateway, sid_wa)
    assert result_wa["status"] == "wrong_answer", result_wa
    assert b"wrong answer" in result_wa["cases"][0]["message"]


def test_run_code_returns_output(harness):
    rid = str(uuid.uuid4())
    harness.gateway.push_run_code(judge_pb2.RunCodeJob(
        request_id=rid, language="cpp17", code=CC_SOURCE, input=b"4 5\n",
        limits=judge_pb2.ResourceLimits(
            time_limit_ms=2000, memory_limit_mb=256, output_limit_kb=64,
            process_limit=32, cpu_cores=1,
        ),
    ))
    deadline = __import__("time").time() + 120
    while __import__("time").time() < deadline:
        if rid in harness.gateway.run_code:
            result = harness.gateway.run_code[rid]
            assert result["status"] == "ok", result
            assert result["output"] == b"9\n"
            return
        __import__("time").sleep(0.1)
    raise AssertionError("等待自测结果超时")

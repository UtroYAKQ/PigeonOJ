"""执行器 argv、isolate meta 判定、Java -Xmx、测试点懒加载。"""
from __future__ import annotations

import time

import pytest

from executor import (
    IsolateExecutor,
    IsolateMeta,
    JudgeCase,
    JudgeWorkerError,
    ResourceLimits,
    _classify,
    _commands,
    _java_xmx_mb,
    _readonly_mounts,
    _same_output,
    parse_meta,
)


def _wait_until(predicate, timeout: float = 3.0) -> None:
    """等待专用重建线程完成（不占 case worker 的异步重建）。"""
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "等待 box 重建超时"
        time.sleep(0.01)


class _StubExecutor(IsolateExecutor):
    """跳过 isolate 探测：只验证 argv 组装。"""

    def __init__(self) -> None:
        super().__init__("isolate", 1, 0)
        self.pool._version = "isolate 2.0"


def test_build_args_runs_isolate_without_shell(tmp_path):
    exe = _StubExecutor()
    args = exe.build_args(
        ["/usr/bin/python3.12", "/box/prog/Main.py"],
        box_id=3,
        time_limit_ms=1500,
        memory_limit_mb=256,
        as_limit_mb=256,
        process_limit=16,
        fsize_kb=1024,
        mounts=[(tmp_path, "/box/prog")],
        meta_host=tmp_path / "meta",
    )
    assert args[0] == "isolate"
    assert args[args.index("--box-id") + 1] == "3"
    assert "--cg" in args
    # 毫秒精度：不再整秒取整
    assert args[args.index("--time") + 1] == "1.500"
    assert args[args.index("--wall-time") + 1] == "2.000"
    # 整组 RSS 硬限 + 地址空间硬限
    assert args[args.index("--cg-mem") + 1] == str(256 * 1024)
    assert args[args.index("--mem") + 1] == str(256 * 1024)
    assert args[args.index("--fsize") + 1] == "1024"
    # --processes 是 getopt 可选参数，必须用 = 绑定
    assert f"--processes=16" in args
    # 文件参数：stdin/stdout/stderr 走沙箱路径，meta 走宿主路径
    assert args[args.index("--chdir") + 1] == "/box"
    assert args[args.index("--stdout") + 1] == "/box/stdout"
    assert args[args.index("--stderr") + 1] == "/box/stderr"
    assert args[args.index("--meta") + 1] == str(tmp_path / "meta")
    # --dir 参数顺序为 inside=outside
    assert f"/box/prog={tmp_path}" in args or f"/box/prog={tmp_path.resolve()}" in args
    dash = args.index("--")
    assert args[dash + 1:] == ["/usr/bin/python3.12", "/box/prog/Main.py"]
    assert "/bin/sh" not in args


def test_build_args_rejects_nul():
    exe = _StubExecutor()
    with pytest.raises(JudgeWorkerError):
        exe.build_args(
            ["/bin/true" + chr(0)], box_id=0, time_limit_ms=1000, memory_limit_mb=64,
        )


def test_parse_meta_reads_isolate_fields():
    text = "\n".join([
        "time:0.123",
        "time-wall:0.456",
        "max-rss:2048",
        "cg-mem:4096",
        "exitcode:0",
        "status:",
        "message:",
    ])
    meta = parse_meta(text)
    assert meta.cpu_ms == 123
    assert meta.wall_ms == 456
    assert meta.max_rss_kb == 2048
    assert meta.cg_mem_kb == 4096
    assert meta.exit_code == 0 and meta.status == ""


def _meta(**kwargs) -> IsolateMeta:
    base = {"status": "", "exitcode": "0", "time": "0.100", "time-wall": "0.120", "max-rss": "1024"}
    base.update(kwargs)
    return parse_meta("".join(f"{k}:{v}\n" for k, v in base.items()))


def test_classify_ok():
    result = _classify(_meta(), ResourceLimits(), 1024, b"out", b"", 120)
    # 展示用 CPU 时间（meta time=0.100），不把沙箱启动的 wall 开销算给用户
    assert result.status == "ok" and result.time_used_ms == 100


def test_classify_timeout_reports_wall_when_cpu_is_low():
    # sleep 类程序 CPU 很低但 wall 超限：报 wall，避免显示接近 0ms
    meta = _meta(**{"time": "0.050", "time-wall": "0.700"})
    result = _classify(meta, ResourceLimits(time_limit_ms=100), 1024, b"", b"", 700)
    assert result.status == "time_limit_exceeded"
    assert result.time_used_ms == 700


def test_classify_timeout_from_meta_status():
    assert _classify(_meta(status="TO"), ResourceLimits(), 1024, b"", b"", 100).status == "time_limit_exceeded"


def test_classify_timeout_from_cpu_over_limit():
    meta = _meta(time="1.500")
    assert _classify(meta, ResourceLimits(time_limit_ms=1000), 1024, b"", b"", 1600).status == "time_limit_exceeded"


def test_classify_memory_over_limit():
    meta = _meta(**{"max-rss": str(300 * 1024)})
    verdict = _classify(meta, ResourceLimits(memory_limit_mb=256), 1024, b"", b"", 100)
    assert verdict.status == "memory_limit_exceeded"


def test_classify_output_over_limit():
    assert _classify(_meta(), ResourceLimits(), 4, b"abcdef", b"", 100).status == "output_limit_exceeded"


def test_classify_sigxfsz_is_output_limit():
    assert _classify(_meta(exitsig="25"), ResourceLimits(), 1024, b"", b"", 100).status == (
        "output_limit_exceeded"
    )


def test_classify_runtime_error():
    assert _classify(_meta(exitcode="1"), ResourceLimits(), 1024, b"", b"", 100).status == "runtime_error"


def test_classify_memory_error_message_is_mle():
    verdict = _classify(_meta(exitcode="1"), ResourceLimits(), 1024, b"", b"MemoryError", 100)
    assert verdict.status == "memory_limit_exceeded"


def test_classify_compile_error_message_is_not_rewritten():
    verdict = _classify(
        _meta(exitcode="1"), ResourceLimits(), 1024, b"", b"std::bad_alloc", 100, compile=True,
    )
    assert verdict.status == "runtime_error"


def test_classify_internal_error_is_system_error():
    assert _classify(_meta(status="XX"), ResourceLimits(), 1024, b"", b"", 100).status == "system_error"


def test_java_xmx_follows_effective_memory():
    _, run, compile_cmd = _commands("java21", "/prog", memory_limit_mb=1024)
    # -Xmx 需为 JVM 非堆开销留余量，不能等于 --cg-mem（否则正常程序被判 MLE）
    assert f"-Xmx{_java_xmx_mb(1024)}m" in run
    assert _java_xmx_mb(1024) < 1024
    assert "-XX:ErrorFile=/tmp/hs_err_pid%p.log" in run
    assert compile_cmd is not None and "/box/out" in compile_cmd
    assert _java_xmx_mb(0) >= 1
    assert _java_xmx_mb(256) < 256


def test_commands_use_box_paths():
    _, run, compile_cmd = _commands("cpp17", "/box/prog")
    assert run == ["/box/prog/Main"]
    assert compile_cmd is not None and compile_cmd[-1] == "/box/prog/Main.cpp"
    assert "/box/out/Main" in compile_cmd


def test_readonly_mounts_share_same_parent(tmp_path):
    a = tmp_path / "1.in"
    b = tmp_path / "1.out"
    a.write_bytes(b"")
    b.write_bytes(b"")
    mounts, paths = _readonly_mounts([a, b])
    assert len(mounts) == 1  # 同目录只挂一次
    assert paths == ["/box/data/1.in", "/box/data/1.out"]


def test_readonly_mounts_separate_parents(tmp_path):
    d1 = tmp_path / "in"
    d2 = tmp_path / "out"
    d1.mkdir()
    d2.mkdir()
    f1, f2 = d1 / "1.in", d2 / "1.out"
    f1.write_bytes(b"")
    f2.write_bytes(b"")
    mounts, paths = _readonly_mounts([f1, f2])
    assert len(mounts) == 2
    assert paths == ["/box/data/1.in", "/box/data/1/1.out"]


def test_same_output_trailing_whitespace_tolerant():
    actual = b"1 2  \n3\n"
    expected = b"1 2\r\n3"  # 行尾空白与 CRLF 规范化后一致
    assert _same_output(actual, expected)
    assert not _same_output(b"1\n", b"2\n")


def test_judge_case_lazy_load(tmp_path):
    inp = tmp_path / "1.in"
    out = tmp_path / "1.out"
    inp.write_bytes(b"in-data")
    out.write_bytes(b"out-data")
    case = JudgeCase(
        "python3.12", b"print(1)", limits=ResourceLimits(),
        stdin_path=inp, expected_path=out,
    )
    assert case.stdin == b"" and case.expected_stdout is None
    assert case.load_stdin() == b"in-data"
    assert case.load_expected() == b"out-data"


def test_judge_case_inline_bytes_still_work():
    case = JudgeCase("python3.12", b"print(1)", b"1\n", b"1\n")
    assert case.load_stdin() == b"1\n"
    assert case.load_expected() == b"1\n"


def _py_case() -> JudgeCase:
    return JudgeCase("python3.12", b"print(1)", b"1\n", b"1\n", ResourceLimits())


def test_execute_cases_stop_on_failure_skips_later_files(tmp_path):
    from executor import ExecutionResult, JudgeWorker

    class FakeExecutor:
        def run(self, command, **_kwargs):
            return ExecutionResult("ok", b"nope\n", b"", 1, 10, 0)

    first_in = tmp_path / "1.in"
    first_out = tmp_path / "1.out"
    later_in = tmp_path / "2.in"
    first_in.write_bytes(b"1\n")
    first_out.write_bytes(b"1\n")
    cases = [
        JudgeCase("python3.12", b"print(1)", limits=ResourceLimits(), stdin_path=first_in, expected_path=first_out),
        JudgeCase("python3.12", b"print(1)", limits=ResourceLimits(), stdin_path=later_in, expected_path=tmp_path / "2.out"),
    ]
    results = JudgeWorker(FakeExecutor(), str(tmp_path)).execute_cases(cases, stop_on_failure=True)
    assert len(results) == 1 and results[0].status == "wrong_answer"
    assert not later_in.exists()


def test_execute_cases_parallel_preserves_order(tmp_path):
    from executor import ExecutionResult, JudgeWorker

    class FakeExecutor:
        def run(self, command, **_kwargs):
            return ExecutionResult("ok", b"1\n", b"", 1, 10, 0)

    results = JudgeWorker(FakeExecutor(), str(tmp_path)).execute_cases(
        [_py_case(), _py_case(), _py_case()], stop_on_failure=False, max_parallel=2
    )
    assert len(results) == 3 and all(r.status == "accepted" for r in results)


def test_execute_cases_cancel_stops_later_serial(tmp_path):
    import threading

    from executor import ExecutionResult, JudgeWorker

    ev = threading.Event()

    class FakeExecutor:
        def run(self, command, **_kwargs):
            ev.set()
            return ExecutionResult("ok", b"1\n", b"", 1, 10, 0)

    results = JudgeWorker(FakeExecutor(), str(tmp_path)).execute_cases(
        [_py_case(), _py_case(), _py_case()], stop_on_failure=True, cancel_event=ev
    )
    assert len(results) == 1


def test_execute_cases_parallel_refills_instead_of_batching(tmp_path):
    """回归（长尾阻塞）：短测试点完成后应立即补位，不等同批最慢点结束。

    旧实现按批 as_completed（整批结束才进下一批），一个慢点拖住整批；
    这里 case0 阻塞在门闩上，断言 case4 在门闩释放前已开始执行。
    """
    import threading
    import time

    from executor import ExecutionResult, JudgeCase, JudgeWorker, ResourceLimits

    gate = threading.Event()
    started: set[bytes] = set()
    lock = threading.Lock()

    class FakeExecutor:
        def run(self, _command, **kwargs):
            tag = kwargs["stdin"]
            with lock:
                started.add(tag)
            if tag == b"\x00":
                gate.wait(2)
            return ExecutionResult("ok", tag, b"", 1, 10, 0)

    cases = [
        JudgeCase(
            "python3.12", b"print(1)", stdin=bytes([i]), expected_stdout=bytes([i]),
            limits=ResourceLimits(),
        )
        for i in range(8)
    ]

    def run() -> None:
        JudgeWorker(FakeExecutor(), str(tmp_path)).execute_cases(cases, max_parallel=4)

    worker = threading.Thread(target=run)
    worker.start()
    try:
        deadline = time.time() + 1
        while b"\x04" not in started and time.time() < deadline:
            time.sleep(0.01)
        assert b"\x04" in started
    finally:
        gate.set()
        worker.join(timeout=5)


def test_execute_cases_parallel_honors_pre_set_cancel(tmp_path):
    """取消事件已置位时不再启动任何测试点（与旧批次边界语义一致）。"""
    import threading

    from executor import ExecutionResult, JudgeWorker

    calls = {"n": 0}

    class FakeExecutor:
        def run(self, _command, **_kwargs):
            calls["n"] += 1
            return ExecutionResult("ok", b"1\n", b"", 1, 10, 0)

    ev = threading.Event()
    ev.set()
    results = JudgeWorker(FakeExecutor(), str(tmp_path)).execute_cases(
        [_py_case(), _py_case()], stop_on_failure=False, cancel_event=ev, max_parallel=2
    )
    assert results == [] and calls["n"] == 0


def test_box_pool_reuses_boxes(tmp_path, monkeypatch):
    """借出 → 归还 → 再借出：池容量恒定，不重复 init。"""
    from executor import BoxPool

    pool = BoxPool("isolate", 2, 0)
    init_calls: list[int] = []
    destroyed: list[int] = []

    def fake_create(box_id):
        init_calls.append(box_id)
        box = tmp_path / f"box{box_id}"
        (box / "box").mkdir(parents=True, exist_ok=True)
        return __import__("executor")._Box(box_id=box_id, host_dir=box)

    monkeypatch.setattr(pool, "_create", fake_create)
    monkeypatch.setattr(pool, "_destroy", lambda box: destroyed.append(box.box_id))
    monkeypatch.setattr(pool, "_probe_version", lambda: "isolate 2.0")

    pool.start()
    assert sorted(init_calls) == [0, 1]
    assert pool.stats()["pool_idle"] == 2

    box = pool.acquire()
    assert pool.stats()["pool_idle"] == 1
    pool.release(box)
    assert pool.stats()["pool_idle"] == 2
    assert sorted(init_calls) == [0, 1]  # 归还即复用，未重建

    pool.close()
    assert sorted(destroyed) == [0, 1]


def test_box_pool_rebuilds_unhealthy_box(tmp_path, monkeypatch):
    from executor import BoxPool

    pool = BoxPool("isolate", 1, 0)
    created: list[int] = []

    def fake_create(box_id):
        created.append(box_id)
        box = tmp_path / f"box{box_id}-{len(created)}"
        (box / "box").mkdir(parents=True, exist_ok=True)
        return __import__("executor")._Box(box_id=box_id, host_dir=box)

    monkeypatch.setattr(pool, "_create", fake_create)
    monkeypatch.setattr(pool, "_destroy", lambda box: None)
    monkeypatch.setattr(pool, "_probe_version", lambda: "isolate 2.0")

    pool.start()
    box = pool.acquire()
    pool.release(box, healthy=False)
    _wait_until(lambda: len(created) == 2 and pool.stats()["pool_idle"] == 1)
    assert created == [0, 0]          # 同 box-id 重建
    assert pool.stats()["pool_total"] == 1
    pool.close()


def test_box_pool_release_unhealthy_does_not_wait_for_rebuild(tmp_path, monkeypatch):
    """release 只入队：重建线程慢时不占用 case worker 线程。"""
    import threading

    from executor import BoxPool, _Box

    pool = BoxPool("isolate", 1, 0)
    gate = threading.Event()
    calls: list[int] = []

    def fake_create(box_id):
        calls.append(box_id)
        if len(calls) > 1:
            gate.wait(3)
        box = tmp_path / f"box{box_id}-{len(calls)}"
        (box / "box").mkdir(parents=True, exist_ok=True)
        return _Box(box_id=box_id, host_dir=box)

    monkeypatch.setattr(pool, "_create", fake_create)
    monkeypatch.setattr(pool, "_destroy", lambda box: None)
    monkeypatch.setattr(pool, "_probe_version", lambda: "isolate 2.0")

    pool.start()
    box = pool.acquire()
    released = threading.Event()

    def do_release() -> None:
        pool.release(box, healthy=False)
        released.set()

    worker = threading.Thread(target=do_release, daemon=True)
    worker.start()
    try:
        assert released.wait(1), "release 被重建阻塞"
        assert pool.stats()["pool_idle"] == 0
    finally:
        gate.set()
        worker.join(timeout=5)
    _wait_until(lambda: pool.stats()["pool_idle"] == 1)
    assert calls == [0, 0]
    pool.close()


def test_box_pool_close_during_use(tmp_path, monkeypatch):
    """已关闭的池不再收回 box（避免 close 后仍写入已销毁目录）。"""
    from executor import BoxPool

    pool = BoxPool("isolate", 1, 0)
    monkeypatch.setattr(pool, "_create", lambda box_id: (
        (tmp_path / "b").mkdir(parents=True, exist_ok=True)
        or __import__("executor")._Box(box_id=box_id, host_dir=tmp_path / "b")
    ))
    monkeypatch.setattr(pool, "_destroy", lambda box: None)
    monkeypatch.setattr(pool, "_probe_version", lambda: "isolate 2.0")

    pool.start()
    box = pool.acquire()
    pool.close()
    pool.release(box)
    assert pool.stats()["pool_idle"] == 0


def test_build_args_always_sets_process_limit():
    """isolate 不给 --processes 时只允许单进程，任何 fork 都会 EAGAIN。"""
    exe = _StubExecutor()
    args = exe.build_args(["/bin/true"], box_id=0, time_limit_ms=1000, memory_limit_mb=64)
    assert any(a.startswith("--processes=") for a in args)


def test_build_args_uses_explicit_process_limit():
    exe = _StubExecutor()
    args = exe.build_args(
        ["/bin/true"], box_id=0, time_limit_ms=1000, memory_limit_mb=64, process_limit=8,
    )
    assert "--processes=8" in args


def test_classify_checker_exit_code_is_verdict_not_error():
    """SPJ checker 以退出码 1 报 WA，属正常判定路径而非 runtime_error。"""
    meta = _meta(status="RE", exitcode="1")
    result = _classify(meta, ResourceLimits(), 1024, b"wrong answer", b"", 100, verdict_exit=True)
    assert result.status == "ok" and result.exit_code == 1


def test_classify_checker_timeout_still_fatal():
    meta = _meta(status="TO", exitcode="0")
    assert _classify(meta, ResourceLimits(), 1024, b"", b"", 5000, verdict_exit=True).status == (
        "time_limit_exceeded"
    )


def test_classify_checker_internal_error_still_fatal():
    assert _classify(_meta(status="XX"), ResourceLimits(), 1024, b"", b"", 10, verdict_exit=True).status == (
        "system_error"
    )


@pytest.mark.skipif(
    __import__("sys").platform != "linux", reason="POSIX 权限位语义（Windows chmod 不反映 0o111）"
)
def test_make_readable_preserves_execute_bit(tmp_path, monkeypatch):
    """编译产物以只读方式挂进沙箱后仍要能被 execve。"""
    import executor as ex

    monkeypatch.setattr(ex.sys, "platform", "linux")
    monkeypatch.setattr(ex.os, "geteuid", lambda: 0, raising=False)
    exe_file = tmp_path / "Main"
    src_file = tmp_path / "Main.cpp"
    exe_file.write_bytes(b"\x7fELF")
    src_file.write_bytes(b"int main(){}")
    exe_file.chmod(0o755)
    src_file.chmod(0o644)

    ex._make_readable(tmp_path)
    assert exe_file.stat().st_mode & 0o111
    assert not (src_file.stat().st_mode & 0o111)


def test_ensure_box_dir_creates_mountpoint(tmp_path):
    import executor as ex

    box = ex._Box(box_id=1, host_dir=tmp_path)
    (tmp_path / "box").mkdir()
    ex._ensure_box_dir(box, "/box/prog")
    assert (tmp_path / "box" / "prog").is_dir()
    # 非 box 内路径不处理
    ex._ensure_box_dir(box, "/data/x")
    assert not (tmp_path / "data").exists()


def test_java_xmx_reserves_nonheap_headroom():
    """JVM 非堆开销会叠加到 cgroup RSS；-Xmx 取满上限必致正常程序误判 MLE。"""
    from executor import _JAVA_NONHEAP_RESERVE_MB, _java_xmx_mb

    assert _java_xmx_mb(256) == 256 - _JAVA_NONHEAP_RESERVE_MB
    assert _java_xmx_mb(256) < 256
    # 非堆开销不随上限缩小：64MB 题只剩 16MB 堆，给 32MB+ 会整组 RSS 超限
    assert _java_xmx_mb(16) >= 16
    assert _java_xmx_mb(64) == 16
    # 大内存题预留不超过上限的 1/4
    assert _java_xmx_mb(4096) >= 4096 * 3 // 4


def test_run_stage_does_not_apply_address_space_limit():
    """运行阶段只给 --cg-mem：--mem 会让 malloc 提前 NULL、cgroup OOM 永不触发。"""
    exe = _StubExecutor()
    args = exe.build_args(
        ["/bin/true"], box_id=0, time_limit_ms=1000, memory_limit_mb=256, as_limit_mb=None,
    )
    assert "--cg-mem" in args
    assert "--mem" not in args

def test_run_one_case_does_not_load_stdin_when_path_present(tmp_path):
    """测试点零拷贝：有 stdin_path 时不得先把整份输入读进内存。"""
    from executor import ExecutionResult, JudgeWorker, ResourceLimits, _run_one_case

    captured: dict = {}

    class FakeExecutor:
        def run(self, command, **kwargs):
            captured.update(kwargs)
            return ExecutionResult("ok", b"1\n", b"", 1, 10, 0)

    inp = tmp_path / "1.in"
    inp.write_bytes(b"x" * 4096)
    out = tmp_path / "1.out"
    out.write_bytes(b"1\n")
    case = JudgeCase(
        "python3.12", b"print(1)", limits=ResourceLimits(),
        stdin_path=inp, expected_path=out,
    )
    worker = JudgeWorker(FakeExecutor(), str(tmp_path))
    with worker.prepare_submission("python3.12", case.source, ResourceLimits()) as submission:
        _run_one_case(submission, 0, case, spj=None, spj_limits=None)
    assert captured["stdin"] == b""
    assert captured["stdin_path"] == inp


def test_compile_timeout_is_reported_as_compile_error(tmp_path):
    """编译超时 / 内存超限属用户代码问题，不能把 TLE/MLE 展示给用户。"""
    from executor import ExecutionResult, JudgeWorker, ResourceLimits

    class FakeExecutor:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, command, **kwargs):
            self.calls += 1
            return ExecutionResult("time_limit_exceeded", b"", b"compile slow", 10_000, 1000, None)

    fake = FakeExecutor()
    case = JudgeCase("cpp17", b"int main() {}", limits=ResourceLimits())
    results = JudgeWorker(fake, str(tmp_path)).execute_cases(
        [case], compile_limits=ResourceLimits(time_limit_ms=10_000)
    )
    assert fake.calls == 1
    assert results[0].status == "compile_error" and results[0].compile
    assert results[0].stderr == b"compile slow"


def test_compile_system_error_stays_system_error(tmp_path):
    from executor import ExecutionResult, JudgeWorker, ResourceLimits

    class FakeExecutor:
        def run(self, command, **kwargs):
            return ExecutionResult("system_error", b"", b"", 1, 10, None)

    case = JudgeCase("cpp17", b"int main() {}", limits=ResourceLimits())
    results = JudgeWorker(FakeExecutor(), str(tmp_path)).execute_cases(
        [case], compile_limits=ResourceLimits()
    )
    assert results[0].status == "system_error"


def test_box_pool_acquire_times_out(tmp_path, monkeypatch):
    from executor import BoxPool, _Box

    pool = BoxPool("isolate", 1, 0)
    box_dir = tmp_path / "box0"
    (box_dir / "box").mkdir(parents=True)
    monkeypatch.setattr(pool, "_create", lambda box_id: _Box(box_id, box_dir))
    monkeypatch.setattr(pool, "_destroy", lambda box: None)
    monkeypatch.setattr(pool, "_probe_version", lambda: "isolate 2.0")
    pool.start()
    box = pool.acquire()
    with pytest.raises(JudgeWorkerError):
        pool.acquire(timeout=0.01)
    pool.release(box)
    pool.close()


def test_same_output_empty_lines():
    assert _same_output(b"", b"")
    assert _same_output(b"1\n", b"1")
    assert not _same_output(b"1\n\n", b"1")

def test_same_output_file_chunked_and_normalized(tmp_path):
    from executor import _same_output_file

    expected = tmp_path / "1.out"
    expected.write_bytes(b"1\n2\n")
    assert _same_output_file(b"1\n2\n", expected)
    assert _same_output_file(b"1\n2", expected)
    assert _same_output_file(b"1  \n2\t\n", expected)
    assert not _same_output_file(b"1\n3\n", expected)
    assert not _same_output_file(b"1\n2\n\n", expected)


def test_run_one_case_does_not_load_expected_when_path_present(tmp_path, monkeypatch):
    from executor import ExecutionResult, JudgeWorker, ResourceLimits, _run_one_case

    class FakeExecutor:
        def run(self, command, **kwargs):
            return ExecutionResult("ok", b"42\n", b"", 1, 10, 0)

    def boom(self):
        raise AssertionError("expected file must not be loaded into memory")

    monkeypatch.setattr(JudgeCase, "load_expected", boom)
    inp = tmp_path / "1.in"
    inp.write_bytes(b"")
    out = tmp_path / "1.out"
    out.write_bytes(b"42\n")
    case = JudgeCase(
        "python3.12", b"print(42)", limits=ResourceLimits(),
        stdin_path=inp, expected_path=out,
    )
    worker = JudgeWorker(FakeExecutor(), str(tmp_path))
    with worker.prepare_submission("python3.12", case.source, ResourceLimits()) as submission:
        result = _run_one_case(submission, 0, case, spj=None, spj_limits=None)
    assert result.status == "accepted"

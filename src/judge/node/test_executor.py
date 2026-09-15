"""执行器参数、管道限流、Java -Xmx、测试点懒加载。"""
from __future__ import annotations

from io import BytesIO

from executor import (
    JudgeCase,
    JudgeWorkerError,
    NsjailExecutor,
    ResourceLimits,
    _commands,
    _is_cpu_tle,
    _java_xmx_mb,
    _read_limited,
)


def test_build_args_no_shell_and_overrides():
    exe = NsjailExecutor("nsjail", "/etc/pigeonoj/nsjail.cfg")
    args = exe.build_args(
        ["/usr/bin/python3.12", "/workspace/Main.py"],
        time_limit_ms=1500,
        as_limit_mb=256,
        bind_src="/tmp/job1",
        process_limit=16,
        cpu_cores=1,
    )
    assert args[:4] == ["nsjail", "--config", "/etc/pigeonoj/nsjail.cfg", "--bindmount"]
    assert args[4] == "/tmp/job1:/workspace"
    assert "--time_limit" in args and args[args.index("--time_limit") + 1] == "2"
    assert "--rlimit_cpu" in args and args[args.index("--rlimit_cpu") + 1] == "2"
    assert "--rlimit_as" in args and args[args.index("--rlimit_as") + 1] == "256"
    assert "--rlimit_nproc" in args and args[args.index("--rlimit_nproc") + 1] == "16"
    assert "--max_cpus" in args and args[args.index("--max_cpus") + 1] == "1"
    dash = args.index("--")
    assert args[dash + 1 :] == ["/usr/bin/python3.12", "/workspace/Main.py"]
    assert "/bin/sh" not in args


def test_build_args_rejects_nul():
    exe = NsjailExecutor()
    try:
        exe.build_args(["/bin/true\x00"], time_limit_ms=1000)
        raise AssertionError("expected JudgeWorkerError")
    except JudgeWorkerError as exc:
        assert "invalid" in str(exc)


def test_java_xmx_follows_effective_memory():
    _, run, compile_cmd = _commands("java21", "/workspace", memory_limit_mb=1024)
    assert "-Xmx1024m" in run
    assert compile_cmd is not None and "-d" in compile_cmd
    assert _java_xmx_mb(0) == 1
    assert _java_xmx_mb(256) == 256


def test_read_limited_caps_and_flags_overflow():
    data, exceeded = _read_limited(BytesIO(b"abcdef"), 3)
    assert data == b"abcd" and exceeded is True
    data, exceeded = _read_limited(BytesIO(b"ab"), 8)
    assert data == b"ab" and exceeded is False


def test_is_cpu_tle():
    assert _is_cpu_tle(-24) and _is_cpu_tle(152)
    assert not _is_cpu_tle(0) and not _is_cpu_tle(1) and not _is_cpu_tle(None)


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

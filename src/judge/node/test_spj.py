"""SPJ 特判执行核心单元测试（docs/contracts/judge.md「SPJ 特判」）。

不依赖 nsjail：向 JudgeWorker 注入 FakeExecutor 回放预设的 ExecutionResult，
覆盖编译失败路径、退出码判定映射、多测试点编译一次、SPJ 数据缺失兜底。
"""
from __future__ import annotations

import threading
import uuid as uuid_mod

import pytest

from executor import (
    ExecutionResult,
    JudgeCase,
    JudgeWorker,
    ResourceLimits,
    SPJ_SOURCE_NAME,
    SpjCompileError,
    _spj_verdict,
)
from gen import judge_pb2

SPJ_SOURCE = b"#include <bits/stdc++.h>\nint main(int c, char** v){ return 0; }\n"

LIMITS = ResourceLimits(time_limit_ms=1000, memory_limit_mb=256, output_limit_kb=16)


class FakeExecutor:
    """按队列回放 ExecutionResult；记录全部 argv 供断言。"""

    def __init__(self, *results: ExecutionResult) -> None:
        self.results = list(results)
        self.commands: list[list[str]] = []
        self._lock = threading.Lock()

    def run(self, command, **_kwargs) -> ExecutionResult:
        with self._lock:
            self.commands.append(command)
            if not self.results:
                raise AssertionError("FakeExecutor 结果队列已耗尽")
            return self.results.pop(0)


def _worker(executor: FakeExecutor, workspace_root) -> JudgeWorker:
    return JudgeWorker(executor, str(workspace_root))


def _case() -> JudgeCase:
    return JudgeCase(
        language="python3.12", source=b"print(input())",
        stdin=b"1\n", expected_stdout=b"2\n", limits=LIMITS,
    )


def _user_run(stdout: bytes = b"2\n") -> ExecutionResult:
    return ExecutionResult("ok", stdout, b"", 12, 1024, 0)


# ---- 退出码判定映射（纯函数） ----


def test_verdict_exit_zero_is_accepted_with_message():
    user = _user_run()
    spj = ExecutionResult("ok", b"accepted 100", b"", 3, 512, 0)
    result = _spj_verdict(spj, user)
    assert result.status == "accepted"
    assert result.stdout == user.stdout
    assert result.time_used_ms == 12 and result.memory_used_kb == 1024
    assert result.message == b"accepted 100"


def test_verdict_exit_one_is_wrong_answer_with_message():
    spj = ExecutionResult("ok", b"wrong answer expected 3, found 4", b"", 3, 512, 1)
    result = _spj_verdict(spj, _user_run())
    assert result.status == "wrong_answer"
    assert result.message == b"wrong answer expected 3, found 4"


@pytest.mark.parametrize("code", [3, 4])
def test_verdict_testlib_checker_failure_is_system_error(code):
    spj = ExecutionResult("ok", b"internal fail", b"", 3, 512, code)
    result = _spj_verdict(spj, _user_run())
    assert result.status == "system_error"
    assert result.stderr == b""  # 不回传 checker 细节（防源码泄露）


def test_verdict_checker_tle_is_system_error():
    spj = ExecutionResult("time_limit_exceeded", b"", b"", 5001, 512, None)
    assert _spj_verdict(spj, _user_run()).status == "system_error"


def test_verdict_unsupported_partial_score_is_wrong_answer():
    # 部分分退出码（16+分值）不支持：按 wrong_answer 处理（契约「明确不做」）
    spj = ExecutionResult("ok", b"partial", b"", 3, 512, 16 + 40)
    assert _spj_verdict(spj, _user_run()).status == "wrong_answer"


def test_verdict_message_capped_at_2kb():
    spj = ExecutionResult("ok", b"x" * 5000, b"", 3, 512, 1)
    assert len(_spj_verdict(spj, _user_run()).message) == 2048


# ---- 编译与执行路径（FakeExecutor 注入） ----


def test_prepare_spj_compile_failure_raises(tmp_path):
    executor = FakeExecutor(ExecutionResult("runtime_error", b"", b"g++ boom", 100, 1000, 1))
    worker = _worker(executor, tmp_path)
    with worker.prepare_submission("python3.12", _case().source, LIMITS) as submission:
        with pytest.raises(SpjCompileError):
            submission.prepare_spj(SPJ_SOURCE, LIMITS)


def test_prepare_spj_success_returns_jail_binary_path(tmp_path):
    executor = FakeExecutor(ExecutionResult("ok", b"", b"", 800, 2000, 0))
    worker = _worker(executor, tmp_path)
    with worker.prepare_submission("python3.12", _case().source, LIMITS) as submission:
        spj = submission.prepare_spj(SPJ_SOURCE, LIMITS)
    assert spj.binary == "/workspace/spj"
    assert executor.commands[0][-1].endswith("spj.cpp")  # 编译命令以特判源码收尾


def test_run_case_with_spj_stages_three_files_and_runs_checker(tmp_path):
    executor = FakeExecutor(
        ExecutionResult("ok", b"", b"", 800, 2000, 0),  # spj 编译
        _user_run(b"2\n"),                              # 用户程序
        ExecutionResult("ok", b"ok", b"", 2, 300, 0),   # 特判运行
    )
    worker = _worker(executor, tmp_path)
    case = _case()
    with worker.prepare_submission("python3.12", case.source, LIMITS) as submission:
        spj = submission.prepare_spj(SPJ_SOURCE, LIMITS)
        result = submission.run_case(case.stdin, case.expected_stdout, case.limits, spj=spj, spj_limits=LIMITS)
        checker_cmd = executor.commands[-1]
        staged_input = (submission.workdir / "spj_input").read_bytes()
        staged_user_out = (submission.workdir / "spj_user_out").read_bytes()
        staged_answer = (submission.workdir / "spj_answer").read_bytes()
    assert result.status == "accepted"
    assert spj.binary == "/workspace/spj"
    assert checker_cmd == [
        "/workspace/spj", "/workspace/spj_input", "/workspace/spj_user_out", "/workspace/spj_answer",
    ]
    assert staged_input == case.stdin
    assert staged_user_out == b"2\n"
    assert staged_answer == case.expected_stdout


def test_user_run_failure_skips_spj(tmp_path):
    executor = FakeExecutor(
        ExecutionResult("ok", b"", b"", 800, 2000, 0),                      # spj 编译
        ExecutionResult("time_limit_exceeded", b"partial", b"", 1001, 100, None),  # 用户程序 TLE
    )
    worker = _worker(executor, tmp_path)
    case = _case()
    with worker.prepare_submission("python3.12", case.source, LIMITS) as submission:
        spj = submission.prepare_spj(SPJ_SOURCE, LIMITS)
        result = submission.run_case(case.stdin, case.expected_stdout, case.limits, spj=spj, spj_limits=LIMITS)
    assert result.status == "time_limit_exceeded"
    assert len(executor.commands) == 2  # 特判未运行


def test_execute_cases_compiles_spj_once_for_all_cases(tmp_path):
    case = _case()
    executor = FakeExecutor(
        ExecutionResult("ok", b"", b"", 800, 2000, 0),  # spj 编译（仅一次）
        _user_run(), ExecutionResult("ok", b"ok", b"", 2, 300, 0),
        _user_run(), ExecutionResult("ok", b"ok", b"", 2, 300, 0),
    )
    worker = _worker(executor, tmp_path)
    results = worker.execute_cases([case, case], compile_limits=LIMITS, spj_source=SPJ_SOURCE, spj_limits=LIMITS)
    assert [r.status for r in results] == ["accepted", "accepted"]
    # 1 次特判编译 + 2×(用户运行 + 特判运行)
    assert len(executor.commands) == 5


def test_execute_cases_spj_system_error_stops_later_cases(tmp_path):
    case = _case()
    executor = FakeExecutor(
        ExecutionResult("ok", b"", b"", 800, 2000, 0),  # spj 编译
        _user_run(), ExecutionResult("ok", b"died", b"", 2, 300, 3),  # checker _died
    )
    worker = _worker(executor, tmp_path)
    results = worker.execute_cases(
        [case, case, case], compile_limits=LIMITS, spj_source=SPJ_SOURCE, spj_limits=LIMITS,
        max_parallel=1,
    )
    assert len(results) == 1 and results[0].status == "system_error"


# ---- daemon 接线：SPJ 数据缺失兜底 ----


@pytest.mark.asyncio
async def test_judge_with_data_missing_spj_source(tmp_path):
    from daemon import NodeDaemon

    node = NodeDaemon.__new__(NodeDaemon)
    job = judge_pb2.SubmitJob(submission_id=str(uuid_mod.uuid4()), spj=True)
    result = await node._judge_with_data(job, tmp_path)
    assert result["status"] == "system_error"
    assert "special judge" in result["error_message"]


@pytest.mark.asyncio
async def test_judge_with_data_spj_failure_sets_plain_error_message(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from daemon import NodeDaemon

    (tmp_path / SPJ_SOURCE_NAME).write_bytes(SPJ_SOURCE)
    node = NodeDaemon.__new__(NodeDaemon)
    captured: dict = {}

    def fake_execute(cases, compile_limits=None, **kwargs):
        captured["spj_source"] = kwargs.get("spj_source")
        return [ExecutionResult("system_error", b"out", b"", 5, 10, 3)]

    node._load_cases_sync = lambda job, data_dir, limits: []
    node.executor = SimpleNamespace(execute_cases=fake_execute)
    node.cfg = SimpleNamespace(sandbox=SimpleNamespace(case_parallel=4))

    job = judge_pb2.SubmitJob(
        submission_id="s-1", spj=True,
        cases=[judge_pb2.TestCaseFile(test_case_id="t1", name="c1")],
    )
    result = await node._judge_with_data(job, tmp_path)
    assert captured["spj_source"] == SPJ_SOURCE  # 缓存中的特判源码已传入执行器
    assert result["status"] == "system_error"
    assert result["error_message"] == "special judge program failed"
    assert result["cases"][0]["message"] == b""

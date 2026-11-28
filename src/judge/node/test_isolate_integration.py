"""isolate 真机集成测试（须在判题节点容器内运行）。

默认跳过；设置 ISOLATE_INTEGRATION=1 且容器内存在 isolate + cgroup v2 时执行：

    docker compose --env-file .env.node --project-directory . -f docker/docker-compose-node.yml \\
        run --rm -e ISOLATE_INTEGRATION=1 judge-node \\
        python3.12 -m pytest -q test_isolate_integration.py

覆盖：三语言 AC / WA / TLE / MLE / OLE / RE / CE、SPJ 判定、box 池复用与泄漏、
沙箱边界（工作区只读、无网络、box 内可写）。判题语义见 docs/contracts.md §10。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from executor import (
    IsolateExecutor,
    JudgeCase,
    JudgeWorker,
    ResourceLimits,
    SpjCompileError,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("ISOLATE_INTEGRATION") != "1"
    or sys.platform != "linux"
    or shutil.which("isolate") is None,
    reason="需要 Linux + isolate（容器内以 ISOLATE_INTEGRATION=1 运行）",
)

LIMITS = ResourceLimits(time_limit_ms=2000, memory_limit_mb=256, output_limit_kb=64)
COMPILE_LIMITS = ResourceLimits(time_limit_ms=20_000, memory_limit_mb=512, output_limit_kb=1024)

CPP_ECHO = b"""
#include <iostream>
int main() { long long a, b; std::cin >> a >> b; std::cout << a + b << std::endl; }
"""
CPP_TLE = b"int main() { for(;;){} }\n"
CPP_RE = b'#include <cstdlib>\nint main() { std::abort(); }\n'
CPP_CE = b"int main() { this is not c++ }\n"
CPP_OLE = b"""
#include <cstdio>
int main() { for (int i = 0; i < 1000000; ++i) std::printf("xxxxxxxxxxxxxxxxxxxxxx\\n"); }
"""
# 持续触碰内存页直到被 cgroup OOM kill：这才是 MLE 的真实判据。
# （若同时施加 --mem 地址空间限制，malloc 会在到限前返回 NULL，程序自行退出，
#   永远走不到 cgroup OOM —— 运行阶段因此只下发 --cg-mem。）
CPP_MLE = b"""
#include <cstdlib>
#include <cstring>
int main() {
    const size_t CH = 8u << 20;
    for (;;) { char* p = (char*)malloc(CH); memset(p, 7, CH); }
}
"""
CPP_FILE_PROBE = b"""
#include <cstdio>
int main() {
    // read-only mount must reject writes; /tmp inside box must be writable
    FILE* f = std::fopen("/box/prog/probe.txt", "w");
    if (f) { std::fclose(f); return 3; }
    FILE* g = std::fopen("/tmp/probe.txt", "w");
    if (!g) return 4;
    std::fclose(g);
    return 0;
}
"""
SPJ_AC = b"""
#include <fstream>
#include <string>
int main(int argc, char** argv) {
    std::ifstream in(argv[1]), out(argv[2]), ans(argv[3]);
    long long a, b, got, want;
    in >> a >> b; out >> got; ans >> want;
    if (got == want) { std::printf("ok %lld\\n", got); return 0; }
    std::printf("wrong answer expected %lld, found %lld\\n", want, got);
    return 1;
}
"""
SPJ_BROKEN = b"""
#include <cstdio>
int main() { std::printf("checker died\\n"); return 3; }
"""


@pytest.fixture(scope="module")
def worker(tmp_path_factory):
    root = tmp_path_factory.mktemp("isolate-work")
    wrk = JudgeWorker(IsolateExecutor("isolate", pool_size=4, box_id_base=900), str(root))
    wrk.start()
    try:
        yield wrk
    finally:
        wrk.close()


def _run(worker, source: bytes, stdin: bytes, expected: bytes | None, language="cpp17"):
    case = JudgeCase(language, source, stdin=stdin, expected_stdout=expected, limits=LIMITS)
    return worker.execute_cases([case], compile_limits=COMPILE_LIMITS)[0]


def test_cpp_accepted(worker):
    result = _run(worker, CPP_ECHO, b"1 2\n", b"3\n")
    assert result.status == "accepted", result
    assert result.stdout == b"3\n"


def test_cpp_wrong_answer(worker):
    result = _run(worker, CPP_ECHO, b"1 2\n", b"4\n")
    assert result.status == "wrong_answer"


def test_cpp_compile_error(worker):
    result = _run(worker, CPP_CE, b"", None)
    assert result.status == "compile_error"
    assert result.stderr  # 编译器输出回传用户


def test_cpp_time_limit(worker):
    result = _run(worker, CPP_TLE, b"", None)
    assert result.status == "time_limit_exceeded"
    # --cg-timing：CPU 时间应为毫秒级，且不超过 wall 兜底
    assert 0 < result.time_used_ms < LIMITS.time_limit_ms + 5000


def test_cpp_runtime_error(worker):
    result = _run(worker, CPP_RE, b"", None)
    assert result.status == "runtime_error"


def test_cpp_output_limit(worker):
    case = JudgeCase(
        "cpp17", CPP_OLE, stdin=b"", expected_stdout=None,
        limits=ResourceLimits(time_limit_ms=5000, memory_limit_mb=256, output_limit_kb=8),
    )
    result = worker.execute_cases([case], compile_limits=COMPILE_LIMITS)[0]
    assert result.status == "output_limit_exceeded"


def test_cpp_memory_limit(worker):
    case = JudgeCase(
        "cpp17", CPP_MLE, stdin=b"", expected_stdout=None,
        limits=ResourceLimits(time_limit_ms=10_000, memory_limit_mb=64, output_limit_kb=64),
    )
    result = worker.execute_cases([case], compile_limits=COMPILE_LIMITS)[0]
    # 必须命中 cgroup OOM 并归为 MLE，而不是被 malloc-NULL 后的自行退出掩成 TLE/WA
    assert result.status == "memory_limit_exceeded", result
    assert result.memory_used_kb and result.memory_used_kb >= 60 * 1024


def test_python_accepted(worker):
    result = _run(worker, b"print(sum(map(int, input().split())))", b"1 2\n", b"3\n", "python3.12")
    assert result.status == "accepted", result


def test_java_accepted(worker):
    source = b"""
import java.util.*;
public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        System.out.println(sc.nextInt() + sc.nextInt());
    }
}
"""
    result = _run(worker, source, b"1 2\n", b"3\n", "java21")
    assert result.status == "accepted", result


def test_sandbox_workdir_readonly_and_tmp_writable(worker):
    # 无比对期望时正常退出即 "ok"：探针用退出码表达结论（0=只读生效且 /tmp 可写）
    result = _run(worker, CPP_FILE_PROBE, b"", None)
    assert result.status == "ok", (result.status, result.exit_code, result.stderr)


def test_sandbox_has_no_network(worker):
    # 沙箱默认不建网络命名空间于 isolate；curl/wget 访问外网必须失败
    source = b"""
#include <cstdlib>
int main() {
    int rc = std::system("wget -T 2 -q -O /dev/null http://example.com");
    return rc == 0 ? 7 : 0;
}
"""
    case = JudgeCase(
        "cpp17", source, stdin=b"", expected_stdout=None,
        limits=ResourceLimits(time_limit_ms=10_000, memory_limit_mb=256, output_limit_kb=64),
    )
    compiler = JudgeCase("cpp17", b"int main(){return 0;}\n", limits=LIMITS)
    results = worker.execute_cases([case], compile_limits=COMPILE_LIMITS)
    # 沙箱内无网络：wget 缺失或被拒，程序自身正常退出（退出码 0）
    assert results[0].status == "ok", results[0]
    assert b"not found" in results[0].stderr or results[0].stdout == b""
    del compiler


def test_box_not_visible_across_runs(worker):
    """上一个测试点写的文件不得泄漏到下一个测试点。"""
    writer = b"""
#include <cstdio>
int main() { FILE* f = std::fopen("/box/leak.txt", "w"); if (f) { std::fputs("x", f); std::fclose(f); } }
"""
    reader = b"""
#include <cstdio>
#include <sys/stat.h>
int main() { struct stat st; return ::stat("/box/leak.txt", &st) == 0 ? 9 : 0; }
"""
    first = _run(worker, writer, b"", None)
    second = _run(worker, reader, b"", None)
    assert first.status == "ok", first
    # reader 发现泄漏会以退出码 9 结束（→ runtime_error）
    assert second.status == "ok", second


def test_spj_accepted_and_wrong_answer(worker):
    spj = SPJ_AC
    ac = worker.execute_cases(
        [JudgeCase("cpp17", CPP_ECHO, stdin=b"1 2\n", expected_stdout=b"3\n", limits=LIMITS)],
        compile_limits=COMPILE_LIMITS, spj_source=spj, spj_limits=LIMITS,
    )[0]
    assert ac.status == "accepted", ac
    assert ac.message.startswith(b"ok")

    bad = b"#include <iostream>\nint main(){ std::cout << 99 << std::endl; }\n"
    wa = worker.execute_cases(
        [JudgeCase("cpp17", bad, stdin=b"1 2\n", expected_stdout=b"3\n", limits=LIMITS)],
        compile_limits=COMPILE_LIMITS, spj_source=spj, spj_limits=LIMITS,
    )[0]
    assert wa.status == "wrong_answer"
    assert b"wrong answer" in wa.message


def test_spj_checker_failure_is_system_error(worker):
    result = worker.execute_cases(
        [JudgeCase("cpp17", CPP_ECHO, stdin=b"1 2\n", expected_stdout=b"3\n", limits=LIMITS)],
        compile_limits=COMPILE_LIMITS, spj_source=SPJ_BROKEN, spj_limits=LIMITS,
    )[0]
    assert result.status == "system_error"
    assert result.stderr == b""  # checker 细节不外泄


def test_spj_compile_error_raises(worker):
    with pytest.raises(SpjCompileError):
        worker.execute_cases(
            [JudgeCase("cpp17", CPP_ECHO, stdin=b"1 2\n", expected_stdout=b"3\n", limits=LIMITS)],
            compile_limits=COMPILE_LIMITS, spj_source=b"not c++", spj_limits=LIMITS,
        )


def test_parallel_cases_use_distinct_boxes(worker, tmp_path):
    """4 个测试点并发：结果正确且 box 池不串数据。"""
    cases = [
        JudgeCase("cpp17", CPP_ECHO, stdin=f"{i} {i}\n".encode(), expected_stdout=f"{i * 2}\n".encode(), limits=LIMITS)
        for i in range(1, 9)
    ]
    results = worker.execute_cases(cases, compile_limits=COMPILE_LIMITS, max_parallel=4)
    assert len(results) == 8
    assert all(r.status == "accepted" for r in results), [(r.status, r.stdout) for r in results]


def test_acm_stop_on_first_failure(worker):
    cases = [
        JudgeCase("cpp17", CPP_ECHO, stdin=b"1 1\n", expected_stdout=b"2\n", limits=LIMITS),
        JudgeCase("cpp17", CPP_ECHO, stdin=b"1 1\n", expected_stdout=b"3\n", limits=LIMITS),
        JudgeCase("cpp17", CPP_ECHO, stdin=b"1 1\n", expected_stdout=b"2\n", limits=LIMITS),
    ]
    results = worker.execute_cases(cases, compile_limits=COMPILE_LIMITS, stop_on_failure=True)
    assert [r.status for r in results] == ["accepted", "wrong_answer"]


def test_no_box_or_cgroup_leak_after_many_runs(worker):
    """连跑 60 次后池容量不变；关闭池后 box 目录与 cgroup 子组必须清理干净。"""
    before = worker.stats()
    for _ in range(60):
        assert _run(worker, CPP_ECHO, b"1 2\n", b"3\n").status == "accepted"
    after = worker.stats()
    assert after["pool_total"] == before["pool_total"] == 4
    assert after["pool_idle"] == 4

    # 用独立 box-id 区间建一个短期池：close() 之后不得残留 box 目录 / cgroup 子组
    base = 940
    short = JudgeWorker(IsolateExecutor("isolate", pool_size=2, box_id_base=base), worker.workspace_root)
    short.start()
    assert _run(short, CPP_ECHO, b"7 8\n", b"15\n").status == "accepted"
    short.close()

    cg_root = Path("/sys/fs/cgroup/isolate")
    if cg_root.is_dir():
        residual = sorted(p.name for p in cg_root.glob(f"box-{base}*"))
        assert not residual, residual

    isolate_boxes = Path("/var/local/lib/isolate")
    if isolate_boxes.is_dir():
        residual = sorted(
            p.name for p in isolate_boxes.iterdir() if p.name.isdigit() and int(p.name) >= base
        )
        assert not residual, residual


def test_isolate_version_reported(worker):
    stats = worker.stats()
    assert stats["backend"] == "isolate"
    assert stats["version"]

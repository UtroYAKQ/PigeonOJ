"""PigeonOJ 判题执行核心（独立副本，仅标准库依赖）。

运行于判题节点容器内（由 node/daemon.py 调用），编译 / 运行 / 比对语义
以 docs/contracts/judge.md 的「判题器执行规范」为准；修改时须同步该契约。
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Language = Literal["python3.12", "cpp17", "java21"]


@dataclass(frozen=True)
class ResourceLimits:
    time_limit_ms: int = 1000
    memory_limit_mb: int = 256
    output_limit_kb: int = 1024
    process_limit: int = 32
    cpu_cores: int = 1


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    stdout: bytes
    stderr: bytes
    time_used_ms: int
    memory_used_kb: int | None
    exit_code: int | None
    compile: bool = False


@dataclass(frozen=True)
class JudgeCase:
    language: Language
    source: bytes
    stdin: bytes
    expected_stdout: bytes | None
    limits: ResourceLimits = ResourceLimits()


class JudgeWorkerError(RuntimeError):
    """配置或执行器错误，不应把宿主机异常原文返回给用户。"""


class NsjailExecutor:
    """以一次性 nsjail 进程执行一个编译或运行阶段。

    节点固定运行在 Linux 容器内（pigeonoj/judge-node 镜像），nsjail 原生执行；
    工作区即容器内 /workspace（宿主机目录由 docker -v 挂载提供）。
    """

    def __init__(
        self,
        nsjail_binary: str = "nsjail",
        config_path: str | None = None,
    ) -> None:
        self.nsjail_binary = nsjail_binary
        self.config_path = config_path

    def build_args(self, command: list[str], *, time_limit_ms: int, as_limit_mb: int | None = None) -> list[str]:
        """组装完整 argv；独立成方法便于对包装逻辑做单元测试。

        as_limit_mb：地址空间硬上限（MB）。设为有效内存限制后，超内存分配会被内核
        直接拒绝（Python 抛 MemoryError / C++ 抛 bad_alloc），实现确定性 MLE 判定。
        """
        if not command or any("\x00" in part for part in command):
            raise JudgeWorkerError("invalid execution command")
        args: list[str] = [self.nsjail_binary]
        if self.config_path:
            args += ["--config", self.config_path]
        args += ["--time_limit", str(max(1, (time_limit_ms + 999) // 1000))]
        if as_limit_mb:
            # 覆盖 nsjail.cfg 的固定 rlimit_as，使内存上限随题目限制动态变化
            args += ["--rlimit_as", str(as_limit_mb)]
        args += ["--"]
        # nsjail 直接 execve 不做 PATH 查找；经 /bin/sh 转发以解析解释器路径
        command = ["/bin/sh", "-c", shlex.join(command)]
        args.extend(command)
        return args

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None,
        stdin: bytes,
        limits: ResourceLimits,
        output_limit: int,
        as_limit_mb: int | None = None,
    ) -> ExecutionResult:
        args = self.build_args(
            command, time_limit_ms=limits.time_limit_ms, as_limit_mb=as_limit_mb
        )
        started = time.monotonic()
        env = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/workspace"}
        try:
            proc = subprocess.Popen(
                args,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
        except (OSError, ValueError) as exc:
            raise JudgeWorkerError("nsjail execution failed") from exc

        import threading

        out_buf: list[bytes] = []
        err_buf: list[bytes] = []

        def _pump(pipe, buf):
            try:
                buf.append(pipe.read())
            except Exception:
                pass
            finally:
                try:
                    pipe.close()
                except Exception:
                    pass

        t_out = threading.Thread(target=_pump, args=(proc.stdout, out_buf), daemon=True)
        t_err = threading.Thread(target=_pump, args=(proc.stderr, err_buf), daemon=True)
        t_out.start(); t_err.start()
        try:
            proc.stdin.write(stdin)
            proc.stdin.close()
        except Exception:
            pass

        # 峰值 RSS 采样（契约口径：进程树峰值 RSS，docs/contracts/judge.md 执行规范）
        peak_kb = [0]
        stop = threading.Event()

        def _sampler():
            while not stop.is_set():
                total = _tree_rss_kb(proc.pid)
                if total > peak_kb[0]:
                    peak_kb[0] = total
                stop.wait(0.01)

        sampler = threading.Thread(target=_sampler, daemon=True)
        sampler.start()

        timed_out = False
        try:
            returncode = proc.wait(timeout=max(1, limits.time_limit_ms / 1000 + 1))
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            returncode = proc.wait()

        stop.set(); sampler.join(timeout=1)
        t_out.join(timeout=1); t_err.join(timeout=1)
        stdout_raw = b"".join(out_buf)
        stderr_raw = b"".join(err_buf)

        elapsed = _elapsed_ms(started)
        stdout = _cap(stdout_raw, output_limit)
        stderr = _strip_nsjail_logs(_cap(stderr_raw, output_limit))
        mem_kb = peak_kb[0] or None
        mem_limit_kb = limits.memory_limit_mb * 1024

        if timed_out or elapsed > limits.time_limit_ms:
            status = "time_limit_exceeded"
        elif mem_kb is not None and mem_kb > mem_limit_kb:
            status = "memory_limit_exceeded"
        elif len(stdout_raw) > output_limit or len(stderr_raw) > output_limit:
            status = "output_limit_exceeded"
        elif returncode != 0 and (
            b"MemoryError" in stderr_raw
            or b"std::bad_alloc" in stderr_raw
            or b"OutOfMemoryError" in stderr_raw
            or b"Cannot allocate memory" in stderr_raw
        ):
            # 地址空间被 rlimit_as 封顶后，超内存分配的典型失败特征 → MLE
            status = "memory_limit_exceeded"
        elif returncode != 0:
            status = "runtime_error"
        else:
            status = "ok"
        return ExecutionResult(status, stdout, stderr, elapsed, mem_kb, returncode)


def _tree_rss_kb(root_pid: int) -> int:
    """统计 root_pid 及其全部后代的当前 RSS 总和（kB）；读取失败按 0 处理。"""
    try:
        children: dict[int, int] = {}
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                with open(f"/proc/{entry}/stat", "rb") as fh:
                    stat = fh.read().decode("utf-8", errors="replace")
                ppid = int(stat.rsplit(")", 1)[1].split()[1])
                children[int(entry)] = ppid
            except (OSError, ValueError, IndexError):
                continue
        total = 0
        stack = [root_pid]
        seen = set()
        while stack:
            pid = stack.pop()
            if pid in seen:
                continue
            seen.add(pid)
            try:
                with open(f"/proc/{pid}/status", "rb") as fh:
                    for line in fh:
                        if line.startswith(b"VmRSS:"):
                            total += int(line.split()[1])
                            break
            except OSError:
                continue
            stack.extend(pid for p, pp in children.items() if pp == pid)
        return total
    except Exception:
        return 0


class PreparedSubmission:
    """一个提交的临时工作区和已完成编译的产物。"""

    def __init__(
        self,
        worker: "JudgeWorker",
        language: Language,
        source: bytes,
        compile_limits: ResourceLimits,
    ) -> None:
        self.worker = worker
        self.language = language
        self.compile_limits = compile_limits
        if worker.workspace_root:
            Path(worker.workspace_root).mkdir(parents=True, exist_ok=True)
        self._tempdir = tempfile.TemporaryDirectory(prefix="pigeonoj-judge-", dir=worker.workspace_root)
        self.workdir = Path(self._tempdir.name)
        source_name, self.run_command, self.compile_command = _commands(language, self._jail_workdir())
        (self.workdir / source_name).write_bytes(source)
        self.compile_result: ExecutionResult | None = None
        self._closed = False
        if self.compile_command:
            self.compile_result = worker.executor.run(
                self.compile_command,
                cwd=self.workdir,
                stdin=b"",
                limits=compile_limits,
                output_limit=compile_limits.output_limit_kb * 1024,
                # JVM 虚拟地址预留远大于堆，编译期不施加 AS 封顶（java 无编译阶段，此参数对 python/cpp 生效）
                as_limit_mb=None if language == "java21" else compile_limits.memory_limit_mb,
            )

    def _jail_workdir(self) -> str:
        """把宿主机工作目录映射为 nsjail 内的 /workspace 路径。"""
        root = Path(self.worker.workspace_root or "/workspace").resolve()
        try:
            relative = self.workdir.relative_to(root)
        except ValueError as exc:
            raise JudgeWorkerError("workspace must be inside JUDGE_WORKSPACE_ROOT") from exc
        return str(Path("/workspace") / relative).replace("\\", "/")

    @property
    def compile_failed(self) -> bool:
        return self.compile_result is not None and self.compile_result.status != "ok"

    def run_case(self, stdin: bytes, expected_stdout: bytes | None, limits: ResourceLimits) -> ExecutionResult:
        if self._closed:
            raise JudgeWorkerError("submission workspace is closed")
        if self.compile_failed:
            assert self.compile_result is not None
            return ExecutionResult(
                "compile_error" if self.compile_result.status == "runtime_error" else self.compile_result.status,
                b"",
                self.compile_result.stderr,
                self.compile_result.time_used_ms,
                self.compile_result.memory_used_kb,
                self.compile_result.exit_code,
                compile=True,
            )
        result = self.worker.executor.run(
            self.run_command,
            cwd=self.workdir,
            stdin=stdin,
            limits=limits,
            output_limit=limits.output_limit_kb * 1024,
            as_limit_mb=None if self.language == "java21" else limits.memory_limit_mb,
        )
        if result.status != "ok":
            return result
        if expected_stdout is not None:
            return ExecutionResult(
                "accepted" if _same_output(result.stdout, expected_stdout) else "wrong_answer",
                result.stdout, result.stderr, result.time_used_ms, result.memory_used_kb, result.exit_code,
            )
        return result

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._tempdir.cleanup()

    def __enter__(self) -> "PreparedSubmission":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


class JudgeWorker:
    """准备提交工作区，编译一次，然后逐测试点运行。"""

    def __init__(self, executor: NsjailExecutor | None = None, workspace_root: str | None = None) -> None:
        self.executor = executor or NsjailExecutor()
        self.workspace_root = workspace_root

    def prepare_submission(
        self, language: Language, source: bytes, compile_limits: ResourceLimits | None = None
    ) -> PreparedSubmission:
        limits = compile_limits or ResourceLimits(time_limit_ms=10_000)
        _validate_source(source)
        _validate_limits(limits)
        return PreparedSubmission(self, language, source, limits)

    def execute_cases(self, cases: list[JudgeCase], compile_limits: ResourceLimits | None = None) -> list[ExecutionResult]:
        if not cases:
            return []
        language = cases[0].language
        if any(case.language != language for case in cases):
            raise JudgeWorkerError("one submission cannot mix languages")
        compile_limits = compile_limits or ResourceLimits(time_limit_ms=10_000)
        with self.prepare_submission(language, cases[0].source, compile_limits) as submission:
            results: list[ExecutionResult] = []
            for case in cases:
                _validate_case(case)
                results.append(submission.run_case(case.stdin, case.expected_stdout, case.limits))
                if results[-1].status in {"compile_error", "system_error"}:
                    break
            return results

    def execute_case(self, case: JudgeCase) -> ExecutionResult:
        """兼容单测试点调用；正式判题请使用 execute_cases。"""
        results = self.execute_cases([case])
        if not results:
            raise JudgeWorkerError("empty case")
        return results[0]


def _commands(language: Language, jail_dir: str) -> tuple[str, list[str], list[str] | None]:
    """编译 / 运行命令。工具链使用绝对路径（沙箱镜像 ubuntu:24.04 布局）：

    - gcc 驱动从 argv[0] 推导安装前缀，裸名调用在 nsjail 下推导失败，
      cc1plus / ld 会退化为 PATH 搜索并报 execvp ENOENT；
      `-B/usr/bin/` 让 collect2 直接命中链接器。
    - OpenJDK launcher 沿符号链定位 JAVA_HOME，/usr/bin/javac 解析失败报
      libjli.so 缺失；直接调用 alternatives 的真实路径。
    绝对路径同时满足判题器对执行环境的确定性要求；语言级命令后续由
    sandbox_configs 配置化（docs/contracts/judge.md）。
    """
    if language == "python3.12":
        return "Main.py", ["/usr/bin/python3.12", f"{jail_dir}/Main.py"], None
    if language == "cpp17":
        return "Main.cpp", [f"{jail_dir}/Main"], ["/usr/bin/g++", "-B/usr/bin/", "-std=c++17", "-O2", "-pipe", "-o", f"{jail_dir}/Main", f"{jail_dir}/Main.cpp"]
    if language == "java21":
        return "Main.java", ["/usr/lib/jvm/java-21-openjdk-amd64/bin/java", "-Xmx256m", "-cp", jail_dir, "Main"], [
            "/usr/lib/jvm/java-21-openjdk-amd64/bin/javac", "-d", jail_dir, f"{jail_dir}/Main.java"
        ]
    raise JudgeWorkerError("unsupported language")


def _validate_source(source: bytes) -> None:
    if not source or len(source) > 64 * 1024:
        raise JudgeWorkerError("source size exceeds limit")


def _validate_limits(limits: ResourceLimits) -> None:
    if (
        limits.time_limit_ms <= 0
        or limits.memory_limit_mb <= 0
        or limits.output_limit_kb <= 0
        or limits.process_limit <= 0
        or limits.cpu_cores <= 0
    ):
        raise JudgeWorkerError("invalid resource limits")


def _validate_case(case: JudgeCase) -> None:
    _validate_source(case.source)
    _validate_limits(case.limits)


def _same_output(actual: bytes, expected: bytes) -> bool:
    def normalize(value: bytes) -> list[bytes]:
        return [line.rstrip() for line in value.replace(b"\r\n", b"\n").splitlines()]

    return normalize(actual) == normalize(expected)


def _cap(value: bytes, limit: int) -> bytes:
    return value[:limit]


# nsjail 自身日志行：[I][2026-08-23T08:30:43+0000][1] logParams():...
# [I]=info / [W]=warning 属沙箱内部信息，不属程序错误输出；[E]/[F] 保留用于定位执行器故障
_NSJAIL_LOG_RE = re.compile(r"^\[[IW]\]\[\d{4}-\d{2}-\d{2}T")


def _strip_nsjail_logs(stderr: bytes) -> bytes:
    """过滤 nsjail 的 info/warning 日志行，保留程序真实 stderr。"""
    if not stderr:
        return b""
    text = stderr.decode("utf-8", errors="replace")
    kept = [line for line in text.splitlines() if not _NSJAIL_LOG_RE.match(line)]
    return ("\n".join(kept) + "\n").encode("utf-8") if kept else b""


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


__all__ = [
    "ExecutionResult",
    "JudgeCase",
    "JudgeWorker",
    "JudgeWorkerError",
    "NsjailExecutor",
    "PreparedSubmission",
    "ResourceLimits",
]


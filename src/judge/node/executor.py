"""PigeonOJ 判题执行核心（独立副本，仅标准库依赖）。

运行于判题节点容器内（由 node/daemon.py 调用），编译 / 运行 / 比对语义
以 docs/contracts/judge.md 的「判题器执行规范」为准；修改时须同步该契约。
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
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
    # SPJ 判定信息（特判程序 stdout，≤2KB；非 SPJ 运行为空，docs/contracts/judge.md「SPJ 特判」）
    message: bytes = b""


@dataclass(frozen=True)
class JudgeCase:
    language: Language
    source: bytes
    stdin: bytes
    expected_stdout: bytes | None
    limits: ResourceLimits = ResourceLimits()


class JudgeWorkerError(RuntimeError):
    """配置或执行器错误，不应把宿主机异常原文返回给用户。"""


class SpjCompileError(JudgeWorkerError):
    """特判程序编译失败（题目数据问题 → 服务端按 system_error 处理）。"""


@dataclass(frozen=True)
class SpjProgram:
    """已编译特判程序（jail 内二进制绝对路径），每个提交作业编译一次。"""

    binary: str


# SPJ 特判文件名（作业目录内，jail 视角 /workspace/<relative>/...）
SPJ_SOURCE_NAME = "spj.cpp"
SPJ_BINARY_NAME = "spj"
# 特判运行时的三文件（testlib 风格 argv：input / user_out / answer）
_SPJ_INPUT_NAME = "spj_input"
_SPJ_USER_OUT_NAME = "spj_user_out"
_SPJ_ANSWER_NAME = "spj_answer"
# 特判程序 stdout 作为判定信息的截断上限（服务端再截 ≤2KB 落库）
_SPJ_MESSAGE_LIMIT = 2048
# testlib 退出码语义：_died=3 / _fail=4 为 checker 自身故障 → 平台错误；
# 0=accepted（_ok / _ac），其余（含 _wa=1、_pe=2、部分分 16+分值）= wrong_answer
_SPJ_FAILURE_EXIT_CODES = {3, 4}


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
        env = {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": "/workspace",
            # 编译驱动（gcc/libiberty choose_temp）与运行时临时文件统一落在 jail 内
            # tmpfs /tmp；禁写 pycache，避免向作业目录写入字节码噪音
            "TMPDIR": "/tmp",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
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
        source_path = self.workdir / source_name
        source_path.write_bytes(source)
        _grant_jail_access(self.workdir, source_path)
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

    def prepare_spj(self, source: bytes, compile_limits: ResourceLimits) -> SpjProgram:
        """编译题目特判程序（每个提交作业一次，与提交代码共用编译预算口径）。

        失败抛 SpjCompileError（不带编译器输出，防特判源码片段泄露给提交者）。
        """
        if self._closed:
            raise JudgeWorkerError("submission workspace is closed")
        if self.compile_failed:
            raise JudgeWorkerError("submission compile failed")
        src_path = self.workdir / SPJ_SOURCE_NAME
        src_path.write_bytes(source)
        binary_path = self.workdir / SPJ_BINARY_NAME
        _grant_jail_access(self.workdir, src_path)
        jail_dir = self._jail_workdir()
        # 与 cpp17 提交编译同款工具链参数（绝对路径，见 _commands 注释）
        command = [
            "/usr/bin/g++", "-B/usr/bin/", "-std=c++17", "-O2", "-pipe",
            "-o", f"{jail_dir}/{SPJ_BINARY_NAME}", f"{jail_dir}/{SPJ_SOURCE_NAME}",
        ]
        result = self.worker.executor.run(
            command,
            cwd=self.workdir,
            stdin=b"",
            limits=compile_limits,
            output_limit=compile_limits.output_limit_kb * 1024,
            as_limit_mb=compile_limits.memory_limit_mb,
        )
        if result.status != "ok":
            raise SpjCompileError("special judge program compile failed")
        _grant_jail_access(self.workdir, binary_path)
        return SpjProgram(binary=f"{jail_dir}/{SPJ_BINARY_NAME}")

    def run_case(
        self,
        stdin: bytes,
        expected_stdout: bytes | None,
        limits: ResourceLimits,
        *,
        spj: SpjProgram | None = None,
        spj_limits: ResourceLimits | None = None,
    ) -> ExecutionResult:
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
        if spj is not None:
            return self._judge_with_spj(result, stdin, expected_stdout, spj, spj_limits or limits)
        if expected_stdout is not None:
            return ExecutionResult(
                "accepted" if _same_output(result.stdout, expected_stdout) else "wrong_answer",
                result.stdout, result.stderr, result.time_used_ms, result.memory_used_kb, result.exit_code,
            )
        return result

    def _judge_with_spj(
        self,
        user_result: ExecutionResult,
        stdin: bytes,
        expected_stdout: bytes | None,
        spj: SpjProgram,
        spj_limits: ResourceLimits,
    ) -> ExecutionResult:
        """SPJ 判定：三文件 argv（input / user_out / answer）运行特判程序，退出码定论。

        用户程序已运行成功（status=ok）；此处仅判定。特判程序自身故障
        （超时 / 崩溃 / 输出超限 / testlib _died / _fail）→ 整个提交 system_error，
        stderr 不回传（防源码泄露，docs/contracts/judge.md「SPJ 特判」）。
        返回结果的 time / memory / stdout 保持用户程序口径（逐点落库依据）。
        """
        input_path = self.workdir / _SPJ_INPUT_NAME
        user_out_path = self.workdir / _SPJ_USER_OUT_NAME
        answer_path = self.workdir / _SPJ_ANSWER_NAME
        input_path.write_bytes(stdin)
        user_out_path.write_bytes(user_result.stdout)
        answer_path.write_bytes(expected_stdout or b"")
        _grant_jail_access(self.workdir, input_path, user_out_path, answer_path)
        jail_dir = self._jail_workdir()
        command = [spj.binary, f"{jail_dir}/{_SPJ_INPUT_NAME}", f"{jail_dir}/{_SPJ_USER_OUT_NAME}", f"{jail_dir}/{_SPJ_ANSWER_NAME}"]
        result = self.worker.executor.run(
            command,
            cwd=self.workdir,
            stdin=b"",
            limits=spj_limits,
            output_limit=max(_SPJ_MESSAGE_LIMIT * 8, spj_limits.output_limit_kb * 1024),
            as_limit_mb=spj_limits.memory_limit_mb,
        )
        return _spj_verdict(result, user_result)

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

    def execute_cases(
        self,
        cases: list[JudgeCase],
        compile_limits: ResourceLimits | None = None,
        *,
        stop_on_failure: bool = False,
        spj_source: bytes | None = None,
        spj_limits: ResourceLimits | None = None,
    ) -> list[ExecutionResult]:
        """编译一次后逐测试点运行。

        stop_on_failure（ACM 赛制短路）：首个非 accepted 测试点后停止执行，
        仅返回已执行测试点的结果（docs/contracts/judge.md「赛制计分」）。
        compile_error / system_error 属平台级故障，无论赛制均终止后续测试点。
        spj_source 非空：编译题目特判程序后逐点以 SPJ 判定替代默认比对
        （docs/contracts/judge.md「SPJ 特判」）。
        """
        if not cases:
            return []
        language = cases[0].language
        if any(case.language != language for case in cases):
            raise JudgeWorkerError("one submission cannot mix languages")
        compile_limits = compile_limits or ResourceLimits(time_limit_ms=10_000)
        with self.prepare_submission(language, cases[0].source, compile_limits) as submission:
            spj: SpjProgram | None = None
            if spj_source is not None:
                spj = submission.prepare_spj(spj_source, compile_limits)
            results: list[ExecutionResult] = []
            for case in cases:
                _validate_case(case)
                results.append(submission.run_case(
                    case.stdin, case.expected_stdout, case.limits,
                    spj=spj, spj_limits=spj_limits,
                ))
                if results[-1].status in {"compile_error", "system_error"}:
                    break
                if stop_on_failure and results[-1].status != "accepted":
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
        # JVM 崩溃日志（hs_err）默认写 cwd，重定向到 /tmp 避免污染工作区
        return "Main.java", [
            "/usr/lib/jvm/java-21-openjdk-amd64/bin/java", "-XX:ErrorFile=/tmp/hs_err_pid%p.log",
            "-Xmx256m", "-cp", jail_dir, "Main",
        ], [
            "/usr/lib/jvm/java-21-openjdk-amd64/bin/javac", "-J-XX:ErrorFile=/tmp/hs_err_pid%p.log",
            "-d", jail_dir, f"{jail_dir}/Main.java",
        ]
    raise JudgeWorkerError("unsupported language")


_JAIL_UID = 65534  # nobody：预留的沙箱内执行身份（当前 nsjail 默认映射仍为全局 root）


def _grant_jail_access(workdir: Path, *files: Path) -> None:
    """保证沙箱内进程可在作业目录产出编译物。

    仅在 Linux root（判题节点容器）下生效；开发机跳过。目录最终态为
    「属主 nobody + 0777」，同时覆盖三类执行身份语义：
    - 未来把 nsjail 映射收紧为 nobody 时：属主位即可写；
    - Docker Desktop 等文件共享层：按元数据属主严格判 DAC 且不提供 root
      旁路，须依赖 other 写位；
    - 现行默认（clone_newuser 映射 0→0，进程具全局 root 文件访问）：任意
      权限均可写。
    每个提交使用一次性独立目录，放开 other 位不构成额外攻击面。
    """
    if sys.platform != "linux" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        return
    try:
        for path in (workdir, *files):
            os.chown(path, _JAIL_UID, _JAIL_UID)
        os.chmod(workdir, 0o777)
    except OSError:
        pass


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


def _spj_verdict(spj_result: ExecutionResult, user_result: ExecutionResult) -> ExecutionResult:
    """SPJ 退出码 → 判定（docs/contracts/judge.md「SPJ 特判」）：

    特判程序自身故障（超时 / 崩溃 / 输出超限 / testlib _died=3 / _fail=4）→ system_error；
    退出码 0 → accepted；其余（含 _wa=1、_pe=2、不支持的部分分 16+分值）→ wrong_answer。
    time / memory / stdout 保持用户程序口径；特判 stdout（≤2KB）作 message。
    """
    if spj_result.status != "ok" or spj_result.exit_code in _SPJ_FAILURE_EXIT_CODES:
        return ExecutionResult(
            "system_error", user_result.stdout, b"",
            user_result.time_used_ms, user_result.memory_used_kb, spj_result.exit_code,
        )
    status = "accepted" if spj_result.exit_code == 0 else "wrong_answer"
    return ExecutionResult(
        status, user_result.stdout, user_result.stderr,
        user_result.time_used_ms, user_result.memory_used_kb, user_result.exit_code,
        message=_cap(spj_result.stdout, _SPJ_MESSAGE_LIMIT),
    )


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
    "SPJ_SOURCE_NAME",
    "SpjCompileError",
    "SpjProgram",
]


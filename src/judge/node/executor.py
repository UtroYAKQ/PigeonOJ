"""PigeonOJ 判题执行核心（独立副本，仅标准库依赖）。

运行于判题节点容器内（由 node/daemon.py 调用），编译 / 运行 / 比对语义
以 docs/contracts/judge.md 的「判题器执行规范」为准；修改时须同步该契约。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    stdin: bytes = b""
    expected_stdout: bytes | None = None
    limits: ResourceLimits = ResourceLimits()
    stdin_path: Path | None = None
    expected_path: Path | None = None

    def load_stdin(self) -> bytes:
        if self.stdin_path is not None:
            return self.stdin_path.read_bytes()
        return self.stdin

    def load_expected(self) -> bytes | None:
        if self.expected_path is not None:
            return self.expected_path.read_bytes()
        return self.expected_stdout


class JudgeWorkerError(RuntimeError):
    """配置或执行器错误，不应把宿主机异常原文返回给用户。"""


class SpjCompileError(JudgeWorkerError):
    """特判程序编译失败（题目数据问题 → 服务端按 system_error 处理）。"""


@dataclass(frozen=True)
class SpjProgram:
    """已编译特判程序（jail 内二进制绝对路径），每个提交作业编译一次。"""

    binary: str


# jail 内工作区：每次调用只 bind 本作业目录到 /workspace（不再挂整棵宿主机 /workspace）
_JAIL_WORKSPACE = "/workspace"
# SPJ 特判文件名（作业目录内，jail 视角 /workspace/...）
SPJ_SOURCE_NAME = "spj.cpp"
SPJ_BINARY_NAME = "spj"
_PIPE_READ_CHUNK = 65536
_SIGXCPU = 24
_DEFAULT_CASE_PARALLEL = 4
_FATAL_CASE_STATUSES = frozenset({"compile_error", "system_error"})
# 特判运行时的三文件（testlib 风格 argv：input / user_out / answer）
_SPJ_INPUT_NAME = "spj_input"
_SPJ_USER_OUT_NAME = "spj_user_out"
_SPJ_ANSWER_NAME = "spj_answer"
# 特判程序 stdout 作为判定信息的截断上限（服务端再截 ≤2KB 落库）
_SPJ_MESSAGE_LIMIT = 2048
# testlib 退出码语义：_died=3 / _fail=4 为 checker 自身故障 → 平台错误；
# 0=accepted（_ok / _ac），其余（含 _wa=1、_pe=2、部分分 16+分值）= wrong_answer
_SPJ_FAILURE_EXIT_CODES = {3, 4}

_CGROUP_V2_ROOT = Path("/sys/fs/cgroup")
_CGROUP_DAEMON_LEAF = "pigeonoj-daemon"
_CGROUP_JOB_PREFIX = "pigeonoj."
_RSS_SAMPLE_INTERVAL_S = 0.05


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

    def build_args(
        self,
        command: list[str],
        *,
        time_limit_ms: int,
        as_limit_mb: int | None = None,
        bind_src: str | None = None,
        process_limit: int | None = None,
        cpu_cores: int | None = None,
    ) -> list[str]:
        """组装完整 argv；独立成方法便于对包装逻辑做单元测试。

        as_limit_mb：地址空间硬上限（MB）。设为有效内存限制后，超内存分配会被内核
        直接拒绝（Python 抛 MemoryError / C++ 抛 bad_alloc），实现确定性 MLE 判定。
        command 必须是绝对路径 argv（工具链与 jail 内产物），直接交给 nsjail execve，
        不再经 /bin/sh。
        """
        if not command or any("\x00" in part for part in command):
            raise JudgeWorkerError("invalid execution command")
        args: list[str] = [self.nsjail_binary]
        if self.config_path:
            args += ["--config", self.config_path]
        if bind_src:
            args += ["--bindmount", f"{bind_src}:{_JAIL_WORKSPACE}"]
        limit_s = max(1, (time_limit_ms + 999) // 1000)
        args += ["--time_limit", str(limit_s), "--rlimit_cpu", str(limit_s)]
        if as_limit_mb:
            args += ["--rlimit_as", str(as_limit_mb)]
        if process_limit:
            args += ["--rlimit_nproc", str(process_limit)]
        if cpu_cores:
            args += ["--max_cpus", str(cpu_cores)]
        args += ["--"]
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
            command,
            time_limit_ms=limits.time_limit_ms,
            as_limit_mb=as_limit_mb,
            bind_src=str(cwd) if cwd is not None else None,
            process_limit=limits.process_limit,
            cpu_cores=limits.cpu_cores,
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
        job_cgroup = _create_job_cgroup()
        popen_kwargs: dict = {}
        if job_cgroup is not None and sys.platform != "win32":
            popen_kwargs["preexec_fn"] = _cgroup_preexec(job_cgroup)
        try:
            proc = subprocess.Popen(
                args,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                **popen_kwargs,
            )
        except (OSError, ValueError) as exc:
            if job_cgroup is not None:
                _release_job_cgroup(job_cgroup)
            raise JudgeWorkerError("nsjail execution failed") from exc
        if job_cgroup is not None and not _cgroup_contains_pid(job_cgroup, proc.pid):
            _release_job_cgroup(job_cgroup)
            job_cgroup = None

        out_buf: list[bytes] = []
        err_buf: list[bytes] = []
        overflow = threading.Event()

        def _pump(pipe, buf):
            try:
                data, exceeded = _read_limited(pipe, output_limit)
                buf.append(data)
                if exceeded:
                    overflow.set()
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

        # 峰值内存：优先每 jail 一个 cgroup v2 叶子读 memory.current；
        # 不可用时沿 nsjail 进程树读 VmRSS（不再扫宿主机全部 /proc）
        peak_kb = [0]
        stop = threading.Event()

        def _sampler():
            while not stop.is_set():
                total = (
                    _cgroup_usage_kb(job_cgroup)
                    if job_cgroup is not None
                    else _tree_rss_kb(proc.pid)
                )
                if total > peak_kb[0]:
                    peak_kb[0] = total
                stop.wait(_RSS_SAMPLE_INTERVAL_S)

        sampler = threading.Thread(target=_sampler, daemon=True)
        sampler.start()

        timed_out = False
        output_exceeded = False
        deadline = started + max(0.05, limits.time_limit_ms / 1000 + 0.1)
        returncode = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                proc.kill()
                returncode = proc.wait()
                break
            if overflow.is_set():
                output_exceeded = True
                proc.kill()
                returncode = proc.wait()
                break
            try:
                returncode = proc.wait(timeout=min(_RSS_SAMPLE_INTERVAL_S, remaining))
                break
            except subprocess.TimeoutExpired:
                continue

        stop.set(); sampler.join(timeout=1)
        t_out.join(timeout=1); t_err.join(timeout=1)
        stdout_raw = b"".join(out_buf)
        stderr_raw = b"".join(err_buf)

        elapsed = _elapsed_ms(started)
        stdout = _cap(stdout_raw, output_limit)
        stderr = _strip_nsjail_logs(_cap(stderr_raw, output_limit))
        if job_cgroup is not None:
            final_kb = _cgroup_peak_kb(job_cgroup)
            if final_kb > peak_kb[0]:
                peak_kb[0] = final_kb
            _release_job_cgroup(job_cgroup)
        mem_kb = peak_kb[0] or None
        mem_limit_kb = limits.memory_limit_mb * 1024

        if timed_out or elapsed > limits.time_limit_ms or _is_cpu_tle(returncode):
            status = "time_limit_exceeded"
        elif mem_kb is not None and mem_kb > mem_limit_kb:
            status = "memory_limit_exceeded"
        elif output_exceeded or len(stdout_raw) > output_limit or len(stderr_raw) > output_limit:
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


def _read_limited(pipe, limit: int) -> tuple[bytes, bool]:
    """读到 EOF 或 limit+1 字节。exceeded=True 表示还有数据（OLE，不再继续读）。"""
    buf = bytearray()
    while True:
        room = (limit + 1) - len(buf)
        if room <= 0:
            return bytes(buf), True
        chunk = pipe.read(min(_PIPE_READ_CHUNK, room))
        if not chunk:
            return bytes(buf), len(buf) > limit
        buf.extend(chunk)


def _is_cpu_tle(returncode: int | None) -> bool:
    """rlimit_cpu 触发 SIGXCPU：负信号或 128+signal。"""
    if returncode is None:
        return False
    return returncode in (-_SIGXCPU, 128 + _SIGXCPU)


_cgroup_parent_resolved: Path | None = None
_cgroup_parent_attempted = False
_cgroup_parent_lock = threading.Lock()
_job_cgroup_seq = 0
_job_cgroup_lock = threading.Lock()


def _reset_cgroup_parent_for_tests() -> None:
    global _cgroup_parent_resolved, _cgroup_parent_attempted
    with _cgroup_parent_lock:
        _cgroup_parent_resolved = None
        _cgroup_parent_attempted = False


def _self_cgroup_v2_path(
    *,
    proc_cgroup: str = "/proc/self/cgroup",
    v2_root: Path = _CGROUP_V2_ROOT,
) -> Path | None:
    """解析本进程在 cgroup v2 统一层级中的目录；非 v2 或读取失败返回 None。"""
    if not (v2_root / "cgroup.controllers").is_file():
        return None
    try:
        with open(proc_cgroup, encoding="ascii") as fh:
            for line in fh:
                # v2：`0::/docker/<id>`；v1 控制器行不含空层级
                if line.startswith("0::"):
                    rel = line.split(":", 2)[2].strip().lstrip("/")
                    return v2_root / rel if rel else v2_root
    except OSError:
        return None
    return None


def _enable_memory_controller(parent: Path) -> bool:
    """在 parent 上打开 memory 子树控制器。先把本进程挪进叶子，避开 no-internal-process。"""
    control = parent / "cgroup.subtree_control"
    try:
        current = control.read_text(encoding="ascii")
    except OSError:
        return False
    if "memory" in current.split():
        return True
    daemon_leaf = parent / _CGROUP_DAEMON_LEAF
    try:
        daemon_leaf.mkdir(exist_ok=True)
        (daemon_leaf / "cgroup.procs").write_text("0", encoding="ascii")
    except OSError:
        pass
    try:
        control.write_text("+memory", encoding="ascii")
        return True
    except OSError:
        return False


def _cgroup_parent() -> Path | None:
    """容器 cgroup v2 目录（已启用 memory 子控制器）；不可用则 None，采样回退进程树。"""
    global _cgroup_parent_resolved, _cgroup_parent_attempted
    with _cgroup_parent_lock:
        if _cgroup_parent_attempted:
            return _cgroup_parent_resolved
        _cgroup_parent_attempted = True
        parent = _self_cgroup_v2_path()
        if parent is None or not _enable_memory_controller(parent):
            _cgroup_parent_resolved = None
            return None
        _cgroup_parent_resolved = parent
        return parent


def _create_job_cgroup() -> Path | None:
    """为一次 nsjail 调用建叶子 cgroup；失败返回 None。"""
    global _job_cgroup_seq
    parent = _cgroup_parent()
    if parent is None:
        return None
    with _job_cgroup_lock:
        _job_cgroup_seq += 1
        seq = _job_cgroup_seq
    path = parent / f"{_CGROUP_JOB_PREFIX}{os.getpid()}.{seq}"
    try:
        path.mkdir(exist_ok=True)
    except OSError:
        return None
    return path


def _cgroup_preexec(path: Path):
    """fork 后、exec nsjail 前把子进程写入叶子 cgroup，使后续 clone 继承。

    只使用 open/write/close：父进程是多线程（asyncio + to_thread），
    preexec 里走 Python 缓冲 IO 可能死锁。
    """
    procs = f"{path}/cgroup.procs"

    def _inner() -> None:
        fd = -1
        try:
            fd = os.open(procs, os.O_WRONLY | os.O_CLOEXEC)
            os.write(fd, str(os.getpid()).encode("ascii"))
        except OSError:
            pass
        finally:
            if fd >= 0:
                os.close(fd)

    return _inner


def _cgroup_contains_pid(path: Path, pid: int) -> bool:
    try:
        return str(pid) in (path / "cgroup.procs").read_text(encoding="ascii").split()
    except OSError:
        return False


def _cgroup_usage_kb(path: Path) -> int:
    try:
        return max(0, int((path / "memory.current").read_bytes().strip()) // 1024)
    except (OSError, ValueError):
        return 0


def _cgroup_peak_kb(path: Path) -> int:
    """优先 memory.peak（内核累计峰值）；没有则退回当前值。"""
    try:
        return max(0, int((path / "memory.peak").read_bytes().strip()) // 1024)
    except (OSError, ValueError):
        return _cgroup_usage_kb(path)


def _release_job_cgroup(path: Path) -> None:
    # 父节点已开 subtree_control 后不能再挂进程；残留 pid 挪到 daemon 叶子
    fallback = path.parent / _CGROUP_DAEMON_LEAF
    if not fallback.is_dir():
        fallback = path.parent
    try:
        leftover = (path / "cgroup.procs").read_text(encoding="ascii").split()
        for pid in leftover:
            try:
                (fallback / "cgroup.procs").write_text(pid, encoding="ascii")
            except OSError:
                pass
    except OSError:
        pass
    try:
        path.rmdir()
        return
    except OSError:
        pass
    try:
        for child in path.iterdir():
            try:
                child.unlink()
            except OSError:
                pass
        path.rmdir()
    except OSError:
        pass


def _pid_rss_kb(pid: int, *, proc_root: str = "/proc") -> int:
    try:
        with open(f"{proc_root}/{pid}/status", "rb") as fh:
            for line in fh:
                if line.startswith(b"VmRSS:"):
                    return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        return 0
    return 0


def _pid_children(pid: int, *, proc_root: str = "/proc") -> list[int]:
    children: list[int] = []
    try:
        for tid in os.listdir(f"{proc_root}/{pid}/task"):
            try:
                with open(f"{proc_root}/{pid}/task/{tid}/children", encoding="ascii") as fh:
                    children.extend(int(x) for x in fh.read().split())
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return children


def _tree_rss_kb(root_pid: int, *, proc_root: str = "/proc") -> int:
    """沿 root_pid 进程树累计 VmRSS（kB）。只走 task/children，不扫宿主机全部 /proc。"""
    total = 0
    stack = [root_pid]
    seen: set[int] = set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        total += _pid_rss_kb(pid, proc_root=proc_root)
        stack.extend(_pid_children(pid, proc_root=proc_root))
    return total


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
        source_name, self.run_command, self.compile_command = _commands(
            language, self._jail_workdir(), memory_limit_mb=compile_limits.memory_limit_mb
        )
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

    def _jail_bind_src(self) -> str:
        """宿主机作业目录；必须落在 workspace_root 下，供 --bindmount 到 /workspace。"""
        root = Path(self.worker.workspace_root or "/workspace").resolve()
        workdir = self.workdir.resolve()
        try:
            workdir.relative_to(root)
        except ValueError as exc:
            raise JudgeWorkerError("workspace must be inside JUDGE_WORKSPACE_ROOT") from exc
        return str(workdir)

    def _jail_workdir(self) -> str:
        self._jail_bind_src()
        return _JAIL_WORKSPACE

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
        file_tag: str = "",
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
        _, run_command, _ = _commands(
            self.language, self._jail_workdir(), memory_limit_mb=limits.memory_limit_mb
        )
        result = self.worker.executor.run(
            run_command,
            cwd=self.workdir,
            stdin=stdin,
            limits=limits,
            output_limit=limits.output_limit_kb * 1024,
            as_limit_mb=None if self.language == "java21" else limits.memory_limit_mb,
        )
        if result.status != "ok":
            return result
        if spj is not None:
            return self._judge_with_spj(
                result, stdin, expected_stdout, spj, spj_limits or limits, file_tag=file_tag
            )
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
        file_tag: str = "",
    ) -> ExecutionResult:
        """SPJ 判定：三文件 argv（input / user_out / answer）运行特判程序，退出码定论。

        用户程序已运行成功（status=ok）；此处仅判定。特判程序自身故障
        （超时 / 崩溃 / 输出超限 / testlib _died / _fail）→ 整个提交 system_error，
        stderr 不回传（防源码泄露，docs/contracts/judge.md「SPJ 特判」）。
        返回结果的 time / memory / stdout 保持用户程序口径（逐点落库依据）。
        """
        in_name, out_name, ans_name = _spj_file_names(file_tag)
        input_path = self.workdir / in_name
        user_out_path = self.workdir / out_name
        answer_path = self.workdir / ans_name
        input_path.write_bytes(stdin)
        user_out_path.write_bytes(user_result.stdout)
        answer_path.write_bytes(expected_stdout or b"")
        _grant_jail_access(self.workdir, input_path, user_out_path, answer_path)
        jail_dir = self._jail_workdir()
        command = [spj.binary, f"{jail_dir}/{in_name}", f"{jail_dir}/{out_name}", f"{jail_dir}/{ans_name}"]
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
        cancel_event: threading.Event | None = None,
        max_parallel: int = _DEFAULT_CASE_PARALLEL,
    ) -> list[ExecutionResult]:
        """编译一次后运行测试点。

        stop_on_failure（ACM 赛制短路）：串行，首个非 accepted 后停止。
        IOI / 练习 / 验题：同作业有限并行（默认 4）；compile_error / system_error
        结束后续批次。cancel_event 在批次边界生效（docs/contracts/judge.md）。
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
            workers = 1 if stop_on_failure else max(1, max_parallel)
            if workers == 1:
                return _run_cases_serial(
                    submission, cases, spj=spj, spj_limits=spj_limits,
                    stop_on_failure=stop_on_failure, cancel_event=cancel_event,
                )
            return _run_cases_parallel(
                submission, cases, spj=spj, spj_limits=spj_limits,
                max_workers=workers, cancel_event=cancel_event,
            )

    def execute_case(self, case: JudgeCase) -> ExecutionResult:
        """兼容单测试点调用；正式判题请使用 execute_cases。"""
        results = self.execute_cases([case])
        if not results:
            raise JudgeWorkerError("empty case")
        return results[0]


def _spj_file_names(file_tag: str) -> tuple[str, str, str]:
    suffix = f".{file_tag}" if file_tag else ""
    return f"{_SPJ_INPUT_NAME}{suffix}", f"{_SPJ_USER_OUT_NAME}{suffix}", f"{_SPJ_ANSWER_NAME}{suffix}"


def _run_one_case(
    submission: PreparedSubmission,
    index: int,
    case: JudgeCase,
    *,
    spj: SpjProgram | None,
    spj_limits: ResourceLimits | None,
) -> ExecutionResult:
    _validate_case(case)
    return submission.run_case(
        case.load_stdin(), case.load_expected(), case.limits,
        spj=spj, spj_limits=spj_limits, file_tag=str(index),
    )


def _run_cases_serial(
    submission: PreparedSubmission,
    cases: list[JudgeCase],
    *,
    spj: SpjProgram | None,
    spj_limits: ResourceLimits | None,
    stop_on_failure: bool,
    cancel_event: threading.Event | None,
) -> list[ExecutionResult]:
    results: list[ExecutionResult] = []
    for index, case in enumerate(cases):
        if cancel_event is not None and cancel_event.is_set():
            break
        results.append(_run_one_case(submission, index, case, spj=spj, spj_limits=spj_limits))
        if results[-1].status in _FATAL_CASE_STATUSES:
            break
        if stop_on_failure and results[-1].status != "accepted":
            break
    return results


def _run_cases_parallel(
    submission: PreparedSubmission,
    cases: list[JudgeCase],
    *,
    spj: SpjProgram | None,
    spj_limits: ResourceLimits | None,
    max_workers: int,
    cancel_event: threading.Event | None,
) -> list[ExecutionResult]:
    ordered: list[ExecutionResult | None] = [None] * len(cases)
    stop_more = False
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for start in range(0, len(cases), max_workers):
            if stop_more or (cancel_event is not None and cancel_event.is_set()):
                break
            batch = list(enumerate(cases[start:start + max_workers], start=start))
            futs = {
                pool.submit(
                    _run_one_case, submission, index, case, spj=spj, spj_limits=spj_limits
                ): index
                for index, case in batch
            }
            for fut in as_completed(futs):
                index = futs[fut]
                ordered[index] = fut.result()
                if ordered[index] is not None and ordered[index].status in _FATAL_CASE_STATUSES:
                    stop_more = True
    return [item for item in ordered if item is not None]


def _java_xmx_mb(memory_limit_mb: int) -> int:
    return max(1, memory_limit_mb)


def _commands(
    language: Language, jail_dir: str, *, memory_limit_mb: int = 256
) -> tuple[str, list[str], list[str] | None]:
    """编译 / 运行命令。工具链使用绝对路径（沙箱镜像 ubuntu:24.04 布局）：

    - gcc 驱动从 argv[0] 推导安装前缀，裸名调用在 nsjail 下推导失败，
      cc1plus / ld 会退化为 PATH 搜索并报 execvp ENOENT；
      `-B/usr/bin/` 让 collect2 直接命中链接器。
    - OpenJDK launcher 沿符号链定位 JAVA_HOME，/usr/bin/javac 解析失败报
      libjli.so 缺失；直接调用 alternatives 的真实路径。
    绝对路径同时满足判题器对执行环境的确定性要求；语言级命令后续由
    sandbox_configs 配置化（docs/contracts/judge.md）。
    Java `-Xmx` 按有效内存换算（契约：运行时参数，判据仍为 RSS）。
    """
    if language == "python3.12":
        return "Main.py", ["/usr/bin/python3.12", f"{jail_dir}/Main.py"], None
    if language == "cpp17":
        return "Main.cpp", [f"{jail_dir}/Main"], ["/usr/bin/g++", "-B/usr/bin/", "-std=c++17", "-O2", "-pipe", "-o", f"{jail_dir}/Main", f"{jail_dir}/Main.cpp"]
    if language == "java21":
        xmx = _java_xmx_mb(memory_limit_mb)
        return "Main.java", [
            "/usr/lib/jvm/java-21-openjdk-amd64/bin/java", "-XX:ErrorFile=/tmp/hs_err_pid%p.log",
            f"-Xmx{xmx}m", "-cp", jail_dir, "Main",
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


"""PigeonOJ 判题执行核心（独立副本，仅标准库依赖）。

运行于判题节点容器内（由 node/daemon.py 调用），编译 / 运行 / 比对语义
以 docs/contracts.md §10 的「判题器执行规范」为准；修改时须同步该契约。

沙箱后端为 isolate（IOI 官方沙箱，cgroup v2）：box 预初始化池化复用，
限流由内核（cgroup + rlimit）记账后经 meta 文件回读。
"""
from __future__ import annotations

import io
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from typing import Iterator, Literal, Sequence

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
    # SPJ 判定信息（特判程序 stdout，≤2KB；非 SPJ 运行为空，docs/contracts.md §10.6）
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
    """已编译特判程序（沙箱内二进制绝对路径），每个提交作业编译一次。"""

    binary: str


# ---- 沙箱内路径约定 ----
# isolate 默认目录规则：box 目录 rw 绑定为沙箱 /box（进程 chdir 到此），
# /tmp 另挂 rw tmpfs（不在 box 目录内）。宿主机侧 /box 对应 `<box目录>/box`。
BOX_ROOT = "/box"
TMP_ROOT = "/tmp"
OUT_DIR = "/box/out"      # 编译产物落地目录（box 可写区，编译后拷回作业目录）
_PROG = "/box/prog"       # 本作业目录（源码 / 编译产物 / 特判程序），只读挂载
_DATA = "/box/data"       # 测试点 / 特判三文件目录，只读挂载（同宿主 inode，零拷贝）
# C++ 预编译头目录：isolate 默认只读挂载 /usr，沙箱内同路径可见（见 Dockerfile）
_CXX_PCH = "/usr/local/lib/cxx-pch"

# box 目录内的相对名（宿主机 `<box>/box/<name>` 与沙箱 `/box/<name>` 同名）
_OUT_NAME = "out"
_STDIN_NAME = "stdin"
_STDOUT_NAME = "stdout"
_STDERR_NAME = "stderr"
_META_NAME = "meta"

_SPJ_SOURCE_NAME = "spj.cpp"
SPJ_SOURCE_NAME = _SPJ_SOURCE_NAME
_SPJ_BINARY_NAME = "spj"
# 题目数据缓存目录内的已编译特判二进制（按 problem_id-data_version 隔离）
SPJ_CACHE_NAME = "spj.bin"

_SIGXFSZ = 25
_DEFAULT_CASE_PARALLEL = 4
_DEFAULT_BOX_POOL = 10
_FATAL_CASE_STATUSES = frozenset({"compile_error", "system_error"})
# 特判程序 stdout 作为判定信息的截断上限（服务端再截 ≤2KB 落库）
_SPJ_MESSAGE_LIMIT = 2048
# testlib 退出码语义：_died=3 / _fail=4 为 checker 自身故障 → 平台错误
_SPJ_FAILURE_EXIT_CODES = {3, 4}
# 编译期文件大小上限（KB）：不按输出上限收紧，避免中间产物被 SIGXFSZ
_COMPILE_FSIZE_KB = 64 * 1024
# 编译期进程数：g++ 驱动要 fork cc1plus 与 ld（cc1plus 自身还会起子进程），
# 题目级 process_limit 通常只按运行阶段给（8~32），直接复用会让编译报
# "vfork: Resource temporarily unavailable"。编译阶段统一放宽。
_COMPILE_PROCESS_LIMIT = 64
# wall-clock 相对 CPU 限制的额外宽限（覆盖进程创建 / 动态链接等非 CPU 开销）
_WALL_GRACE_MS = 500
# 执行器自身兜底：isolate 进程超过该时间仍未退出即强杀并重置 box
_ISOLATE_GRACE_S = 15.0
_MEMORY_ERROR_MARKERS = (
    b"MemoryError",
    b"std::bad_alloc",
    b"OutOfMemoryError",
    b"Cannot allocate memory",
)
# isolate 默认已只读挂载 /bin /dev /dev/shm /lib /lib64 /proc /usr 与 rw 的 /tmp；
# 这里只补工具链与 locale 需要的目录（--dir 默认只读）。/proc 必须由 isolate 自己挂：
# 它在独立 PID namespace 内以 hidepid=2 提供，glibc 展开 RPATH 的 $ORIGIN、
# JVM launcher 定位 libjli 都依赖 /proc/self/exe，自行替换会破坏这两者。
_EXTRA_RUNTIME_DIRS = ("/sbin", "/etc")


class IsolateMeta:
    """isolate `--meta` 文件解析结果（缺失字段为 None）。"""

    __slots__ = (
        "status", "message", "exit_code", "exit_sig", "cpu_ms", "wall_ms",
        "max_rss_kb", "cg_mem_kb", "killed", "cg_oom_killed",
    )

    def __init__(self, raw: dict[str, str]) -> None:
        self.status = raw.get("status") or ""
        self.message = raw.get("message") or ""
        self.exit_code = _opt_int(raw.get("exitcode"))
        self.exit_sig = _opt_int(raw.get("exitsig"))
        self.cpu_ms = _ms_from_seconds(raw.get("time"))
        self.wall_ms = _ms_from_seconds(raw.get("time-wall"))
        self.max_rss_kb = _opt_int(raw.get("max-rss"))
        self.cg_mem_kb = _opt_int(raw.get("cg-mem"))
        self.killed = "killed" in raw
        self.cg_oom_killed = "cg-oom-killed" in raw

    def __repr__(self) -> str:  # pragma: no cover - 排障用
        return (
            f"IsolateMeta(status={self.status!r}, exit={self.exit_code}, sig={self.exit_sig}, "
            f"cpu={self.cpu_ms}, wall={self.wall_ms}, rss={self.max_rss_kb}, oom={self.cg_oom_killed})"
        )


def _opt_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _ms_from_seconds(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return max(0, int(round(float(value) * 1000)))
    except ValueError:
        return None


def parse_meta(text: str) -> IsolateMeta:
    """解析 meta 文件：每行 `key:value`；无冒号的非空行按「标记存在」记录。"""
    raw: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            if line.strip():
                raw[line.strip()] = ""
            continue
        raw[key.strip()] = value.strip()
    return IsolateMeta(raw)


def _format_seconds(ms: int) -> str:
    return f"{max(1, ms) / 1000:.3f}"


@dataclass
class _Box:
    """一个已 `--init` 的 box：宿主机目录 + 复用状态。"""

    box_id: int
    host_dir: Path

    @property
    def root(self) -> Path:
        """沙箱 `/box` 对应的宿主机目录。"""
        return self.host_dir / "box"


class BoxPool:
    """固定容量的预初始化 box 池。

    isolate 的 `--init --cg` 建 box + cgroup 是每次调用的固定开销；池化后
    仅在启动 / 异常恢复时执行，判题热路径只剩 `--run`。借出 / 归还都在
    调用线程内同步完成（调用方本身在 to_thread 里）。
    """

    def __init__(self, binary: str = "isolate", size: int = _DEFAULT_BOX_POOL, base_id: int = 0) -> None:
        self.binary = binary
        self.size = max(1, int(size))
        self.base_id = max(0, int(base_id))
        self._free: queue.Queue[_Box] = queue.Queue(maxsize=self.size)
        self._boxes: dict[int, _Box] = {}
        self._lock = threading.Lock()
        # start() 会连续执行 size 次 --init：并发 acquire 若各自触发建池，
        # 会把同一批 box-id 初始化两遍（第二次 --init 失败），必须整体串行
        self._start_lock = threading.Lock()
        self._started = False
        self._closed = False
        self._version = ""

    # ---- 生命周期 ----

    def start(self) -> None:
        """探测 isolate 并预热整个池；失败抛 JudgeWorkerError（节点不启动）。"""
        with self._start_lock:
            with self._lock:
                if self._closed:
                    raise JudgeWorkerError("sandbox box pool closed")
                if self._started:
                    return
            self._version = self._probe_version()
            boxes: list[_Box] = []
            errors: list[Exception] = []
            # box-id 相互独立，--init 可并行：10 个 box 串行约 1~2s，并行后显著缩短
            # 节点启动 / 重连等待；整个建池仍由 _start_lock 保证只执行一次
            with ThreadPoolExecutor(
                max_workers=min(self.size, 8), thread_name_prefix="isolate-init"
            ) as pool:
                futures = [
                    pool.submit(self._create, self.base_id + index)
                    for index in range(self.size)
                ]
                for future in futures:
                    try:
                        boxes.append(future.result())
                    except Exception as exc:  # noqa: BLE001 - 汇总后统一抛出
                        errors.append(exc)
            if errors:
                for box in boxes:
                    self._destroy(box)
                raise errors[0]
            with self._lock:
                for box in boxes:
                    self._boxes[box.box_id] = box
                    self._free.put(box)
                self._started = True

    def close(self) -> None:
        with self._lock:
            self._closed = True
            boxes = list(self._boxes.values())
            self._boxes.clear()
        for box in boxes:
            self._destroy(box)
        while True:
            try:
                self._free.get_nowait()
            except queue.Empty:
                break

    @property
    def version(self) -> str:
        return self._version

    def stats(self) -> dict:
        with self._lock:
            total = len(self._boxes)
        return {
            "backend": "isolate",
            "version": self._version,
            "pool_size": self.size,
            "pool_total": total,
            "pool_idle": self._free.qsize(),
        }

    # ---- 借还 ----

    def acquire(self, timeout: float = 60.0) -> _Box:
        if not self._started:
            self.start()
        with self._lock:
            if self._closed:
                raise JudgeWorkerError("sandbox box pool closed")
        try:
            return self._free.get(timeout=timeout)
        except queue.Empty as exc:
            raise JudgeWorkerError("no free sandbox box") from exc

    def release(self, box: _Box, *, healthy: bool = True) -> None:
        """归还未借出的 box；不健康则清理后按原 box-id 重建（池容量恒定）。"""
        with self._lock:
            if self._closed:
                return
            if not healthy:
                self._boxes.pop(box.box_id, None)
        if not healthy:
            self._destroy(box)
            try:
                fresh = self._create(box.box_id)
            except Exception:  # noqa: BLE001 - 重建失败只缩容，下一轮启动自愈
                return
            with self._lock:
                self._boxes[fresh.box_id] = fresh
            self._free.put(fresh)
            return
        self._free.put(box)

    # ---- 内部 ----

    def _create(self, box_id: int) -> _Box:
        result = subprocess.run(
            [self.binary, "--silent", "--box-id", str(box_id), "--cg", "--init"],
            capture_output=True,
            timeout=60,
            env=_isolate_env(),
        )
        if result.returncode != 0:
            raise JudgeWorkerError(
                "isolate box init failed: "
                + (result.stderr or result.stdout or b"").decode("utf-8", errors="replace")[:500]
            )
        # `--init` 在 stdout 打印 box 宿主机目录
        lines = [ln.strip() for ln in result.stdout.decode("utf-8", errors="replace").splitlines() if ln.strip()]
        if not lines:
            raise JudgeWorkerError("isolate box init returned no box path")
        host_dir = Path(lines[0])
        if not host_dir.is_dir():
            raise JudgeWorkerError(f"isolate box path missing: {host_dir}")
        # isolate 已建好 `<box>/box`；补一个可写产出目录
        (host_dir / "box").mkdir(exist_ok=True)
        return _Box(box_id=box_id, host_dir=host_dir)

    def _destroy(self, box: _Box) -> None:
        try:
            subprocess.run(
                [self.binary, "--silent", "--box-id", str(box.box_id), "--cg", "--cleanup"],
                capture_output=True,
                timeout=30,
                env=_isolate_env(),
            )
        except (OSError, subprocess.SubprocessError):
            pass

    def _probe_version(self) -> str:
        try:
            result = subprocess.run(
                [self.binary, "--version"], capture_output=True, timeout=15, env=_isolate_env()
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise JudgeWorkerError(f"isolate binary unavailable: {self.binary}") from exc
        text = (result.stdout or result.stderr or b"").decode("utf-8", errors="replace").strip()
        return text.replace("\n", " ")[:120] or "isolate"


def _isolate_env() -> dict[str, str]:
    return {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}


def _box_env() -> dict[str, str]:
    """沙箱内进程环境：最小集合，locale 固定 UTF-8（Python / Java 默认编码依赖它）。"""
    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": BOX_ROOT,
        # 编译器与运行时临时文件统一落在 box 内 rw tmpfs
        "TMPDIR": TMP_ROOT,
        # 禁写 pycache，避免向只读挂载的作业目录写入
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


class IsolateExecutor:
    """以池化 isolate box 执行一个编译或运行阶段。

    节点固定运行在 Linux 容器内（pigeonoj/judge-node 镜像），需要 cgroup v2
    与 privileged 容器；环境不满足时启动即失败，不做静默降级。
    """

    def __init__(
        self,
        isolate_binary: str = "isolate",
        pool_size: int = _DEFAULT_BOX_POOL,
        box_id_base: int = 0,
        acquire_timeout: float = 60.0,
    ) -> None:
        self.pool = BoxPool(isolate_binary, pool_size, box_id_base)
        # 等不到空闲 box 时尽快以 system_error 失败（网关侧还有 5min 判死兜底），
        # 避免节点线程长时间挂住、把提交拖到网关超时
        self.acquire_timeout = max(1.0, float(acquire_timeout))

    # ---- 生命周期 ----

    def start(self) -> None:
        self.pool.start()

    def close(self) -> None:
        self.pool.close()

    def stats(self) -> dict:
        return self.pool.stats()

    # ---- argv 组装（独立成方法便于单测） ----

    def build_args(
        self,
        command: Sequence[str],
        *,
        box_id: int,
        time_limit_ms: int,
        memory_limit_mb: int,
        as_limit_mb: int | None = None,
        fsize_kb: int | None = None,
        process_limit: int | None = None,
        mounts: Sequence[tuple[Path, str]] = (),
        stdin_box: str | None = None,
        meta_host: Path | None = None,
        runtime_dirs: Sequence[str] = _EXTRA_RUNTIME_DIRS,
    ) -> list[str]:
        """组装完整 argv（参数语义见 `isolate --help`）。

        - `--dir=<inside>[=<outside>][:选项]`：inside 在前；默认只读。
        - `--cg-mem`：整组 RSS 硬限（MLE 判据）。运行阶段只给 `--cg-mem`：同时给
          `--mem` 会让分配提前失败、程序自行退出，cgroup OOM 永不触发，MLE 无法归因。
          `--mem` 仅用于编译阶段（约束编译器而非判题语义）。
          （仅 C++ / Python 施加，JVM 虚拟预留远大于堆，施加会启动即失败）。
        - `--processes` 在 getopt 中是可选参数，必须用 `=` 形式绑定。
        - `--stdin/--stdout/--stderr` 在 chroot 后按沙箱路径打开；
          `--meta` 在进入 namespace 前由父进程按**宿主路径**打开。
        """
        if not command or any("\x00" in part for part in command):
            raise JudgeWorkerError("invalid execution command")
        args: list[str] = [
            self.pool.binary,
            "--silent",
            "--box-id", str(box_id),
            "--cg",
            # CPU 时间在 --cg 下按 cgroup 记账（毫秒精度）
            "--time", _format_seconds(time_limit_ms),
            # wall-clock 上限，留出进程创建 / 动态链接等非 CPU 开销；Python 侧另有兜底
            "--wall-time", _format_seconds(time_limit_ms + _WALL_GRACE_MS),
            "--cg-mem", str(max(1, memory_limit_mb) * 1024),
        ]
        if as_limit_mb:
            args += ["--mem", str(as_limit_mb * 1024)]
        if fsize_kb:
            args += ["--fsize", str(fsize_kb)]
        # --processes 必须始终指定：不给时 isolate 只允许单进程，任何 fork 都会
        # 以 EAGAIN 失败（编译器、JVM、Python 子进程都受影响）
        args += [f"--processes={process_limit or _COMPILE_PROCESS_LIMIT}"]
        args += ["--chdir", BOX_ROOT]
        args += ["--stdin", stdin_box or "/dev/null"]
        args += ["--stdout", f"{BOX_ROOT}/{_STDOUT_NAME}"]
        args += ["--stderr", f"{BOX_ROOT}/{_STDERR_NAME}"]
        if meta_host is not None:
            args += ["--meta", str(meta_host)]
        for key, value in _box_env().items():
            args += ["--env", f"{key}={value}"]
        for path in runtime_dirs:
            args += ["--dir", path]
        # --dir 默认只读：沙箱内唯一可写区是 box 根（/box）与 isolate 自挂的 /tmp
        for src, dest in mounts:
            args += ["--dir", f"{dest}={Path(src).resolve()}"]
        args += ["--run", "--"]
        args.extend(command)
        return args

    # ---- 执行 ----

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None,
        stdin: bytes,
        limits: ResourceLimits,
        output_limit: int,
        as_limit_mb: int | None = None,
        stdin_path: Path | None = None,
        extra_mounts: Sequence[tuple[Path, str]] = (),
        artifacts_out: Path | None = None,
        capture_stdout: Path | None = None,
        mode: str = "run",
    ) -> ExecutionResult:
        """在池化 box 中执行一次。

        - `stdin_path`：宿主测试点文件，只读挂载后直接作为沙箱 stdin（零拷贝）；
          缺省时把 `stdin` 字节写入 box 可写区。
        - `artifacts_out`：编译模式下落地产物目录（把 `/box/out/*` 拷回）。
        - `capture_stdout`：把程序 stdout 落一份到该宿主路径（SPJ 判定复用）。
        - `mode="compile"`：放宽 fsize、以编译预算判定，供工具链写中间文件。
        """
        box = self.pool.acquire(self.acquire_timeout)
        healthy = True
        result: ExecutionResult | None = None
        try:
            result = self._run_in_box(
                box,
                command,
                cwd=cwd,
                stdin=stdin,
                limits=limits,
                output_limit=output_limit,
                as_limit_mb=as_limit_mb,
                stdin_path=stdin_path,
                extra_mounts=extra_mounts,
                artifacts_out=artifacts_out,
                capture_stdout=capture_stdout,
                mode=mode,
            )
            return result
        except _BoxBroken:
            healthy = False
            raise
        finally:
            # cgroup OOM 之后 box 的 cgroup 计数与可写区状态不可信：实测复用该 box 做
            # 后续运行（如 SPJ）会得到 system_error。OOM 与超时同样归为不健康，重建。
            if result is not None and result.status == "memory_limit_exceeded":
                healthy = False
            self.pool.release(box, healthy=healthy)

    def _run_in_box(
        self,
        box: _Box,
        command: Sequence[str],
        *,
        cwd: Path | None,
        stdin: bytes,
        limits: ResourceLimits,
        output_limit: int,
        as_limit_mb: int | None,
        stdin_path: Path | None,
        extra_mounts: Sequence[tuple[Path, str]],
        artifacts_out: Path | None,
        capture_stdout: Path | None,
        mode: str,
    ) -> ExecutionResult:
        # 每次运行前清空 box 可写区：上一位用户留下的文件 / 临时文件不得可见
        _reset_box(box)
        meta_host = box.host_dir / _META_NAME
        meta_host.unlink(missing_ok=True)
        mount_list: list[tuple[Path, str]] = []
        if cwd is not None:
            mount_list.append((Path(cwd), _PROG))
        mount_list.extend(extra_mounts)
        stdin_box: str | None = None
        if stdin_path is not None:
            # 测试点零拷贝：只读挂载其所在目录，沙箱直接读宿主同一 inode
            readonly, args_in = _readonly_mounts([Path(stdin_path)])
            mount_list.extend(readonly)
            stdin_box = args_in[0]
        else:
            (box.root / _STDIN_NAME).write_bytes(stdin)
            stdin_box = f"{BOX_ROOT}/{_STDIN_NAME}"
        # fsize 比输出上限多 1KB：允许刚好写满上限的程序正常退出，超出由读取判定 OLE
        fsize_kb = _COMPILE_FSIZE_KB if mode == "compile" else max(1, limits.output_limit_kb) + 1
        process_limit = _COMPILE_PROCESS_LIMIT if mode == "compile" else limits.process_limit
        # isolate 不会替我们创建挂载点：目标目录必须先在 box 内存在
        for _src, dest in mount_list:
            _ensure_box_dir(box, dest)
        args = self.build_args(
            command,
            box_id=box.box_id,
            time_limit_ms=limits.time_limit_ms,
            memory_limit_mb=limits.memory_limit_mb,
            as_limit_mb=as_limit_mb,
            fsize_kb=fsize_kb,
            process_limit=process_limit,
            mounts=mount_list,
            stdin_box=stdin_box,
            meta_host=meta_host,
        )
        started = time.monotonic()
        try:
            proc = subprocess.run(
                args,
                # isolate 以 --silent 运行，自身只可能往 stderr 写诊断；
                # stdout 不建管道，省一次 pipe 与读取线程（结果只看 box 内文件）
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=limits.time_limit_ms / 1000 + _ISOLATE_GRACE_S,
                env=_isolate_env(),
            )
        except subprocess.TimeoutExpired as exc:
            # isolate 自己没退出：box 状态不可信，交给池回收重建
            raise _BoxBroken("isolate run timed out") from exc
        except OSError as exc:
            raise JudgeWorkerError("isolate execution failed") from exc
        elapsed_ms = max(0, int((time.monotonic() - started) * 1000))

        meta = _read_meta(box)
        stdout = _read_limited_file(box.root / _STDOUT_NAME, output_limit + 1)
        stderr = _read_limited_file(box.root / _STDERR_NAME, output_limit + 1)
        if meta is None:
            # isolate 在程序结束时必写 meta；缺失说明沙箱自身异常（被强杀 / box 损坏）
            raise _BoxBroken(
                "isolate meta missing: "
                + (proc.stderr or b"").decode("utf-8", errors="replace")[:500]
            )
        if artifacts_out is not None:
            _collect_artifacts(box, Path(artifacts_out))
        result = _classify(
            meta, limits, output_limit, stdout, stderr, elapsed_ms,
            compile=mode == "compile", verdict_exit=mode == "spj",
        )
        if capture_stdout is not None and (box.root / _STDOUT_NAME).is_file():
            # 供 SPJ 判定复用：把用户输出搬进作业目录（下一次运行会重置 box 可写区）
            target = Path(capture_stdout)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(box.root / _STDOUT_NAME, target)
        return result


class _BoxBroken(Exception):
    """box 状态不可信（isolate 超时 / meta 缺失），归还时清理重建。"""


def _reset_box(box: _Box) -> None:
    """清空 box 可写区并重建编译产物目录。"""
    root = box.root
    if not root.is_dir():
        raise JudgeWorkerError("sandbox box missing")
    with os.scandir(root) as entries:
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    shutil.rmtree(entry.path, ignore_errors=True)
                else:
                    os.unlink(entry.path)
            except OSError:
                pass
    (root / _OUT_NAME).mkdir(exist_ok=True)


def _ensure_box_dir(box: _Box, box_path: str) -> None:
    """在 box 目录内创建挂载点（isolate 要求目标已存在，且不替我们创建）。"""
    rel = box_path.lstrip("/")
    if not rel.startswith("box/"):
        return
    try:
        (box.host_dir / rel).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise JudgeWorkerError(f"cannot create mount point {box_path}") from exc


def _read_meta(box: _Box) -> IsolateMeta | None:
    path = box.host_dir / _META_NAME
    if not path.is_file():
        return None
    try:
        return parse_meta(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def _read_limited_file(path: Path, limit: int) -> bytes:
    """读取至多 limit 字节（fsize 已在内核侧封顶，这里只防异常膨胀）。"""
    try:
        with open(path, "rb") as fh:
            return fh.read(limit)
    except OSError:
        return b""


def _collect_artifacts(box: _Box, dest: Path) -> None:
    out_dir = box.root / _OUT_NAME
    if not out_dir.is_dir():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for item in out_dir.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
            # 编译产物需要沙箱内编译用户可执行
            try:
                os.chmod(target, 0o755)
            except OSError:
                pass


def _classify(
    meta: IsolateMeta,
    limits: ResourceLimits,
    output_limit: int,
    stdout: bytes,
    stderr: bytes,
    elapsed_ms: int,
    *,
    compile: bool = False,
    verdict_exit: bool = False,
) -> ExecutionResult:
    """meta → 判题状态（docs/contracts.md §10「判题器执行规范」）。

    status: RE=非零退出 / SG=被信号杀 / TO=超时 / XX=isolate 自身故障 / 空=正常退出。
    时间取 `time`（`--cg` 下为 cgroup CPU 记账），内存取 `max-rss` / `cg-mem` 峰值。

    `verdict_exit=True` 用于 SPJ 特判程序：其退出码本身是判定结果（0=AC、1=WA、
    3/4=checker 故障），不能按普通程序的非零退出归为 runtime_error，
    只有超时 / 崩溃 / 输出超限 / isolate 故障才交给 `_spj_verdict` 判 system_error。
    """
    cpu_ms = meta.cpu_ms if meta.cpu_ms is not None else elapsed_ms
    wall_ms = meta.wall_ms if meta.wall_ms is not None else elapsed_ms
    mem_kb = meta.max_rss_kb if meta.max_rss_kb is not None else meta.cg_mem_kb
    mem_limit_kb = limits.memory_limit_mb * 1024

    if meta.status == "XX":
        status = "system_error"
    elif meta.status == "TO" or cpu_ms > limits.time_limit_ms or wall_ms > limits.time_limit_ms + _WALL_GRACE_MS:
        status = "time_limit_exceeded"
    elif meta.cg_oom_killed or (mem_kb is not None and mem_kb > mem_limit_kb):
        status = "memory_limit_exceeded"
    elif meta.exit_sig == _SIGXFSZ or len(stdout) > output_limit or len(stderr) > output_limit:
        status = "output_limit_exceeded"
    elif verdict_exit and meta.status in ("RE", "SG"):
        # checker 以非零码结束是正常判定路径；退出码交由 _spj_verdict 解释
        status = "ok"
    elif meta.status in ("RE", "SG") or (meta.exit_code or 0) != 0:
        # 地址空间 / cgroup 封顶后，超内存分配的典型失败特征 → MLE
        status = (
            "memory_limit_exceeded"
            if not compile and any(marker in stderr for marker in _MEMORY_ERROR_MARKERS)
            else "runtime_error"
        )
    else:
        status = "ok"

    exit_code = meta.exit_code
    if exit_code is None and meta.exit_sig:
        exit_code = -meta.exit_sig
    # 展示口径：正常结束用 CPU 时间（与主流 OJ 一致，不含沙箱启动开销）；
    # 因 wall 超限判 TLE 时改报 wall，否则 sleep 类程序会显示接近 0ms 的假象
    shown_ms = wall_ms if status == "time_limit_exceeded" and wall_ms > cpu_ms else cpu_ms
    return ExecutionResult(
        status,
        _cap(stdout, output_limit),
        _cap(stderr, output_limit),
        shown_ms,
        mem_kb,
        exit_code,
        compile=compile,
    )


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
            language, _PROG, memory_limit_mb=compile_limits.memory_limit_mb
        )
        (self.workdir / source_name).write_bytes(source)
        self.compile_result: ExecutionResult | None = None
        self._closed = False
        _make_readable(self.workdir)
        if self.compile_command:
            self.compile_result = worker.executor.run(
                self.compile_command,
                cwd=self.workdir,
                stdin=b"",
                limits=compile_limits,
                output_limit=compile_limits.output_limit_kb * 1024,
                # JVM 虚拟地址预留远大于堆，编译期不施加 AS 封顶（java 无编译阶段，此参数对 python/cpp 生效）
                as_limit_mb=None if language == "java21" else compile_limits.memory_limit_mb,
                artifacts_out=self.workdir,
                mode="compile",
            )
            # 产物从 box 拷回后需重设权限：沙箱内以低权限身份 execve，
            # 且作业目录本身是只读挂载（文件必须自带可执行位）
            _make_readable(self.workdir)

    @property
    def compile_failed(self) -> bool:
        return self.compile_result is not None and self.compile_result.status != "ok"

    def prepare_spj(
        self, source: bytes, compile_limits: ResourceLimits, *, cache_path: Path | None = None
    ) -> SpjProgram:
        """编译题目特判程序（同一题目版本只编译一次，与提交代码共用编译预算口径）。

        命中 cache_path 时直接复用已编译二进制，不再启动 g++；失败抛
        SpjCompileError（不带编译器输出，防特判源码片段泄露给提交者）。
        """
        if self._closed:
            raise JudgeWorkerError("submission workspace is closed")
        if self.compile_failed:
            raise JudgeWorkerError("submission compile failed")
        binary = self.workdir / _SPJ_BINARY_NAME
        if cache_path is not None and cache_path.is_file():
            try:
                shutil.copy2(cache_path, binary)
                os.chmod(binary, 0o755)
                _make_readable_paths(self.workdir, binary)
                return SpjProgram(binary=f"{_PROG}/{_SPJ_BINARY_NAME}")
            except OSError:
                pass  # 缓存不可读：回退重新编译
        (self.workdir / _SPJ_SOURCE_NAME).write_bytes(source)
        _make_readable(self.workdir)
        # 与 cpp17 提交编译同款工具链参数（绝对路径，见 _commands 注释）
        command = [
            "/usr/bin/g++", "-B/usr/bin/", "-std=c++17", "-O2", "-pipe",
            "-o", f"{OUT_DIR}/{_SPJ_BINARY_NAME}", f"{_PROG}/{_SPJ_SOURCE_NAME}",
        ]
        result = self.worker.executor.run(
            command,
            cwd=self.workdir,
            stdin=b"",
            limits=compile_limits,
            output_limit=compile_limits.output_limit_kb * 1024,
            as_limit_mb=compile_limits.memory_limit_mb,
            artifacts_out=self.workdir,
            mode="compile",
        )
        if result.status != "ok":
            raise SpjCompileError("special judge program compile failed")
        _make_readable_paths(self.workdir, binary)  # 特判二进制同样需要可执行位
        if cache_path is not None and binary.is_file():
            _store_spj_cache(binary, cache_path)
        return SpjProgram(binary=f"{_PROG}/{_SPJ_BINARY_NAME}")

    def run_case(
        self,
        stdin: bytes,
        expected_stdout: bytes | None,
        limits: ResourceLimits,
        *,
        spj: SpjProgram | None = None,
        spj_limits: ResourceLimits | None = None,
        stdin_path: Path | None = None,
        expected_path: Path | None = None,
        file_tag: str = "",
    ) -> ExecutionResult:
        if self._closed:
            raise JudgeWorkerError("submission workspace is closed")
        if self.compile_failed:
            assert self.compile_result is not None
            # 编译阶段非 system_error 的失败（超时 / 内存 / 输出超限 / 非零退出）
            # 都属于用户代码问题，统一报 compile_error，不让用户看到 TLE/MLE
            status = "system_error" if self.compile_result.status == "system_error" else "compile_error"
            return ExecutionResult(
                status,
                b"",
                self.compile_result.stderr,
                self.compile_result.time_used_ms,
                self.compile_result.memory_used_kb,
                self.compile_result.exit_code,
                compile=True,
            )
        _, run_command, _ = _commands(self.language, _PROG, memory_limit_mb=limits.memory_limit_mb)
        # 用户输出需要跨运行保留（SPJ 要读它）：先落作业目录，再随本次执行挂回沙箱
        user_out = self.workdir / f"user_out.{file_tag or 0}"
        user_out.unlink(missing_ok=True)
        result = self.worker.executor.run(
            run_command,
            cwd=self.workdir,
            stdin=stdin,
            limits=limits,
            output_limit=limits.output_limit_kb * 1024,
            # 运行阶段只施加 --cg-mem：同时给 --mem（地址空间）会让 malloc 在到限前
            # 返回 NULL，程序可能自行退出成 WA/RE，永远走不到 cgroup OOM，MLE 判不出来。
            # 实测：--mem+--cg-mem 同值时程序打印 "malloc-null at 56MB" 正常退出；
            # 仅 --cg-mem 时 meta 为 cg-oom-killed:1 / exitsig:9，可正确判 MLE。
            as_limit_mb=None,
            stdin_path=stdin_path,
            capture_stdout=user_out if spj is not None else None,
        )
        if result.status != "ok":
            return result
        if spj is not None:
            return self._judge_with_spj(
                result,
                stdin,
                expected_stdout,
                spj,
                spj_limits or limits,
                user_out=user_out,
                stdin_path=stdin_path,
                expected_path=expected_path,
                file_tag=file_tag,
            )
        if expected_stdout is not None:
            same = _same_output(result.stdout, expected_stdout)
        elif expected_path is not None:
            same = _same_output_file(result.stdout, expected_path)
        else:
            return result
        return ExecutionResult(
            "accepted" if same else "wrong_answer",
            result.stdout, result.stderr, result.time_used_ms, result.memory_used_kb, result.exit_code,
        )

    def _judge_with_spj(
        self,
        user_result: ExecutionResult,
        stdin: bytes,
        expected_stdout: bytes | None,
        spj: SpjProgram,
        spj_limits: ResourceLimits,
        *,
        user_out: Path,
        stdin_path: Path | None,
        expected_path: Path | None,
        file_tag: str = "",
    ) -> ExecutionResult:
        """SPJ 判定：三文件 argv（input / user_out / answer）运行特判程序，退出码定论。

        input / answer 直接只读挂载题目数据目录（零拷贝）；user_out 是上一次用户
        运行落地到作业目录的输出文件。特判程序自身故障（超时 / 崩溃 / 输出超限 /
        testlib _died / _fail）→ 整个提交 system_error，stderr 不回传（防源码泄露）。
        返回结果的 time / memory / stdout 保持用户程序口径（逐点落库依据）。
        """
        files: list[Path] = []
        if stdin_path is not None:
            files.append(Path(stdin_path))
        else:
            name = f"spj_in.{file_tag or 0}"
            (self.workdir / name).write_bytes(stdin)
            files.append(self.workdir / name)
        files.append(Path(user_out))
        if expected_path is not None:
            files.append(Path(expected_path))
        else:
            name = f"spj_ans.{file_tag or 0}"
            (self.workdir / name).write_bytes(expected_stdout or b"")
            files.append(self.workdir / name)
        _make_readable_paths(self.workdir, *files)
        # 作业目录内文件复用 /prog 挂载点；目录外文件（题目数据）补进 /data
        extra, box_paths = _readonly_mounts(
            files, already_mounted=self.workdir, mounted_at=_PROG
        )
        command = [spj.binary, *box_paths]
        result = self.worker.executor.run(
            command,
            cwd=self.workdir,
            stdin=b"",
            limits=spj_limits,
            output_limit=max(_SPJ_MESSAGE_LIMIT * 8, spj_limits.output_limit_kb * 1024),
            as_limit_mb=spj_limits.memory_limit_mb,
            extra_mounts=extra,
            # checker 退出码即判定结果（0=AC / 1=WA / 3,4=故障），不走普通程序状态映射
            mode="spj",
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

    def __init__(self, executor: IsolateExecutor | None = None, workspace_root: str | None = None) -> None:
        self.executor = executor or IsolateExecutor()
        self.workspace_root = workspace_root

    def start(self) -> None:
        start = getattr(self.executor, "start", None)
        if callable(start):
            start()

    def close(self) -> None:
        close = getattr(self.executor, "close", None)
        if callable(close):
            close()

    def stats(self) -> dict:
        stats = getattr(self.executor, "stats", None)
        return stats() if callable(stats) else {}

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
        spj_cache_path: Path | None = None,
        cancel_event: threading.Event | None = None,
        max_parallel: int = _DEFAULT_CASE_PARALLEL,
    ) -> list[ExecutionResult]:
        """编译一次后运行测试点。

        stop_on_failure（ACM 赛制短路）：串行，首个非 accepted 后停止。
        IOI / 练习 / 验题：同作业有限并行（默认 4）；compile_error / system_error
        结束后续批次。cancel_event 在批次边界生效（docs/contracts.md §10）。
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
                spj = submission.prepare_spj(
                    spj_source, compile_limits, cache_path=spj_cache_path
                )
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


def _run_one_case(
    submission: PreparedSubmission,
    index: int,
    case: JudgeCase,
    *,
    spj: SpjProgram | None,
    spj_limits: ResourceLimits | None,
) -> ExecutionResult:
    _validate_case(case)
    # 有文件路径时执行器直接只读挂载（零拷贝），不要先把整份 .in/.out 读进内存；
    # SPJ 模式下 answer 同样走挂载，内容无需读入
    stdin = b"" if case.stdin_path is not None else case.load_stdin()
    # 期望输出有文件时交给 run_case 分块比对（不整份读入内存）；
    # SPJ 模式下该路径同样只用于只读挂载
    expected = None if case.expected_path is not None else case.load_expected()
    return submission.run_case(
        stdin, expected, case.limits,
        spj=spj, spj_limits=spj_limits,
        stdin_path=case.stdin_path,
        expected_path=case.expected_path,
        file_tag=str(index),
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
    """同作业多测试点持续并发：固定 max_workers 个在途，完成一个补一个。

    旧实现按 max_workers 分批（整批 as_completed 后才进下一批），任一长尾
    测试点都会拖住整批；持续补位让总耗时接近「总工作量 / 并发度」。
    compile_error / system_error 后停止补位，仅让在途点跑完并记录结果；
    cancel_event 在当前在途点结束后生效（契约：批次边界取消）。
    """
    if cancel_event is not None and cancel_event.is_set():
        return []
    ordered: list[ExecutionResult | None] = [None] * len(cases)
    stop_more = False
    next_index = 0

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        inflight: dict[Future, int] = {}

        def submit_next() -> None:
            nonlocal next_index
            if next_index >= len(cases):
                return
            index = next_index
            next_index += 1
            inflight[pool.submit(
                _run_one_case, submission, index, cases[index], spj=spj, spj_limits=spj_limits
            )] = index

        for _ in range(min(max_workers, len(cases))):
            submit_next()

        while inflight:
            done, _ = wait(inflight, return_when=FIRST_COMPLETED)
            for fut in done:
                index = inflight.pop(fut)
                ordered[index] = fut.result()
                if ordered[index] is not None and ordered[index].status in _FATAL_CASE_STATUSES:
                    stop_more = True
            if cancel_event is not None and cancel_event.is_set():
                break
            if not stop_more:
                for _ in range(len(done)):
                    submit_next()
    return [item for item in ordered if item is not None]


# JVM 非堆开销（元空间 / 代码缓存 / 线程栈 / GC 结构）实测约 30~45MB。
# -Xmx 直接取题目内存上限会让「堆峰值 + 非堆」越过 --cg-mem，把正常程序误判成 MLE。
# 该开销不随内存上限缩小，因此固定预留，只给堆保留 16MB 下限。
_JAVA_NONHEAP_RESERVE_MB = 48


def _java_xmx_mb(memory_limit_mb: int) -> int:
    """给 JVM 堆留出非堆余量，避免堆打满时整组 RSS 超 --cg-mem。"""
    limit = max(1, memory_limit_mb)
    return max(16, limit - _JAVA_NONHEAP_RESERVE_MB)


def _commands(
    language: Language, prog_dir: str, *, memory_limit_mb: int = 256
) -> tuple[str, list[str], list[str] | None]:
    """编译 / 运行命令。工具链使用绝对路径（沙箱镜像 ubuntu:24.04 布局）：

    - gcc 驱动从 argv[0] 推导安装前缀，裸名调用在沙箱内推导失败，
      cc1plus / ld 会退化为 PATH 搜索并报 execvp ENOENT；
      `-B/usr/bin/` 让 collect2 直接命中链接器。
    - OpenJDK launcher 沿符号链定位 JAVA_HOME，/usr/bin/javac 解析失败报
      libjli.so 缺失；直接调用 alternatives 的真实路径。
    编译产物落在沙箱可写区 /box/out，运行期从只读作业目录 /box/prog 取产物。
    语言级命令后续由 sandbox_configs 配置化（docs/contracts.md §10）。
    Java `-Xmx` 按有效内存换算（契约：运行时参数，判据仍为 RSS），
    JVM 临时目录指向 box 内 rw tmpfs。
    """
    if language == "python3.12":
        return "Main.py", ["/usr/bin/python3.12", f"{prog_dir}/Main.py"], None
    if language == "cpp17":
        return "Main.cpp", [f"{prog_dir}/Main"], [
            "/usr/bin/g++", "-B/usr/bin/", f"-I{_CXX_PCH}", "-std=c++17", "-O2", "-pipe",
            "-o", f"{OUT_DIR}/Main", f"{prog_dir}/Main.cpp",
        ]
    if language == "java21":
        return "Main.java", [
            "/usr/lib/jvm/java-21-openjdk-amd64/bin/java",
            f"-XX:ErrorFile={TMP_ROOT}/hs_err_pid%p.log",
            f"-Djava.io.tmpdir={TMP_ROOT}",
            f"-Xmx{_java_xmx_mb(memory_limit_mb)}m", "-cp", prog_dir, "Main",
        ], [
            "/usr/lib/jvm/java-21-openjdk-amd64/bin/javac",
            f"-J-XX:ErrorFile={TMP_ROOT}/hs_err.log",
            f"-J-Djava.io.tmpdir={TMP_ROOT}",
            "-d", OUT_DIR, f"{prog_dir}/Main.java",
        ]
    raise JudgeWorkerError("unsupported language")


def _readonly_mounts(
    files: Sequence[Path], *, already_mounted: Path | None = None, mounted_at: str | None = None
) -> tuple[list[tuple[Path, str]], list[str]]:
    """把一批宿主文件按只读方式映射进沙箱，返回 (挂载列表, 沙箱内路径)。

    `already_mounted` 目录（作业目录）内的文件直接复用其沙箱挂载点
    （`mounted_at`），不重复 bind；其余文件按父目录分组挂到 `/box/data/<n>`，
    同目录只挂一次（测试点 input / answer 通常同目录）。
    """
    mounts: list[tuple[Path, str]] = []
    by_parent: dict[Path, str] = {}
    paths: list[str] = []
    index = 0
    parent_root = Path(already_mounted).resolve() if already_mounted is not None else None
    base_root = mounted_at or _PROG
    for item in files:
        path = Path(item).resolve()
        if parent_root is not None and path.parent == parent_root:
            paths.append(f"{base_root}/{path.name}")
            continue
        parent = path.parent
        if parent in by_parent:
            base = by_parent[parent]
        else:
            base = _DATA if index == 0 else f"{_DATA}/{index}"
            by_parent[parent] = base
            mounts.append((parent, base))
            index += 1
        paths.append(f"{base}/{path.name}")
    return mounts, paths


def _chmod_readable(item: Path) -> None:
    """放开单个路径给沙箱内低权限身份读取；可执行文件保持可执行位。"""
    if sys.platform != "linux" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        return
    if not item.exists():
        return
    try:
        if item.is_dir():
            os.chmod(item, 0o755)
            return
        executable = bool(os.stat(item).st_mode & 0o111)
        os.chmod(item, 0o755 if executable else 0o644)
    except OSError:
        pass


def _make_readable(workdir: Path, *files: Path) -> None:
    """作业目录全量放开权限（准备阶段调用一次，文件数少）。"""
    if sys.platform != "linux" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        return
    try:
        os.chmod(workdir, 0o755)
    except OSError:
        pass
    if workdir.is_dir():
        for item in workdir.iterdir():
            _chmod_readable(item)
    for item in files:
        _chmod_readable(item)


def _make_readable_paths(workdir: Path, *files: Path) -> None:
    """只放开目录与本次新增文件：SPJ 每测试点调用，避免反复扫描整个作业目录。"""
    if sys.platform != "linux" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        return
    try:
        os.chmod(workdir, 0o755)
    except OSError:
        pass
    for item in files:
        _chmod_readable(item)


def _store_spj_cache(source: Path, cache_path: Path) -> None:
    """原子写入 SPJ 二进制缓存：并发提交编译同一题时不会读到半份文件。"""
    tmp = cache_path.with_name(f"{cache_path.name}.tmp-{os.getpid()}-{threading.get_ident()}")
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, tmp)
        os.chmod(tmp, 0o755)
        os.replace(tmp, cache_path)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
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


def _normalized_lines(value: bytes) -> Iterator[bytes]:
    """按行流式归一化（忽略行尾空白与末尾换行），不生成整份行列表。"""
    stream = io.BytesIO(value)
    while True:
        line = stream.readline()
        if not line:
            return
        yield line.rstrip()


def _same_output(actual: bytes, expected: bytes) -> bool:
    return all(
        a == b
        for a, b in zip_longest(
            _normalized_lines(actual), _normalized_lines(expected), fillvalue=None
        )
    )


_COMPARE_CHUNK_BYTES = 1 << 20


def _same_output_lines_file(actual: bytes, expected_path: Path) -> bool:
    """末尾空白 / 换行差异的兜底：逐行比较，不把整份期望输出读入内存。"""
    try:
        with Path(expected_path).open("rb") as fh:
            stream = io.BytesIO(actual)
            while True:
                a = stream.readline()
                b = fh.readline()
                if not a and not b:
                    return True
                if not a or not b:
                    return False
                if a.rstrip() != b.rstrip():
                    return False
    except OSError:
        return False


def _same_output_file(actual: bytes, expected_path: Path) -> bool:
    """与期望输出文件比较：先按 1MB 分块做字节级快速比较（AC 常见路径），
    只有长度 / 末尾空白不一致时才逐行兜底，内存占用恒定为块大小。"""
    try:
        with Path(expected_path).open("rb") as fh:
            offset = 0
            while True:
                chunk = fh.read(_COMPARE_CHUNK_BYTES)
                if not chunk:
                    break
                if actual[offset:offset + len(chunk)] != chunk:
                    return _same_output_lines_file(actual, expected_path)
                offset += len(chunk)
        return offset == len(actual) or _same_output_lines_file(actual, expected_path)
    except OSError:
        return False


def _spj_verdict(spj_result: ExecutionResult, user_result: ExecutionResult) -> ExecutionResult:
    """SPJ 退出码 → 判定（docs/contracts.md §10.6）：

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
        user_result.time_used_ms, user_result.memory_used_kb, spj_result.exit_code,
        message=_cap(spj_result.stdout, _SPJ_MESSAGE_LIMIT),
    )


def _cap(value: bytes, limit: int) -> bytes:
    return value[:limit]


__all__ = [
    "BOX_ROOT",
    "BoxPool",
    "ExecutionResult",
    "IsolateExecutor",
    "IsolateMeta",
    "JudgeCase",
    "JudgeWorker",
    "JudgeWorkerError",
    "OUT_DIR",
    "PreparedSubmission",
    "ResourceLimits",
    "SPJ_SOURCE_NAME",
    "SpjCompileError",
    "SpjProgram",
    "TMP_ROOT",
    "parse_meta",
]

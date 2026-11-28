"""判题节点配置（node.toml + 环境变量覆盖，标准库 tomllib）。

节点固定运行在 Docker 容器内（pigeonoj/judge-node 镜像）：
- 工作区固定为容器内 /workspace（宿主机目录由 docker run -v <host>:/workspace 指定）
- 题目数据缓存固定为容器内 /cache
"""
from __future__ import annotations

import os
import socket
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

NODE_VERSION = "isolate-node-2.0"  # 注册与管理页展示，随沙箱后端变更跳动


@dataclass
class ServerConfig:
    address: str = "127.0.0.1:50051"
    token: str = ""
    tls: bool = False           # true 时走 TLS（如经 nginx 按路径反代复用 443 域名）


@dataclass
class NodeConfig:
    id: str = ""                # 留空自动 {hostname}-{pid}
    name: str = ""
    capacity: int = 2


@dataclass
class PathsConfig:
    workspace: str = "/workspace"   # 容器内路径；宿主机目录由挂载决定
    data_cache: str = "/cache"


@dataclass
class SandboxConfig:
    isolate_binary: str = "isolate"     # isolate 可执行文件（镜像内已在 PATH）
    box_pool_size: int = 10             # 预初始化 box 数；建议 ≥ capacity×(case_parallel+1)
    box_id_base: int = 0                # 池占用 box-id 区间起点，同机多节点进程需错开
    case_parallel: int = 4              # IOI/练习同作业并行测试点数；ACM 短路仍串行
    box_acquire_timeout_seconds: float = 60.0  # 等不到空闲 box 的失败时限（秒）


@dataclass
class AdminConfig:
    bind: str = "127.0.0.1"         # 管理页监听地址；空字符串 = 不启动
    port: int = 18080               # 0 = 不启动


@dataclass
class CacheConfig:
    max_mb: int = 512               # /cache 总大小上限；0 表示不限制（不回收）
    gc_interval_seconds: int = 300  # 回收巡检间隔


@dataclass
class JudgeNodeConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    node: NodeConfig = field(default_factory=NodeConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    admin: AdminConfig = field(default_factory=AdminConfig)


def load_config(path: str | Path) -> JudgeNodeConfig:
    raw: dict = {}
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    cfg = JudgeNodeConfig(
        server=ServerConfig(**raw.get("server", {})),
        node=NodeConfig(**raw.get("node", {})),
        paths=PathsConfig(**raw.get("paths", {})),
        sandbox=SandboxConfig(**raw.get("sandbox", {})),
        cache=CacheConfig(**raw.get("cache", {})),
        admin=AdminConfig(**raw.get("admin", {})),
    )

    # 环境变量覆盖（compose/K8s 注入场景）
    cfg.server.address = os.environ.get("SERVER_ADDRESS", cfg.server.address)
    cfg.server.token = os.environ.get("SERVER_TOKEN", cfg.server.token)
    if tls := os.environ.get("SERVER_TLS"):
        cfg.server.tls = tls.strip().lower() in ("1", "true", "yes", "on")
    cfg.node.id = os.environ.get("JUDGE_NODE_ID", cfg.node.id)
    cfg.node.name = os.environ.get("JUDGE_NODE_NAME", cfg.node.name)
    if cap := os.environ.get("JUDGE_NODE_CAPACITY"):
        cfg.node.capacity = int(cap)
    if max_mb := os.environ.get("JUDGE_CACHE_MAX_MB"):
        cfg.cache.max_mb = int(max_mb)
    if gc_interval := os.environ.get("JUDGE_CACHE_GC_INTERVAL_SECONDS"):
        cfg.cache.gc_interval_seconds = int(gc_interval)
    if parallel := os.environ.get("JUDGE_CASE_PARALLEL"):
        cfg.sandbox.case_parallel = max(1, int(parallel))
    if isolate_binary := os.environ.get("JUDGE_ISOLATE_BINARY"):
        cfg.sandbox.isolate_binary = isolate_binary
    if pool := os.environ.get("JUDGE_ISOLATE_BOX_POOL"):
        cfg.sandbox.box_pool_size = max(1, int(pool))
    if base := os.environ.get("JUDGE_ISOLATE_BOX_ID_BASE"):
        cfg.sandbox.box_id_base = max(0, int(base))
    if acquire := os.environ.get("JUDGE_ISOLATE_ACQUIRE_TIMEOUT"):
        cfg.sandbox.box_acquire_timeout_seconds = max(1.0, float(acquire))
    if admin_bind := os.environ.get("JUDGE_ADMIN_BIND"):
        cfg.admin.bind = admin_bind
    if admin_port := os.environ.get("JUDGE_ADMIN_PORT"):
        cfg.admin.port = int(admin_port)

    if not cfg.node.id:
        cfg.node.id = f"{socket.gethostname()}-{os.getpid()}"
    apply_runtime_overlay(cfg)
    return cfg


def _toml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def save_config(path: str | Path, cfg: JudgeNodeConfig) -> None:
    """把可调配置写回 TOML（管理页保存用）。路径类字段保持原值。"""
    text = (
        "# PigeonOJ 判题节点配置（可由节点管理页写回）\n"
        "# 管理页另写 /cache/node.runtime.toml，加载时覆盖环境变量中的可调项\n"
        "\n"
        "[server]\n"
        f"address = {_toml_str(cfg.server.address)}\n"
        f"token = {_toml_str(cfg.server.token)}\n"
        f"tls = {str(cfg.server.tls).lower()}\n"
        "\n"
        "[node]\n"
        f"id = {_toml_str(cfg.node.id)}\n"
        f"name = {_toml_str(cfg.node.name)}\n"
        f"capacity = {max(1, int(cfg.node.capacity))}\n"
        "\n"
        "[paths]\n"
        f"workspace = {_toml_str(cfg.paths.workspace)}\n"
        f"data_cache = {_toml_str(cfg.paths.data_cache)}\n"
        "\n"
        "[cache]\n"
        f"max_mb = {int(cfg.cache.max_mb)}\n"
        f"gc_interval_seconds = {int(cfg.cache.gc_interval_seconds)}\n"
        "\n"
        "[sandbox]\n"
        f"isolate_binary = {_toml_str(cfg.sandbox.isolate_binary)}\n"
        f"box_pool_size = {max(1, int(cfg.sandbox.box_pool_size))}\n"
        f"box_id_base = {max(0, int(cfg.sandbox.box_id_base))}\n"
        f"case_parallel = {max(1, int(cfg.sandbox.case_parallel))}\n"
        f"box_acquire_timeout_seconds = {max(1.0, float(cfg.sandbox.box_acquire_timeout_seconds)):.1f}\n"
        "\n"
        "[admin]\n"
        f"bind = {_toml_str(cfg.admin.bind)}\n"
        f"port = {int(cfg.admin.port)}\n"
    )
    Path(path).write_text(text, encoding="utf-8")
    save_runtime_overlay(cfg)


_RUNTIME_OVERLAY_NAME = "node.runtime.toml"


def runtime_overlay_path(cfg: JudgeNodeConfig) -> Path:
    return Path(cfg.paths.data_cache) / _RUNTIME_OVERLAY_NAME


def apply_runtime_overlay(cfg: JudgeNodeConfig) -> None:
    """管理页写入的运行时覆盖，优先于 compose 环境变量；文件在 /cache 卷上跨重建保留。"""
    path = runtime_overlay_path(cfg)
    if not path.is_file():
        return
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return
    server = raw.get("server") or {}
    node = raw.get("node") or {}
    sandbox = raw.get("sandbox") or {}
    cache = raw.get("cache") or {}
    if address := server.get("address"):
        cfg.server.address = str(address)
    if "token" in server and server["token"] is not None:
        cfg.server.token = str(server["token"])
    if "tls" in server:
        cfg.server.tls = bool(server["tls"])
    if "name" in node and node["name"] is not None:
        cfg.node.name = str(node["name"])
    if "capacity" in node:
        try:
            cfg.node.capacity = max(1, int(node["capacity"]))
        except (TypeError, ValueError):
            pass
    if "case_parallel" in sandbox:
        try:
            cfg.sandbox.case_parallel = max(1, int(sandbox["case_parallel"]))
        except (TypeError, ValueError):
            pass
    if "box_pool_size" in sandbox:
        try:
            cfg.sandbox.box_pool_size = max(1, int(sandbox["box_pool_size"]))
        except (TypeError, ValueError):
            pass
    if "box_id_base" in sandbox:
        try:
            cfg.sandbox.box_id_base = max(0, int(sandbox["box_id_base"]))
        except (TypeError, ValueError):
            pass
    if "box_acquire_timeout_seconds" in sandbox:
        try:
            cfg.sandbox.box_acquire_timeout_seconds = max(1.0, float(sandbox["box_acquire_timeout_seconds"]))
        except (TypeError, ValueError):
            pass
    if "isolate_binary" in sandbox and sandbox["isolate_binary"]:
        cfg.sandbox.isolate_binary = str(sandbox["isolate_binary"])
    if "max_mb" in cache:
        try:
            cfg.cache.max_mb = max(0, int(cache["max_mb"]))
        except (TypeError, ValueError):
            pass


def save_runtime_overlay(cfg: JudgeNodeConfig) -> None:
    path = runtime_overlay_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# 管理页运行时覆盖（优先于环境变量，随 /cache 卷保留）\n"
        "[server]\n"
        f"address = {_toml_str(cfg.server.address)}\n"
        f"token = {_toml_str(cfg.server.token)}\n"
        f"tls = {str(cfg.server.tls).lower()}\n"
        "[node]\n"
        f"name = {_toml_str(cfg.node.name)}\n"
        f"capacity = {max(1, int(cfg.node.capacity))}\n"
        "[sandbox]\n"
        f"case_parallel = {max(1, int(cfg.sandbox.case_parallel))}\n"
        f"box_acquire_timeout_seconds = {max(1.0, float(cfg.sandbox.box_acquire_timeout_seconds)):.1f}\n"
        "[cache]\n"
        f"max_mb = {int(cfg.cache.max_mb)}\n",
        encoding="utf-8",
    )

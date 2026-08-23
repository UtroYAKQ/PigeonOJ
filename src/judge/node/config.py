"""判题节点配置（node.toml + 环境变量覆盖，标准库 tomllib）。

节点固定运行在 Docker 容器内（pigeonoj/judge-node 镜像）：
- 工作区固定为容器内 /sandbox（宿主机目录由 docker run -v <host>:/sandbox 指定）
- 题目数据缓存固定为容器内 /cache
"""
from __future__ import annotations

import os
import socket
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ServerConfig:
    address: str = "127.0.0.1:50051"
    token: str = ""


@dataclass
class NodeConfig:
    id: str = ""                # 留空自动 {hostname}-{pid}
    name: str = ""
    capacity: int = 2


@dataclass
class PathsConfig:
    workspace: str = "/sandbox"   # 容器内路径；宿主机目录由挂载决定
    data_cache: str = "/cache"


@dataclass
class SandboxConfig:
    nsjail_binary: str = "nsjail"
    nsjail_config: str = "/etc/pigeonoj/nsjail.cfg"


@dataclass
class JudgeNodeConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    node: NodeConfig = field(default_factory=NodeConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)


def load_config(path: str | Path) -> JudgeNodeConfig:
    raw: dict = {}
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    cfg = JudgeNodeConfig(
        server=ServerConfig(**raw.get("server", {})),
        node=NodeConfig(**raw.get("node", {})),
        paths=PathsConfig(**raw.get("paths", {})),
        sandbox=SandboxConfig(**raw.get("sandbox", {})),
    )

    # 环境变量覆盖（compose/K8s 注入场景）
    cfg.server.address = os.environ.get("SERVER_ADDRESS", cfg.server.address)
    cfg.server.token = os.environ.get("SERVER_TOKEN", cfg.server.token)
    cfg.node.id = os.environ.get("JUDGE_NODE_ID", cfg.node.id)
    cfg.node.name = os.environ.get("JUDGE_NODE_NAME", cfg.node.name)
    if cap := os.environ.get("JUDGE_NODE_CAPACITY"):
        cfg.node.capacity = int(cap)

    if not cfg.node.id:
        cfg.node.id = f"{socket.gethostname()}-{os.getpid()}"
    return cfg

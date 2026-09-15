"""判题节点本机管理页（标准库 http.server，默认只绑 127.0.0.1）。

GET  /           管理页
GET  /api/status 运行状态（token 掩码）
POST /api/config 写回 node.toml；网关/令牌变更后请求重连
POST /api/ping   TCP 探测网关 host:port
POST /api/reconnect 断开当前 gRPC 流并由主循环重连
"""
from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from config import JudgeNodeConfig, save_config

_INDEX = Path(__file__).resolve().parent / "admin.html"
_MASK = "********"


def mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 4:
        return _MASK
    return token[:2] + _MASK + token[-2:]


def parse_gateway(address: str) -> tuple[str, int]:
    raw = (address or "").strip()
    if not raw:
        raise ValueError("empty address")
    if "://" in raw:
        parts = urlsplit(raw)
        host = parts.hostname or ""
        port = parts.port or (443 if parts.scheme == "https" else 80)
        if not host:
            raise ValueError("invalid address")
        return host, port
    if raw.startswith("[") and "]" in raw:
        host, _, rest = raw[1:].partition("]")
        port = int(rest[1:]) if rest.startswith(":") else 50051
        return host, port
    if raw.count(":") == 1:
        host, _, port_s = raw.partition(":")
        return host, int(port_s)
    return raw, 50051


def tcp_probe(host: str, port: int, *, timeout: float = 2.0) -> dict[str, Any]:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {
                "ok": True, "host": host, "port": port,
                "latency_ms": int((time.monotonic() - started) * 1000), "error": "",
            }
    except OSError as exc:
        return {
            "ok": False, "host": host, "port": port,
            "latency_ms": int((time.monotonic() - started) * 1000), "error": str(exc),
        }


def apply_updates(cfg: JudgeNodeConfig, payload: dict) -> str:
    if "gateway" in payload and payload["gateway"] is not None:
        address = str(payload["gateway"]).strip()
        try:
            parse_gateway(address)
        except (ValueError, TypeError):
            return "invalid gateway"
        cfg.server.address = address
    if payload.get("token") and payload["token"] != _MASK:
        cfg.server.token = str(payload["token"]).strip()
        if not cfg.server.token:
            return "token required"
    if "tls" in payload and payload["tls"] is not None:
        cfg.server.tls = bool(payload["tls"])
    if "name" in payload and payload["name"] is not None:
        cfg.node.name = str(payload["name"]).strip()
    if "capacity" in payload and payload["capacity"] is not None:
        try:
            cfg.node.capacity = max(1, int(payload["capacity"]))
        except (TypeError, ValueError):
            return "invalid capacity"
    if "case_parallel" in payload and payload["case_parallel"] is not None:
        try:
            cfg.sandbox.case_parallel = max(1, int(payload["case_parallel"]))
        except (TypeError, ValueError):
            return "invalid case_parallel"
    if "cache_max_mb" in payload and payload["cache_max_mb"] is not None:
        try:
            cfg.cache.max_mb = max(0, int(payload["cache_max_mb"]))
        except (TypeError, ValueError):
            return "invalid cache_max_mb"
    return ""


class NodeAdmin:
    def __init__(self, daemon, config_path: str) -> None:
        self.daemon = daemon
        self.config_path = str(config_path)
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        cfg = self.daemon.cfg
        if not cfg.admin.bind or cfg.admin.port <= 0:
            return
        handler = _make_handler(self)
        self._httpd = ThreadingHTTPServer((cfg.admin.bind, cfg.admin.port), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="node-admin", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


def _make_handler(admin: NodeAdmin):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/" or self.path.startswith("/?"):
                data = _INDEX.read_bytes()
                self._send(200, data, "text/html; charset=utf-8")
                return
            if self.path == "/api/status":
                self._send_json(200, _status_payload(admin))
                return
            self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            if length > 64 * 1024:
                self._send_json(413, {"ok": False, "error": "payload too large"})
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            if self.path == "/api/config":
                self._save(payload if isinstance(payload, dict) else {})
                return
            if self.path == "/api/ping":
                self._ping(payload if isinstance(payload, dict) else {})
                return
            if self.path == "/api/reconnect":
                admin.daemon.request_reconnect()
                self._send_json(200, {"ok": True})
                return
            self._send_json(404, {"ok": False, "error": "not found"})

        def _save(self, payload: dict) -> None:
            cfg = admin.daemon.cfg
            error = apply_updates(cfg, payload)
            if error:
                self._send_json(400, {"ok": False, "error": error})
                return
            reconnect = bool(
                payload.get("gateway")
                or payload.get("tls") is not None
                or (payload.get("token") and payload["token"] != _MASK)
            )
            try:
                save_config(admin.config_path, cfg)
            except OSError as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            if reconnect:
                admin.daemon.request_reconnect()
            self._send_json(200, {"ok": True, "reconnect": reconnect})

        def _ping(self, payload: dict) -> None:
            address = payload.get("gateway") or admin.daemon.cfg.server.address
            try:
                host, port = parse_gateway(str(address))
            except (ValueError, TypeError) as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, tcp_probe(host, port))

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, code: int, body: dict) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self._send(code, data, "application/json; charset=utf-8")

    return Handler


def _status_payload(admin: NodeAdmin) -> dict[str, Any]:
    daemon = admin.daemon
    cfg = daemon.cfg
    cache_mb = 0.0
    try:
        cache_mb = round(daemon.cache.total_size() / 1048576, 1)
    except OSError:
        pass
    return {
        "connected": bool(getattr(daemon, "registered", False)),
        "connection_state": getattr(daemon, "connection_state", "disconnected"),
        "last_error_code": getattr(daemon, "last_error_code", "") or "",
        "last_error": getattr(daemon, "last_error", "") or "",
        "gateway": cfg.server.address,
        "tls": cfg.server.tls,
        "token_masked": mask_token(cfg.server.token),
        "node_id": daemon.node_id,
        "name": cfg.node.name or daemon.node_id,
        "capacity": cfg.node.capacity,
        "running_tasks": daemon.running_tasks,
        "case_parallel": cfg.sandbox.case_parallel,
        "cache_max_mb": cfg.cache.max_mb,
        "cache_used_mb": cache_mb,
        "cpu_usage": daemon._cpu_usage(),
        "memory_usage": daemon._memory_usage(),
        "heartbeat_interval": daemon.heartbeat_interval,
        "version": "nsjail-node-1.3",
        "admin_bind": cfg.admin.bind,
        "admin_port": cfg.admin.port,
    }

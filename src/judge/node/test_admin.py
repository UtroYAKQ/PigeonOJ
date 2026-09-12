"""节点管理页：地址解析、令牌掩码、配置写回、TCP 探测。"""
from __future__ import annotations

import socket

import pytest

from admin_server import apply_updates, mask_token, parse_gateway, tcp_probe
from daemon import classify_gateway_error
from config import JudgeNodeConfig, apply_runtime_overlay, load_config, save_config, save_runtime_overlay


def test_classify_gateway_error():
    assert classify_gateway_error(details="invalid node token")[0] == "token"
    assert classify_gateway_error(code="UNAUTHENTICATED")[0] == "token"
    assert classify_gateway_error(details="Failed to connect to remote host: Connection refused")[0] == "unreachable"
    assert classify_gateway_error(code="UNAVAILABLE")[0] == "unreachable"
    assert classify_gateway_error(text="SSL handshake failure")[0] == "tls"


def test_parse_gateway_host_port():
    assert parse_gateway("127.0.0.1:50051") == ("127.0.0.1", 50051)
    assert parse_gateway("example.com:443") == ("example.com", 443)


def test_parse_gateway_url_and_ipv6():
    assert parse_gateway("https://oj.example.com")[1] == 443
    assert parse_gateway("[::1]:50051") == ("::1", 50051)


def test_parse_gateway_rejects_empty():
    with pytest.raises(ValueError):
        parse_gateway("  ")


def test_mask_token():
    assert mask_token("") == ""
    assert mask_token("ab") == "********"
    assert mask_token("dev-token").startswith("de")
    assert "token" not in mask_token("dev-token")


def test_apply_updates_skips_masked_token():
    cfg = JudgeNodeConfig()
    cfg.server.token = "secret-token"
    err = apply_updates(cfg, {"token": "********", "capacity": 4, "gateway": "10.0.0.2:50051"})
    assert err == ""
    assert cfg.server.token == "secret-token"
    assert cfg.node.capacity == 4
    assert cfg.server.address == "10.0.0.2:50051"


def test_apply_updates_rejects_bad_gateway():
    cfg = JudgeNodeConfig()
    assert apply_updates(cfg, {"gateway": "://"}) == "invalid gateway"


def test_save_and_load_config_roundtrip(tmp_path):
    cfg = JudgeNodeConfig()
    cfg.server.address = "192.168.1.9:50051"
    cfg.server.token = "abc"
    cfg.server.tls = True
    cfg.node.capacity = 3
    cfg.sandbox.case_parallel = 2
    cfg.admin.port = 18080
    cfg.paths.data_cache = str(tmp_path / "cache")
    path = tmp_path / "node.toml"
    save_config(path, cfg)
    loaded = load_config(path)
    assert loaded.server.address == "192.168.1.9:50051"
    assert loaded.server.token == "abc"
    assert loaded.server.tls is True
    assert loaded.node.capacity == 3
    assert loaded.sandbox.case_parallel == 2
    assert loaded.admin.port == 18080


def test_runtime_overlay_wins_over_env(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    toml = tmp_path / "node.toml"
    toml.write_text(
        '[server]\naddress="127.0.0.1:50051"\ntoken="t"\n'
        '[node]\ncapacity=2\n[paths]\ndata_cache="%s"\n' % cache.as_posix().replace("\\", "/"),
        encoding="utf-8",
    )
    monkeypatch.setenv("JUDGE_NODE_CAPACITY", "2")
    cfg = load_config(toml)
    cfg.node.capacity = 8
    save_runtime_overlay(cfg)
    again = load_config(toml)
    assert again.node.capacity == 8


def test_tcp_probe_loopback():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        ok = tcp_probe("127.0.0.1", port)
        bad = tcp_probe("127.0.0.1", 1)
        assert ok["ok"] is True and ok["port"] == port
        assert bad["ok"] is False
    finally:
        srv.close()

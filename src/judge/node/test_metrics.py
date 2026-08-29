"""节点宿主指标采集测试（/proc/stat、/proc/meminfo 解析）。"""
from __future__ import annotations

import daemon as daemon_mod
from daemon import NodeDaemon, read_cpu_times, read_memory_usage


def test_read_cpu_times_parses_first_line(tmp_path):
    stat = tmp_path / "stat"
    stat.write_text("cpu  1000 20 300 5000 100 10 20 0 0 0\ncpu0 1 1 1 1 0 0 0 0 0 0\n")
    idle, total = read_cpu_times(str(stat))
    assert idle == 5100  # idle + iowait
    assert total == 6450


def test_read_cpu_times_missing_file(tmp_path):
    assert read_cpu_times(str(tmp_path / "nope")) is None


def test_read_cpu_times_malformed(tmp_path):
    stat = tmp_path / "stat"
    stat.write_text("cpu a b c d\n")
    assert read_cpu_times(str(stat)) is None


def test_read_memory_usage_with_available(tmp_path):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(
        "MemTotal:       1000 kB\nMemFree:          50 kB\nMemAvailable:    250 kB\n"
        "Buffers:          10 kB\nCached:           20 kB\n"
    )
    assert read_memory_usage(str(meminfo)) == 75  # (1000-250)/1000


def test_read_memory_usage_fallback_without_available(tmp_path):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:       1000 kB\nMemFree:         400 kB\nBuffers:          50 kB\nCached:          150 kB\n")
    assert read_memory_usage(str(meminfo)) == 40  # 1000-400-50-150


def test_read_memory_usage_missing_file(tmp_path):
    assert read_memory_usage(str(tmp_path / "nope")) is None


def test_cpu_usage_needs_baseline_then_computes_delta(monkeypatch):
    node = NodeDaemon.__new__(NodeDaemon)  # 跳过 __init__（不触碰执行器/配置）
    node.cpu_sample = None

    monkeypatch.setattr(daemon_mod, "read_cpu_times", lambda path="/proc/stat": (5100, 6450))
    assert node._cpu_usage() == 0  # 首次采样无基线

    monkeypatch.setattr(daemon_mod, "read_cpu_times", lambda path="/proc/stat": (5200, 6650))
    assert node._cpu_usage() == 50  # total +200，idle +100 → 占用 50%


def test_cpu_usage_zero_when_stat_unavailable(monkeypatch):
    node = NodeDaemon.__new__(NodeDaemon)
    node.cpu_sample = None
    monkeypatch.setattr(daemon_mod, "read_cpu_times", lambda path="/proc/stat": None)
    assert node._cpu_usage() == 0


def test_memory_usage_defaults_to_zero_when_unavailable(monkeypatch):
    node = NodeDaemon.__new__(NodeDaemon)
    monkeypatch.setattr(daemon_mod, "read_memory_usage", lambda path="/proc/meminfo": None)
    assert node._memory_usage() == 0

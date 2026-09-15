"""cgroup v2 内存采样与进程树 RSS 回退（docs/contracts/judge.md 内存测量）。"""
from __future__ import annotations

from executor import (
    _cgroup_contains_pid,
    _cgroup_peak_kb,
    _cgroup_usage_kb,
    _enable_memory_controller,
    _release_job_cgroup,
    _self_cgroup_v2_path,
    _tree_rss_kb,
)


def test_self_cgroup_v2_path_parses_container_root(tmp_path):
    (tmp_path / "cgroup.controllers").write_text("memory pids cpu\n")
    proc = tmp_path / "cgroup"
    proc.write_text("0::/\n")
    assert _self_cgroup_v2_path(proc_cgroup=str(proc), v2_root=tmp_path) == tmp_path


def test_self_cgroup_v2_path_parses_nested_docker_path(tmp_path):
    (tmp_path / "cgroup.controllers").write_text("memory\n")
    (tmp_path / "docker" / "abc").mkdir(parents=True)
    proc = tmp_path / "cgroup"
    proc.write_text("0::/docker/abc\n")
    assert _self_cgroup_v2_path(proc_cgroup=str(proc), v2_root=tmp_path) == tmp_path / "docker" / "abc"


def test_self_cgroup_v2_path_none_without_controllers(tmp_path):
    proc = tmp_path / "cgroup"
    proc.write_text("0::/\n")
    assert _self_cgroup_v2_path(proc_cgroup=str(proc), v2_root=tmp_path) is None


def test_self_cgroup_v2_path_ignores_v1_lines(tmp_path):
    (tmp_path / "cgroup.controllers").write_text("memory\n")
    proc = tmp_path / "cgroup"
    proc.write_text("1:name=systemd:/\n12:memory:/user.slice\n")
    assert _self_cgroup_v2_path(proc_cgroup=str(proc), v2_root=tmp_path) is None


def test_enable_memory_controller_skips_when_already_on(tmp_path):
    control = tmp_path / "cgroup.subtree_control"
    control.write_text("cpu memory pids\n")
    assert _enable_memory_controller(tmp_path) is True
    assert "memory" in control.read_text()


def test_enable_memory_controller_moves_self_then_writes_plus_memory(tmp_path):
    control = tmp_path / "cgroup.subtree_control"
    control.write_text("cpu pids\n")
    (tmp_path / "cgroup.procs").write_text("1\n")
    assert _enable_memory_controller(tmp_path) is True
    assert control.read_text() == "+memory"
    assert (tmp_path / "pigeonoj-daemon").is_dir()


def test_cgroup_usage_and_peak_kb(tmp_path):
    (tmp_path / "memory.current").write_bytes(b"1048576\n")
    (tmp_path / "memory.peak").write_bytes(b"2097152\n")
    assert _cgroup_usage_kb(tmp_path) == 1024
    assert _cgroup_peak_kb(tmp_path) == 2048


def test_cgroup_peak_falls_back_to_current(tmp_path):
    (tmp_path / "memory.current").write_bytes(b"4096\n")
    assert _cgroup_peak_kb(tmp_path) == 4


def test_cgroup_usage_missing_is_zero(tmp_path):
    assert _cgroup_usage_kb(tmp_path) == 0


def test_cgroup_contains_pid(tmp_path):
    (tmp_path / "cgroup.procs").write_text("10\n20\n")
    assert _cgroup_contains_pid(tmp_path, 20)
    assert not _cgroup_contains_pid(tmp_path, 30)


def test_release_job_cgroup_moves_leftover_to_daemon_leaf(tmp_path):
    daemon = tmp_path / "pigeonoj-daemon"
    daemon.mkdir()
    (daemon / "cgroup.procs").write_text("")
    leaf = tmp_path / "pigeonoj.1.1"
    leaf.mkdir()
    (leaf / "cgroup.procs").write_text("99\n")
    _release_job_cgroup(leaf)
    assert not leaf.exists()
    assert "99" in (daemon / "cgroup.procs").read_text()


def _write_proc_pid(proc: Path, pid: int, rss_kb: int, children: list[int], extra_tids: list[int] | None = None) -> None:
    status = proc / str(pid) / "status"
    status.parent.mkdir(parents=True)
    status.write_bytes(f"Name:\tjob\nVmRSS:\t{rss_kb} kB\n".encode())
    tids = [pid, *(extra_tids or [])]
    for tid in tids:
        task = proc / str(pid) / "task" / str(tid)
        task.mkdir(parents=True)
        payload = " ".join(str(c) for c in children) + ("\n" if children else "")
        (task / "children").write_text(payload if tid == pid else "")


def test_tree_rss_walks_descendants_only(tmp_path):
    proc = tmp_path / "proc"
    _write_proc_pid(proc, 10, 100, [11])
    _write_proc_pid(proc, 11, 50, [12])
    _write_proc_pid(proc, 12, 25, [])
    _write_proc_pid(proc, 99, 8000, [])  # 无关进程，不得计入
    assert _tree_rss_kb(10, proc_root=str(proc)) == 175


def test_tree_rss_missing_root_is_zero(tmp_path):
    assert _tree_rss_kb(1, proc_root=str(tmp_path / "proc")) == 0

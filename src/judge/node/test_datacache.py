"""题目数据缓存：分片追加与路径校验。"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from datacache import ProblemDataCache


class _Chunk:
    def __init__(self, path: str, content: bytes) -> None:
        self.path = path
        self.content = content


@pytest.mark.asyncio
async def test_sync_appends_same_path(tmp_path):
    cache = ProblemDataCache(tmp_path)

    async def stream():
        yield _Chunk("manifest.json", b'{"n":1}')
        yield _Chunk("cases/1.in", b"ab")
        yield _Chunk("cases/1.in", b"cd")

    await cache.sync("p", "v1", stream())
    assert (tmp_path / "p-v1" / "cases" / "1.in").read_bytes() == b"abcd"


@pytest.mark.asyncio
async def test_sync_rejects_path_traversal(tmp_path):
    cache = ProblemDataCache(tmp_path)

    async def stream():
        yield _Chunk("manifest.json", b"{}")
        yield _Chunk("../evil", b"x")

    with pytest.raises(RuntimeError, match="invalid problem data path"):
        await cache.sync("p", "v2", stream())

@pytest.mark.asyncio
async def test_sync_concurrent_same_version_reuses_result(tmp_path):
    """两个任务同时拉同一题目版本：后完成者不能因 rename 冲突报 system_error。"""
    cache = ProblemDataCache(tmp_path)

    def stream():
        async def gen():
            yield _Chunk("manifest.json", b"{}")
            yield _Chunk("cases/1.in", b"ab")
        return gen()

    results = await asyncio.gather(
        cache.sync("p", "v3", stream()),
        cache.sync("p", "v3", stream()),
    )
    assert all(path == tmp_path / "p-v3" for path in results)
    assert (tmp_path / "p-v3" / "cases" / "1.in").read_bytes() == b"ab"


@pytest.mark.asyncio
async def test_ensure_data_concurrent_fetches_once(tmp_path):
    """同题同版本并发只调用一次 FetchProblemData（daemon 侧锁去重）。"""
    from config import JudgeNodeConfig
    from daemon import NodeDaemon
    from gen import judge_pb2

    cfg = JudgeNodeConfig()
    cfg.paths.data_cache = str(tmp_path / "cache")
    node = NodeDaemon(cfg)
    calls = 0
    entered = asyncio.Event()
    release = asyncio.Event()

    class StubGateway:
        def FetchProblemData(self, request, metadata):
            nonlocal calls
            calls += 1

            async def chunks():
                entered.set()
                await release.wait()
                yield _Chunk("manifest.json", b"{}")

            return chunks()

    job = judge_pb2.SubmitJob(problem_id="p", data_version="v4")

    async def fetch() -> Path:
        return await node._ensure_data(StubGateway(), job)

    tasks = [asyncio.create_task(fetch()) for _ in range(3)]
    await asyncio.wait_for(entered.wait(), 5)
    await asyncio.sleep(0.01)
    release.set()
    paths = await asyncio.wait_for(asyncio.gather(*tasks), 5)
    assert all(path == tmp_path / "cache" / "p-v4" for path in paths)
    assert calls == 1


@pytest.mark.asyncio
async def test_total_size_tracks_synced_chunks(tmp_path):
    """sync 完成即登记目录字节数，total_size 不再扫描全树。"""
    cache = ProblemDataCache(tmp_path / "cache")

    async def stream():
        yield _Chunk("manifest.json", b"{}")
        yield _Chunk("cases/1.in", b"abcd")

    await cache.sync("p", "v1", stream())
    assert cache.total_size() == 6
    assert cache.collect(6) == []
    assert cache.total_size() == 6


def test_collect_updates_size_index_after_lru(tmp_path):
    """LRU 回收后索引同步剔除，占用中的目录保留。"""
    root = tmp_path / "cache"
    old, new = root / "p-v1", root / "p-v2"
    for path, content in ((old, b"aaa"), (new, b"bb")):
        (path / "cases").mkdir(parents=True)
        (path / "cases" / "1.in").write_bytes(content)
        (path / "manifest.json").write_bytes(b"{}")
    os.utime(old, (1, 1))
    cache = ProblemDataCache(root)
    cache.mark_in_use(new.name)
    assert cache.total_size() == 9
    assert cache.collect(2) == [old.name]
    assert cache.total_size() == 4
    assert new.is_dir()


def test_total_size_reconciles_on_restart(tmp_path, monkeypatch):
    """重启指向同一缓存目录时按现有目录对账，且 total_size 不触发 rglob。"""
    root = tmp_path / "cache"
    data = root / "p-v1" / "cases"
    data.mkdir(parents=True)
    (data / "1.in").write_bytes(b"x" * 4096)
    (root / "p-v1" / "manifest.json").write_bytes(b"{}")
    cache = ProblemDataCache(root)
    assert cache.total_size() == 4098

    def no_rglob(*_args, **_kwargs):
        raise AssertionError("total_size 不应扫描文件树")

    monkeypatch.setattr(Path, "rglob", no_rglob)
    assert cache.total_size() == 4098

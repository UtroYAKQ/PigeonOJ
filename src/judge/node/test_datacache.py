"""题目数据缓存：分片追加与路径校验。"""
from __future__ import annotations

import asyncio

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

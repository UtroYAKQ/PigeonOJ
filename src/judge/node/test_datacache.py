"""题目数据缓存：分片追加与路径校验。"""
from __future__ import annotations

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

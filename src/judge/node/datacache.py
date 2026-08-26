"""题目数据缓存：按 <problem_id>-<data_version> 惰性拉取并落盘。

容量有界：collect() 按 mtime 从旧到新回收（LRU），运行中作业的目录受
mark_in_use/unmark_in_use 保护不会被删除；max_mb<=0 表示不限制（不回收）。
"""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path


class ProblemDataCache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._in_use: set[str] = set()

    def dir_for(self, problem_id: str, data_version: str) -> Path:
        return self.root / f"{problem_id}-{data_version}"

    def has(self, problem_id: str, data_version: str) -> bool:
        hit = (self.dir_for(problem_id, data_version) / "manifest.json").is_file()
        if hit:
            # 命中即刷新 mtime，供 LRU 回收判定"最近使用"
            os.utime(self.dir_for(problem_id, data_version), None)
        return hit

    def mark_in_use(self, dir_name: str) -> None:
        self._in_use.add(dir_name)

    def unmark_in_use(self, dir_name: str) -> None:
        self._in_use.discard(dir_name)

    async def sync(self, problem_id: str, data_version: str, chunk_stream) -> Path:
        """chunk_stream：FetchProblemData 的异步流（由调用方携带认证元数据发起）。"""
        target = self.dir_for(problem_id, data_version)
        if self.has(problem_id, data_version):
            return target
        task_name = asyncio.current_task().get_name()
        tmp = target.with_name(target.name + f".tmp-{task_name}")
        tmp.mkdir(parents=True, exist_ok=True)
        count = 0
        try:
            async for chunk in chunk_stream:
                dest = tmp / chunk.path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(chunk.content)
                count += 1
            if count == 0 or not (tmp / "manifest.json").exists():
                raise RuntimeError("empty or invalid problem data stream")
            tmp.rename(target)
            os.utime(target, None)
        finally:
            if tmp.exists():
                for p in sorted(tmp.rglob("*"), reverse=True):
                    p.unlink() if p.is_file() else p.rmdir()
                tmp.rmdir()
        return target

    def total_size(self) -> int:
        """缓存总字节数（跳过 .tmp-* 过渡目录）。"""
        return sum(
            f.stat().st_size
            for d in self.root.iterdir() if d.is_dir() and ".tmp-" not in d.name
            for f in d.rglob("*") if f.is_file()
        )

    def collect(self, max_bytes: int) -> list[str]:
        """超过 max_bytes 时按 mtime 从旧到新回收目录，返回被删目录名列表。

        运行中作业的目录（_in_use）与 .tmp-* 过渡目录不参与回收；
        单目录超限且被占用时尽力而为，剩余留给下次巡检。
        """
        if max_bytes <= 0:
            return []
        entries: list[tuple[float, int, Path]] = []
        total = 0
        for d in self.root.iterdir():
            if not d.is_dir() or ".tmp-" in d.name:
                continue
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            entries.append((d.stat().st_mtime, size, d))
            total += size
        if total <= max_bytes:
            return []
        removed: list[str] = []
        for _, size, path in sorted(entries, key=lambda e: e[0]):
            if total <= max_bytes:
                break
            if path.name in self._in_use:
                continue
            shutil.rmtree(path, ignore_errors=True)
            total -= size
            removed.append(path.name)
        return removed

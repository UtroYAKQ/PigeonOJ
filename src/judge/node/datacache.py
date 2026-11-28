"""题目数据缓存：按 <problem_id>-<data_version> 惰性拉取并落盘。

容量有界：collect() 按 mtime 从旧到新回收（LRU），运行中作业的目录受
mark_in_use/unmark_in_use 保护不会被删除；max_mb<=0 表示不限制（不回收）。
"""
from __future__ import annotations

import asyncio
import os
import shutil
import threading
from pathlib import Path


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


class ProblemDataCache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._in_use: set[str] = set()
        self._sizes: dict[str, int] = {}
        self._sizes_lock = threading.Lock()
        # 重启后索引为空：按现有就绪目录对账一次，避免管理页首次显示 0
        with self._sizes_lock:
            for d in self.root.iterdir():
                if d.is_dir() and ".tmp-" not in d.name:
                    self._sizes[d.name] = _dir_size(d)

    def dir_for(self, problem_id: str, data_version: str) -> Path:
        return self.root / f"{problem_id}-{data_version}"

    def has(self, problem_id: str, data_version: str) -> bool:
        target = self.dir_for(problem_id, data_version)
        hit = (target / "manifest.json").is_file()
        if hit:
            # 命中即刷新 mtime，供 LRU 回收判定"最近使用"
            os.utime(target, None)
        return hit

    async def has_async(self, problem_id: str, data_version: str) -> bool:
        """异步调用方走线程池：has 命中时的 os.utime 不阻塞事件循环。"""
        return await asyncio.to_thread(self.has, problem_id, data_version)

    @staticmethod
    def _write_chunk(dest: Path, content: bytes) -> None:
        """单个分块落盘；调用方保证同一 path 的调用严格串行。"""
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("ab") as fh:
            fh.write(content)

    def mark_in_use(self, dir_name: str) -> None:
        self._in_use.add(dir_name)

    def unmark_in_use(self, dir_name: str) -> None:
        self._in_use.discard(dir_name)

    async def sync(self, problem_id: str, data_version: str, chunk_stream) -> Path:
        """chunk_stream：FetchProblemData 的异步流（由调用方携带认证元数据发起）。"""
        target = self.dir_for(problem_id, data_version)
        if await self.has_async(problem_id, data_version):
            return target
        task_name = asyncio.current_task().get_name()
        tmp = target.with_name(target.name + f".tmp-{task_name}")
        tmp.mkdir(parents=True, exist_ok=True)
        count = 0
        try:
            async for chunk in chunk_stream:
                rel = str(chunk.path).replace("\\", "/").lstrip("/")
                if not rel or rel.startswith("/") or ".." in Path(rel).parts:
                    raise RuntimeError("invalid problem data path")
                dest = tmp / rel
                # 顺序 await 保证同 path 分块严格按流中顺序追加；文件 I/O 不占事件循环线程
                await asyncio.to_thread(self._write_chunk, dest, chunk.content or b"")
                count += 1
            if count == 0 or not (tmp / "manifest.json").exists():
                raise RuntimeError("empty or invalid problem data stream")
            try:
                tmp.rename(target)
            except OSError:
                # 并发拉取同一题目版本：另一个任务已先落盘，复用已有目录即可；
                # 否则说明目标目录损坏（无 manifest），交回上层报错
                if await self.has_async(problem_id, data_version):
                    return target
                raise
            os.utime(target, None)
            with self._sizes_lock:
                self._sizes[target.name] = _dir_size(target)
        finally:
            if tmp.exists():
                for p in sorted(tmp.rglob("*"), reverse=True):
                    p.unlink() if p.is_file() else p.rmdir()
                tmp.rmdir()
        return target

    def total_size(self) -> int:
        """缓存总字节数：直接读索引，不每次 rglob/stat 全树。"""
        with self._sizes_lock:
            return sum(self._sizes.values())

    def collect(self, max_bytes: int) -> list[str]:
        """超过 max_bytes 时按 mtime 从旧到新回收目录，返回被删目录名列表。

        运行中作业的目录（_in_use）与 .tmp-* 过渡目录不参与回收；
        单目录超限且被占用时尽力而为，剩余留给下次巡检。
        """
        if max_bytes <= 0:
            return []
        entries: list[tuple[float, int, Path]] = []
        with self._sizes_lock:
            for d in self.root.iterdir():
                if not d.is_dir() or ".tmp-" in d.name:
                    continue
                size = self._sizes.get(d.name)
                if size is None:  # 外部新建的目录：首次纳入索引
                    size = _dir_size(d)
                    self._sizes[d.name] = size
                entries.append((d.stat().st_mtime, size, d))
            total = sum(entry[1] for entry in entries)
            # 外部已删除的目录不留陈旧索引
            names = {d.name for _, _, d in entries}
            for name in [n for n in self._sizes if n not in names]:
                del self._sizes[name]
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
            with self._sizes_lock:
                self._sizes.pop(path.name, None)
        return removed

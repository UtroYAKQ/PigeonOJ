"""题目数据缓存：按 <problem_id>-<data_version> 惰性拉取并落盘。"""
from __future__ import annotations

import asyncio
from pathlib import Path


class ProblemDataCache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def dir_for(self, problem_id: str, data_version: str) -> Path:
        return self.root / f"{problem_id}-{data_version}"

    def has(self, problem_id: str, data_version: str) -> bool:
        return (self.dir_for(problem_id, data_version) / "manifest.json").is_file()

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
        finally:
            if tmp.exists():
                for p in sorted(tmp.rglob("*"), reverse=True):
                    p.unlink() if p.is_file() else p.rmdir()
                tmp.rmdir()
        return target

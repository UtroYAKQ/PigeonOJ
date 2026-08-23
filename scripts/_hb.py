"""验证 gRPC 网关注册表与 Redis 心跳桥接（临时脚本）。"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, r"C:\Users\33112\Documents\MyCode\work\PigeonOJ\src\backend")

from app.modules.judge.gateway import REGISTRY


async def main() -> None:
    nodes = await REGISTRY.list_nodes()
    print("gateway registered:", [(n["id"], n["channel"]) for n in nodes])


asyncio.run(main())

"""判题派发：全部经 gRPC 网关注册表负载均衡（docs/contracts/judge.md 节点网关协议）。

无在线节点时提交保持 pending，由网关维护循环周期性重扫派发。
"""
from __future__ import annotations


async def active_judge_count() -> int:
    """全平台正在判题的任务数（提交并发上限 4002 依据）。"""
    from app.modules.judge import gateway

    return sum(len(conn.inflight) for conn in gateway.REGISTRY.list_nodes())


__all__ = ["active_judge_count"]

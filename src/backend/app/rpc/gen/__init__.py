"""gRPC 生成代码包（scripts/gen_proto.py 产出）。统一经本包导入：

    from app.rpc.gen import judge_pb2, judge_pb2_grpc  # 后端
    from gen import judge_pb2, judge_pb2_grpc          # 节点
"""
from __future__ import annotations

from ._shim import judge_pb2, judge_pb2_grpc

__all__ = ["judge_pb2", "judge_pb2_grpc"]

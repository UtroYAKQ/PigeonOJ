from __future__ import annotations

import pathlib
import sys

_DIR = pathlib.Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from pigeonoj.judge.v1 import judge_pb2, judge_pb2_grpc  # noqa: E402,F401
__all__ = ['judge_pb2', 'judge_pb2_grpc']

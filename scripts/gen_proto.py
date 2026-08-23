"""生成 gRPC 双端 stub：protos/pigeonoj/judge/v1/judge.proto → 后端 + 判题节点。

用法：先安装代码生成依赖 `pip install grpcio-tools`，然后在仓库根目录执行：
    python scripts/gen_proto.py
生成产物直接提交入库，运行时不需要 protoc。
"""
from __future__ import annotations

import pathlib

from grpc_tools import protoc

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROTO_DIR = ROOT / "protos"
TARGETS = [
    ROOT / "src" / "backend" / "app" / "modules" / "judge" / "rpc_gen",
    ROOT / "src" / "judge" / "node" / "gen",
]

_INIT = '"""gRPC 生成包（scripts/gen_proto.py 产出，勿手改）。"""\n'


def main() -> None:
    for target in TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        protoc.main(
            [
                "protoc",  # 程序名占位（grpc_tools 约定）
                f"-I{PROTO_DIR}",
                f"--python_out={target}",
                f"--grpc_python_out={target}",
                str(PROTO_DIR / "pigeonoj" / "judge" / "v1" / "judge.proto"),
            ]
        )
        # 命名空间子包链上的 __init__.py（不含目标根本身）
        for pkg in (target / "pigeonoj", target / "pigeonoj" / "judge", target / "pigeonoj" / "judge" / "v1"):
            (pkg / "__init__.py").write_text(_INIT, encoding="utf-8")
        # 顶层垫片：sys.path 注入后按 pigeonoj.judge.v1 再导出，
        # 使用方统一写 `from <本包> import judge_pb2, judge_pb2_grpc`
        (target / "_shim.py").write_text(
            "from __future__ import annotations\n\n"
            "import pathlib\nimport sys\n\n"
            "_DIR = pathlib.Path(__file__).resolve().parent\n"
            "if str(_DIR) not in sys.path:\n"
            "    sys.path.insert(0, str(_DIR))\n\n"
            "from pigeonoj.judge.v1 import judge_pb2, judge_pb2_grpc  # noqa: E402,F401\n"
            "__all__ = ['judge_pb2', 'judge_pb2_grpc']\n",
            encoding="utf-8",
        )
        (target / "__init__.py").write_text(
            '"""gRPC 生成代码包（scripts/gen_proto.py 产出）。统一经本包导入：\n\n'
            "    from app.modules.judge.rpc_gen import judge_pb2, judge_pb2_grpc  # 后端\n"
            "    from gen import judge_pb2, judge_pb2_grpc                        # 节点\n"
            '"""\n'
            "from __future__ import annotations\n\n"
            "from ._shim import judge_pb2, judge_pb2_grpc\n\n"
            '__all__ = ["judge_pb2", "judge_pb2_grpc"]\n',
            encoding="utf-8",
        )
        print(f"generated -> {target}")


if __name__ == "__main__":
    main()
